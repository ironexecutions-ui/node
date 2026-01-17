from fastapi import APIRouter, HTTPException, Query
from database import executar_select
from datetime import datetime

router = APIRouter()


# --------------------------------------------------------------
# ROTAS DE DESEMPENHO
# --------------------------------------------------------------

# --------------------------------------------------------------
# ROTA 1: MAIORES E MENORES VENDIDOS
# --------------------------------------------------------------
@router.get("/desempenho/maiores-menores")
def maiores_menores(
    data: str = Query(..., description="Data no formato YYYY-MM-DD"),
    limite: int = Query(5, description="Quantidade de produtos desejados")
):
    try:
        data_inicio = datetime.strptime(data, "%Y-%m-%d")
        data_fim = datetime.now()
    except:
        raise HTTPException(status_code=400, detail="Formato de data inválido")

    vendas = executar_select(
        """
        SELECT 
            vi.produto_id,
            p.nome AS nome_produto,
            SUM(vi.quantidade) AS total_vendido
        FROM vendas_itens vi
        JOIN produtos p ON p.id = vi.produto_id
        WHERE vi.data_hora BETWEEN %s AND %s
        GROUP BY vi.produto_id, p.nome
        ORDER BY total_vendido DESC
        """,
        (data_inicio, data_fim)
    )

    if not vendas:
        return {"maiores": [], "menores": []}

    maiores = sorted(vendas, key=lambda x: x["total_vendido"], reverse=True)[:limite]
    menores = sorted(vendas, key=lambda x: x["total_vendido"])[:limite]

    return {
        "maiores": maiores,
        "menores": menores
    }
@router.get("/desempenho/historico")
def historico_vendas(
    pagina: int = Query(1),
    limite: int = Query(7)
):
    offset = (pagina - 1) * limite

    # Busca as vendas desejadas
    vendas = executar_select(
        """
        SELECT 
            v.venda_numero,
            v.usuario_nome,
            v.data_hora,
            SUM(v.preco_pago) AS total_venda
        FROM vendas_itens v
        GROUP BY v.venda_numero, v.usuario_nome, v.data_hora
        ORDER BY v.venda_numero DESC
        LIMIT %s OFFSET %s
        """,
        (limite, offset)
    )

    if not vendas:
        return {"historico": []}

    # Extrai apenas os números das vendas que serão exibidas
    ids = tuple([v["venda_numero"] for v in vendas])

    # Previne erro se só houver uma venda
    if len(ids) == 1:
        ids = f"({ids[0]})"

    # Busca itens de todas as vendas selecionadas de uma vez só
    itens = executar_select(
        f"""
        SELECT 
            v.venda_numero,
            p.nome AS nome_produto,
            v.quantidade,
            v.preco_pago
        FROM vendas_itens v
        JOIN produtos p ON p.id = v.produto_id
        WHERE v.venda_numero IN {ids}
        ORDER BY v.venda_numero DESC
        """
    )

    resultado = []

    for venda in vendas:
        venda_itens = [i for i in itens if i["venda_numero"] == venda["venda_numero"]]

        resultado.append({
            "venda_numero": venda["venda_numero"],
            "usuario_nome": venda["usuario_nome"],
            "data_hora": venda["data_hora"].strftime("%Y-%m-%d %H:%M:%S"),
            "total_venda": float(venda["total_venda"]),
            "itens": venda_itens
        })

    return {"historico": resultado}

@router.get("/desempenho/graficos")
def graficos():

    # últimos 7 dias
    dias = executar_select(
        """
        SELECT 
            DATE(vi.data_hora) AS label,
            SUM(vi.preco_pago) AS total
        FROM vendas_itens vi
        WHERE vi.data_hora >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(vi.data_hora)
        ORDER BY DATE(vi.data_hora)
        """
    )

    # últimas 7 semanas (formato Ano-Semana)
    semanas = executar_select(
        """
        SELECT 
            DATE_FORMAT(vi.data_hora, '%x-%v') AS label,
            SUM(vi.preco_pago) AS total
        FROM vendas_itens vi
        GROUP BY DATE_FORMAT(vi.data_hora, '%x-%v')
        ORDER BY DATE_FORMAT(vi.data_hora, '%x-%v') DESC
        LIMIT 7
        """
    )

    # últimos 7 meses
    meses = executar_select(
        """
        SELECT 
            DATE_FORMAT(vi.data_hora, '%Y-%m') AS label,
            SUM(vi.preco_pago) AS total
        FROM vendas_itens vi
        GROUP BY DATE_FORMAT(vi.data_hora, '%Y-%m')
        ORDER BY DATE_FORMAT(vi.data_hora, '%Y-%m') DESC
        LIMIT 7
        """
    )

    return {
        "dias": dias,
        "semanas": semanas[::-1],  # mais antigo -> mais novo
        "meses": meses[::-1]
    }
