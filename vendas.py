from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from fpdf import FPDF
import socket
import tempfile
import os
import random
import string
from zoneinfo import ZoneInfo
import requests
from decimal import Decimal
from datetime import datetime, date
FISCAL_API_URL = "https://nfcee.onrender.com"
FISCAL_API_TOKEN = "fiscal_secreto_2026"

def normalizar_json(obj):
    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {k: normalizar_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [normalizar_json(i) for i in obj]

    return obj



from auth_clientes import verificar_token_cliente
from database import executar_insert, executar_select, executar_comando
def log(msg):
    print(f"[VENDAS][{datetime.now().strftime('%H:%M:%S')}] {msg}")

router = APIRouter()
def pos_processar_venda(venda_id, comercio, produtos, pagamento, total, cpf):
    caminho_pdf = gerar_pdf_comanda(
        venda_id, comercio, produtos, pagamento, total
    )

    nome_arquivo = os.path.basename(caminho_pdf)

    with open(caminho_pdf, "rb") as f:
        supabase.storage.from_("assinaturas").upload(
            f"comandas/{nome_arquivo}",
            f.read(),
            {"content-type": "application/pdf"}
        )

    base_url = supabase.storage.from_("assinaturas").get_public_url(
        f"comandas/{nome_arquivo}"
    )

    url_pdf = f"{base_url}&response-content-disposition=attachment"

    executar_comando(
        "UPDATE vendas_ib SET comanda = %s WHERE id = %s",
        (url_pdf, venda_id)
    )

    if comercio.get("node") == 1:
        log(f"Node ativo, imprimindo comanda da venda {venda_id}")
        requests.post(
            "http://localhost:3334/print",
            json={"url": url_pdf},
            timeout=5
        )


        log(f"Comanda enviada para impressão venda {venda_id}")

    try:
        payload = {}
        if cpf:
            payload["cpf"] = cpf

        resp = requests.post(
            f"{FISCAL_API_URL}/nfce/emitir/{venda_id}",
            json=payload if payload else None,
            headers={"Authorization": f"Bearer {FISCAL_API_TOKEN}"},
            timeout=15
        )

        if resp.status_code == 200:
            executar_comando(
                "UPDATE vendas_ib SET status = %s WHERE id = %s",
                ("nfce_emitida", venda_id)
            )
            log(f"NFC-e emitida com sucesso venda {venda_id}")
        else:
            log(f"NFC-e NÃO emitida venda {venda_id} | {resp.text}")

    except Exception as e:
        log(f"Erro na emissão automática NFC-e venda {venda_id}: {e}")

@router.get("/vendas/nfce-pendentes")
def listar_nfce_pendentes(usuario=Depends(verificar_token_cliente)):

    if "id" not in usuario:
        raise HTTPException(status_code=401, detail="Usuário inválido")

    cliente = executar_select(
        "SELECT comercio_id FROM clientes WHERE id = %s",
        (usuario["id"],)
    )

    if not cliente or not cliente[0]["comercio_id"]:
        raise HTTPException(status_code=400, detail="Cliente sem comércio vinculado")

    comercio_id = cliente[0]["comercio_id"]

    vendas = executar_select(
        """
        SELECT 
            id,
            valor_pago,
            pagamento,
    DATE(created_at) AS data,
    TIME(DATE_SUB(created_at, INTERVAL 3 HOUR)) AS hora,
            comanda
        FROM vendas_ib
        WHERE empresa = %s
          AND status = 'nfce_pendente'
        ORDER BY id DESC
        """,
        (comercio_id,)
    )

    return vendas

@router.post("/vendas/{venda_id}/emitir-nfce")
def emitir_nfce_manual(venda_id: int, usuario=Depends(verificar_token_cliente)):
    log(f"Solicitação de emissão NFC-e da venda {venda_id}")

    venda = executar_select(
        "SELECT * FROM vendas_ib WHERE id = %s",
        (venda_id,)
    )

    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    venda = venda[0]

    if venda["status"] != "nfce_pendente":
        raise HTTPException(status_code=409, detail="Venda não está pendente de NFC-e")

    cpf = venda.get("cpf_consumidor")

    try:
        payload = {}
        if cpf:
            payload["cpf"] = cpf

        resp = requests.post(
            f"{FISCAL_API_URL}/nfce/emitir/{venda_id}",
            json=payload if payload else None,
            headers={
                "Authorization": f"Bearer {FISCAL_API_TOKEN}"
            },
            timeout=30
        )

        if resp.status_code != 200:
            try:
                erro = resp.json()
                detalhe = erro.get("detail") or erro.get("erro") or resp.text
            except Exception:
                detalhe = resp.text

            raise HTTPException(
                status_code=resp.status_code,
                detail=detalhe
            )

    except HTTPException:
        raise

    except Exception as e:
        log(f"Erro de comunicação com API fiscal: {e}")
        raise HTTPException(
            status_code=502,
            detail="Falha ao comunicar com o serviço fiscal"
        )

    executar_comando(
        "UPDATE vendas_ib SET status = %s WHERE id = %s",
        ("nfce_emitida", venda_id)
    )

    return {
        "ok": True,
        "venda_id": venda_id,
        "mensagem": "NFC-e emitida com sucesso"
    }

# SUPABASE
# ===============================
SUPABASE_URL = "https://mtljmvivztkgoolnnwxc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im10bGptdml2enRrZ29vbG5ud3hjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQwMzM0MywiZXhwIjoyMDc4OTc5MzQzfQ.XFJVnYVbK-pxJ7oftduk680YsXltdUB06Yr_buIoJPA"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
def enviar_pagamento_maquininha(valor, metodo, comercio, maquininha):
    """
    Retorna True se aprovado
    Retorna False se recusado
    """

    payload = {
        "valor_centavos": int(valor * 100),
        "metodo": metodo,
        "maquininha_numero": maquininha["maquininha_numero"],
        "comercio_id": comercio["id"]
    }

    # SIMULAÇÃO POR ENQUANTO
    resposta = {
        "status": "aprovado"
    }

    return resposta["status"] == "aprovado"

def verificar_conexao_maquininha(maquininha):
    """
    Retorna True se a maquininha estiver conectada
    Retorna False se não estiver
    """

    # Por enquanto é controle lógico
    # Depois aqui entra ping, socket, request, etc.
    if maquininha.get("ativa") == 1:
        return True

    return False



# ===============================
# GERAR CÓDIGO ÚNICO
# ===============================
def gerar_codigo_unico():
    while True:
        codigo = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=10)
        )
        existe = executar_select(
            "SELECT id FROM vendas_ib WHERE codigo = %s",
            (codigo,)
        )
        if not existe:
            return codigo

# ===============================
# PDF COMANDA 80mm CORRETA
# ===============================

def gerar_pdf_comanda(venda_id, comercio, produtos, pagamento, total):
    W = 64            # largura real segura para 80mm
    SEP = "-" * 26    # separador que NÃO estoura

    pdf = FPDF(unit="mm", format=(80, 300))
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()

    # ===============================
    # CABEÇALHO
    # ===============================
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(W, 6, comercio["loja"].upper(), ln=True, align="C")

    pdf.set_font("Helvetica", "B", size=9.5)


    if comercio.get("cnpj"):
        pdf.cell(W, 4, f"CNPJ: {comercio['cnpj']}", ln=True, align="C")

    if comercio.get("rua"):
        pdf.cell(W, 4, f"{comercio['rua']}, {comercio['numero']}", ln=True, align="C")

    if comercio.get("bairro"):
        pdf.cell(
            W,
            4,
            f"{comercio['bairro']} - {comercio['cidade']}/{comercio['estado']}",
            ln=True,
            align="C"
        )

    if comercio.get("cep"):
        pdf.cell(W, 4, f"CEP {comercio['cep']}", ln=True, align="C")

    if comercio.get("email"):
        pdf.cell(W, 4, comercio["email"], ln=True, align="C")

    if comercio.get("celular"):
        pdf.cell(W, 4, comercio["celular"], ln=True, align="C")

    pdf.ln(2)
    pdf.cell(W, 4, SEP, ln=True, align="C")

    # ===============================
    # PROTOCOLO
    # ===============================
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(W, 4, f"PROTOCOLO {venda_id}", ln=True, align="C")
    pdf.cell(W, 4, f"PAGAMENTO {pagamento.upper()}", ln=True, align="C")
    pdf.cell(W, 4, SEP, ln=True, align="C")

    # ===============================
    # ITENS
    # ===============================
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(W, 4, "ITENS", ln=True, align="C")
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", size=9.5)

    for p in produtos:
        pdf.multi_cell(W, 4, p["nome"].upper(), align="C")

        if p.get("unidade"):
            pdf.set_font("Helvetica", "I", 7)
            pdf.cell(W, 4, f"Unidade: {p['unidade']}", ln=True, align="C")
            pdf.set_font("Helvetica", "B", size=9)

        pdf.cell(W, 4, f"{p['quantidade']} x R$ {p['preco']:.2f}", ln=True, align="C")

        pdf.set_font("Helvetica", "B", 8.8)
        pdf.cell(W, 4, f"Subtotal: R$ {p['subtotal']:.2f}", ln=True, align="C")
        pdf.set_font("Helvetica", "B", size=9)

        if p.get("tempo_servico"):
            pdf.set_font("Helvetica", "I", 7)
            pdf.multi_cell(W, 4, f"Pronto em {p['tempo_servico']}", align="C")
            pdf.set_font("Helvetica", "B", size=8)

        pdf.ln(1)

    # ===============================
    # TOTAL
    # ===============================
    pdf.cell(W, 4, SEP, ln=True, align="C")
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(W, 6, f"TOTAL R$ {total:.2f}", ln=True, align="C")
    pdf.cell(W, 4, SEP, ln=True, align="C")

    # ===============================
    # RODAPÉ (HORÁRIO BRASIL)
    # ===============================
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

    pdf.ln(1)
    pdf.set_font("Helvetica", "B", size=8.5)
    pdf.cell(W, 4, agora_br.strftime("%d/%m/%Y %H:%M"), ln=True, align="C")
    pdf.cell(W, 4, "OBRIGADO PELA PREFERÊNCIA", ln=True, align="C")

    # ===============================
    # NOME DO ARQUIVO
    # ===============================
    nome_arquivo = agora_br.strftime("comanda_%Y-%m-%d_%H-%M-%S.pdf")
    caminho = os.path.join(tempfile.gettempdir(), nome_arquivo)

    pdf.output(caminho)
    return caminho
# ===============================
# ROTA FINALIZAR VENDA
# ===============================
from fastapi import BackgroundTasks

@router.post("/vendas/finalizar")
def finalizar_venda(
    dados: dict,
    background_tasks: BackgroundTasks,
    usuario=Depends(verificar_token_cliente)
):


    log("INÍCIO DA ROTA /vendas/finalizar")

    try:
        if "id" not in usuario:
            raise HTTPException(status_code=401, detail="Usuário inválido")

        # ===============================
        # CPF DO CONSUMIDOR (OPCIONAL)
        # ===============================
        cpf = dados.get("cpf")
        if cpf:
            cpf = "".join(filter(str.isdigit, cpf))
            if len(cpf) != 11:
                cpf = None

        # ===============================
        # CLIENTE / COMÉRCIO
        # ===============================
        cliente = executar_select(
            "SELECT comercio_id FROM clientes WHERE id = %s",
            (usuario["id"],)
        )

        if not cliente or not cliente[0]["comercio_id"]:
            raise HTTPException(status_code=400, detail="Cliente sem comércio vinculado")

        comercio_id = cliente[0]["comercio_id"]

        comercio = executar_select(
            "SELECT * FROM comercios_cadastradas WHERE id = %s",
            (comercio_id,)
        )

        if not comercio:
            raise HTTPException(status_code=400, detail="Comércio não encontrado")

        comercio = comercio[0]

        # ===============================
        # PAGAMENTO COM MAQUININHA
        # ===============================
        maquininha = None

        if (
            comercio.get("api") == 1
            and dados["pagamento"] in ["debito", "credito", "pix"]
            and not dados.get("forcar_manual")
        ):
            maq = executar_select(
                "SELECT * FROM maquininhas WHERE comercio_id = %s AND ativa = 1 LIMIT 1",
                (comercio_id,)
            )

            if not maq:
                raise HTTPException(status_code=409, detail="Maquininha não conectada")

            maquininha = maq[0]

            if not verificar_conexao_maquininha(maquininha):
                raise HTTPException(status_code=409, detail="Maquininha não conectada")

            aprovado = enviar_pagamento_maquininha(
                valor=dados["valor"],
                metodo=dados["pagamento"],
                comercio=comercio,
                maquininha=maquininha
            )

            if not aprovado:
                raise HTTPException(status_code=402, detail="Pagamento recusado")

        # ===============================
        # REGISTRAR VENDA
        # ===============================
        produtos_txt = ",".join(
            f"{p['id']}:{p['quantidade']}"
            for p in dados["produtos"]
        )

        codigo = gerar_codigo_unico()
        agora = datetime.now()

        venda_id = executar_insert(
            """
            INSERT INTO vendas_ib
            (codigo, pagamento, realizada, empresa, valor_pago, data, hora,
             dispositivo, produtos, modulo, status, maquininha, cpf_consumidor)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                codigo,
                dados["pagamento"],
                usuario["id"],
                comercio_id,
                dados["valor"],
                agora.date(),
                agora.strftime("%H:%M:%S"),
                socket.gethostname(),
                produtos_txt,
                1,
                "nfce_pendente",
                maquininha["apelido"] if maquininha else None,
                cpf
            )
        )

        # ===============================
        # RECONSTRUIR PRODUTOS REAIS
        # ===============================
        produtos = []
        for item in produtos_txt.split(","):
            pid, qtd = item.split(":")

            prod = executar_select(
                """
                SELECT nome, preco, unidade, tempo_servico
                FROM produtos_servicos
                WHERE id = %s
                """,
                (pid,)
            )[0]

            produtos.append({
                "nome": prod["nome"],
                "quantidade": int(qtd),
                "preco": float(prod["preco"]),
                "subtotal": float(prod["preco"]) * int(qtd),
                "unidade": prod.get("unidade"),
                "tempo_servico": prod.get("tempo_servico")
            })

        # ===============================
        # PÓS PROCESSAMENTO ÚNICO
        # ===============================
        background_tasks.add_task(
            pos_processar_venda,
            venda_id,
            comercio,
            produtos,
            dados["pagamento"],
            dados["valor"],
            cpf
        )


        return {
            "ok": True,
            "venda_id": venda_id,
            "codigo": codigo
        }

    except HTTPException:
        raise

    except Exception as e:
        log(f"ERRO FINALIZAR VENDA: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao finalizar venda"
        )

@router.get("/comercio/status-pagamento")
def status_pagamento(usuario=Depends(verificar_token_cliente)):

    if "id" not in usuario:
        raise HTTPException(status_code=401, detail="Usuário inválido")

    cliente = executar_select(
        "SELECT comercio_id FROM clientes WHERE id = %s",
        (usuario["id"],)
    )

    if not cliente or not cliente[0]["comercio_id"]:
        raise HTTPException(status_code=400, detail="Cliente sem comércio vinculado")

    comercio_id = cliente[0]["comercio_id"]

    comercio = executar_select(
        "SELECT api FROM comercios_cadastradas WHERE id = %s",
        (comercio_id,)
    )

    if not comercio:
        raise HTTPException(status_code=404, detail="Comércio não encontrado")

    return {
        "api_maquininha": comercio[0]["api"] == 1
    }

@router.post("/vendas/pre-registrar")
def pre_registrar_venda(dados: dict, usuario=Depends(verificar_token_cliente)):

    log("PRÉ-REGISTRO DE VENDA (vendas_ib_p)")

    cliente = executar_select(
        "SELECT comercio_id FROM clientes WHERE id = %s",
        (usuario["id"],)
    )

    comercio_id = cliente[0]["comercio_id"]

    produtos_txt = ",".join(
        f"{p['id']}:{p['quantidade']}"
        for p in dados["produtos"]
    )

    codigo = gerar_codigo_unico()
    agora = datetime.now()

    venda_p_id = executar_insert(
        """
        INSERT INTO vendas_ib_p
        (codigo, pagamento, realizada, empresa, valor_pago, data, hora,
         dispositivo, produtos, modulo, status, maquininha, cpf_consumidor)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            codigo,
            dados["pagamento"],
            usuario["id"],
            comercio_id,
            dados["valor"],
            agora.date(),
            agora.strftime("%H:%M:%S"),
            socket.gethostname(),
            produtos_txt,
            1,
            "aguardando_confirmacao",
            None,
            dados.get("cpf")
        )
    )

    return {
        "ok": True,
        "venda_p_id": venda_p_id,
        "codigo": codigo
    }
@router.post("/vendas/confirmar-local/{venda_p_id}")
def confirmar_pagamento_local(
    venda_p_id: int,
    usuario=Depends(verificar_token_cliente)
):

    log(f"CONFIRMANDO VENDA LOCAL {venda_p_id}")

    # ===============================
    # BUSCAR PRÉ-VENDA
    # ===============================
    venda_p = executar_select(
        "SELECT * FROM vendas_ib_p WHERE id = %s",
        (venda_p_id,)
    )

    if not venda_p:
        raise HTTPException(status_code=404, detail="Pré-venda não encontrada")

    venda_p = venda_p[0]

    # ===============================
    # BUSCAR COMÉRCIO
    # ===============================
    comercio = executar_select(
        "SELECT * FROM comercios_cadastradas WHERE id = %s",
        (venda_p["empresa"],)
    )

    if not comercio:
        raise HTTPException(status_code=400, detail="Comércio não encontrado")

    comercio = comercio[0]

    # ===============================
    # INSERIR NA vendas_ib
    # ===============================
    venda_id = executar_insert(
        """
        INSERT INTO vendas_ib
        (codigo, pagamento, realizada, empresa, valor_pago, data, hora,
         dispositivo, produtos, modulo, status, maquininha, cpf_consumidor)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'nfce_pendente',%s,%s)
        """,
        (
            venda_p["codigo"],
            venda_p["pagamento"],
            venda_p["realizada"],
            venda_p["empresa"],
            venda_p["valor_pago"],
            venda_p["data"],
            venda_p["hora"],
            venda_p["dispositivo"],
            venda_p["produtos"],
            venda_p["modulo"],
            venda_p["maquininha"],
            venda_p["cpf_consumidor"]
        )
    )

    # ===============================
    # REMOVER PRÉ-VENDA
    # ===============================
    executar_comando(
        "DELETE FROM vendas_ib_p WHERE id = %s",
        (venda_p_id,)
    )

    # ===============================
    # RECONSTRUIR PRODUTOS
    # ===============================
    produtos = []

    for item in venda_p["produtos"].split(","):
        pid, qtd = item.split(":")

        prod = executar_select(
            """
            SELECT nome, preco, unidade, tempo_servico
            FROM produtos_servicos
            WHERE id = %s
            """,
            (pid,)
        )[0]

        produtos.append({
            "nome": prod["nome"],
            "quantidade": int(qtd),
            "preco": float(prod["preco"]),
            "subtotal": float(prod["preco"]) * int(qtd),
            "unidade": prod.get("unidade"),
            "tempo_servico": prod.get("tempo_servico")
        })

    # ===============================
    # PÓS-PROCESSAMENTO REAL
    # ===============================
    pos_processar_venda(
        venda_id=venda_id,
        comercio=comercio,
        produtos=produtos,
        pagamento=venda_p["pagamento"],
        total=venda_p["valor_pago"],
        cpf=venda_p["cpf_consumidor"]
    )

    return {
        "ok": True,
        "venda_id": venda_id
    }
