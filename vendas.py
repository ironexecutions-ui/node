from fastapi import APIRouter, HTTPException
import requests
from datetime import datetime

router = APIRouter()


def log(msg):
    print(f"[LOCAL][{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ===============================
# ROTA ÚNICA: IMPRIMIR COMANDA
# ===============================
@router.post("/imprimir")
def imprimir_comanda(dados: dict):
    """
    Espera receber:
    {
        "venda_id": 123,
        "url": "https://link-do-pdf"
    }
    """

    venda_id = dados.get("venda_id")
    url = dados.get("url")

    if not venda_id:
        raise HTTPException(status_code=400, detail="venda_id não informado")

    if not url:
        raise HTTPException(status_code=400, detail="URL do PDF não informada")

    try:
        log(f"Recebida solicitação de impressão da venda {venda_id}")
        log(f"URL: {url}")

        resp = requests.post(
            "http://localhost:3334/print",
            json={"url": url},
            timeout=10
        )

        if resp.status_code != 200:
            raise Exception(f"Printer retornou {resp.status_code}")

        log("Comanda enviada para a impressora com sucesso")

        return {
            "ok": True,
            "venda_id": venda_id,
            "mensagem": "Comanda impressa com sucesso"
        }

    except Exception as e:
        log(f"Erro ao imprimir venda {venda_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Falha ao enviar para a impressora"
        )


# ===============================
# HEALTH CHECK
# ===============================
@router.get("/health")
def health():
    return {
        "ok": True,
        "service": "local-api"
    }
