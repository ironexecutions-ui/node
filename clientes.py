from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import executar_select
from .auth import verificar_token

router = APIRouter(prefix="/clientes")


class ClienteMe(BaseModel):
    id: int
    nome_completo: str
    cargo: str
    funcao: str
    codigo: str
    qrcode: str
    comercio_id: int | None = None
    modulos: dict | None = None
    node: int  # 🔥 vem de comercios_cadastradas


@router.get("/me")
async def get_me(usuario=Depends(verificar_token)):
    dados = executar_select(
        """
        SELECT 
            c.id,
            c.nome_completo,
            c.cargo,
            c.funcao,
            c.codigo,
            c.qrcode,
            c.comercio_id,
            COALESCE(cc.node, 0) AS node
        FROM clientes c
        LEFT JOIN comercios_cadastradas cc ON cc.id = c.comercio_id
        WHERE c.id = %s
        LIMIT 1
        """,
        (usuario["id"],)
    )

    if not dados:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    cliente = dados[0]

    modulos = None

    if cliente["comercio_id"]:
        lista = executar_select(
            """
            SELECT 
                produtividade,
                administracao,
                delivery_vendas,
                mesas_salao_cozinha,
                integracao_ifood,
                agendamentos,
                gerencial,
                fiscal
            FROM comercios_cadastradas
            WHERE id = %s
            """,
            (cliente["comercio_id"],)
        )

        if lista:
            modulos = lista[0]

    return {
        "id": cliente["id"],
        "nome_completo": cliente["nome_completo"],
        "cargo": cliente["cargo"],
        "funcao": cliente["funcao"],
        "codigo": cliente["codigo"],
        "qrcode": cliente["qrcode"],
        "comercio_id": cliente["comercio_id"],
        "modulos": modulos,
        "node": int(cliente["node"])  # 🔒 sempre 0 ou 1
    }


@router.get("/modulo")
def listar_modulos():
    return executar_select("SELECT * FROM modulos WHERE ativo = 1")
