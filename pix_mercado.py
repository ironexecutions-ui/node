import mercadopago
from fastapi import APIRouter, Depends, HTTPException
from database import executar_select
from crypto import descriptografar
from auth_clientes import verificar_token_cliente
from pydantic import BaseModel

router = APIRouter(prefix="/vendas/pix", tags=["Pix"])


class PixGerarBody(BaseModel):
    valor: float


# ===============================
# GERAR PIX
# ===============================
@router.post("/gerar")
def gerar_pix(dados: PixGerarBody, usuario=Depends(verificar_token_cliente)):

    usuario_id = usuario["id"]

    comercio = executar_select(
        """
        SELECT c.id, c.mercado
        FROM clientes cl
        JOIN comercios_cadastradas c ON c.id = cl.comercio_id
        WHERE cl.id = %s
        LIMIT 1
        """,
        (usuario_id,)
    )

    if not comercio:
        raise HTTPException(403, "Usuário sem comércio vinculado")

    comercio_id = comercio[0]["id"]
    mercado = comercio[0]["mercado"]

    # ===============================
    # PIX LOCAL (SEM MERCADO PAGO)
    # ===============================
    if mercado == 0:
        return {
            "tipo": "pix_local",
            "mensagem": "Pix local confirmado no caixa"
        }

    # ===============================
    # PIX MERCADO PAGO
    # ===============================
    r = executar_select(
        """
        SELECT access_token
        FROM pix_caixa
        WHERE comercio_id = %s
        LIMIT 1
        """,
        (comercio_id,)
    )

    if not r:
        raise HTTPException(403, "Pix Mercado Pago não configurado")

    access_token = descriptografar(r[0]["access_token"])
    sdk = mercadopago.SDK(access_token)

    pagamento = sdk.payment().create({
        "transaction_amount": float(dados.valor),
        "payment_method_id": "pix",
        "description": "Venda no caixa",
        "payer": {"email": "cliente@local.com"}
    })

    if pagamento.get("status") != 201:
        raise HTTPException(500, "Erro ao gerar Pix")

    mp = pagamento["response"]

    return {
        "tipo": "pix_mp",
        "id": mp["id"],
        "qr_code": mp["point_of_interaction"]["transaction_data"]["qr_code"],
        "qr_code_base64": mp["point_of_interaction"]["transaction_data"]["qr_code_base64"]
    }


# ===============================
# STATUS PIX (SÓ MERCADO PAGO)
# ===============================
@router.get("/status/{payment_id}")
def status_pix(payment_id: int, usuario=Depends(verificar_token_cliente)):

    usuario_id = usuario["id"]

    comercio = executar_select(
        """
        SELECT c.id, c.mercado
        FROM clientes cl
        JOIN comercios_cadastradas c ON c.id = cl.comercio_id
        WHERE cl.id = %s
        LIMIT 1
        """,
        (usuario_id,)
    )

    if not comercio:
        raise HTTPException(403, "Usuário sem comércio")

    # Pix local nunca consulta status
    if comercio[0]["mercado"] == 0:
        return {"status": "approved"}

    comercio_id = comercio[0]["id"]

    r = executar_select(
        """
        SELECT access_token
        FROM pix_caixa
        WHERE comercio_id = %s
        LIMIT 1
        """,
        (comercio_id,)
    )

    if not r:
        return {"status": "pending"}

    access_token = descriptografar(r[0]["access_token"])
    sdk = mercadopago.SDK(access_token)

    mp = sdk.payment().get(payment_id)
    status_mp = mp.get("response", {}).get("status")

    if status_mp == "approved":
        return {"status": "approved"}

    return {"status": "pending"}
