import mysql.connector
import requests
from cryptography.fernet import Fernet

# =========================
# CONFIG
# =========================
USAR_ONLINE = True

BACKEND_URL = "https://ironexecutions-backend.onrender.com"
ROTA_DADOS = "/seguranca/dados-conexao"

# Token válido do sistema (login feito antes)
TOKEN_SISTEMA = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0aXBvIjoic2lzdGVtYSIsIm5vbWUiOiJwZHYtbG9jYWwiLCJleHAiOjE4MDAxNTA3Nzl9.rhj4B1zIP30Br1EhIINlYZ4YaBkwTTYv7ih9_yDoxh4"

# =========================
# CHAVE DE CRIPTOGRAFIA
# =========================
CHAVE = b"GLGL8PCeYjSUmd1vazugbSSgAHeV_S1yJTBxMzuLqZc="

# =========================
# FALLBACK LOCAL (offline)
# =========================
DADOS_LOCAL = b"gAAAAABpauDXajlZ1XCd6xXTSWgHxnbdtNwnjKmYxvVgvrzaM2PJaWPAg48NJyAO4L_OgXZxq0NV2a_Wv2Rzo-FhLEDoNzhnNSB5ay_hFsMWId-Pbj7Lnr9R6Agintharf4vPTVRQFXP"

# =========================
# BUSCAR DADOS DO BACKEND
# =========================
def _buscar_dados_online():
    if not TOKEN_SISTEMA:
        raise Exception("Token do sistema não definido")

    resp = requests.get(
        BACKEND_URL + ROTA_DADOS,
        headers={
            "Authorization": f"Bearer {TOKEN_SISTEMA}"
        },
        timeout=10
    )

    if resp.status_code != 200:
        raise Exception("Não autorizado pelo servidor")

    return resp.json()["dados"].encode()

# =========================
# FUNÇÃO INTERNA DE CONFIG
# =========================
def _obter_config():
    f = Fernet(CHAVE)

    if USAR_ONLINE:
        dados_criptografados = _buscar_dados_online()
    else:
        dados_criptografados = DADOS_LOCAL

    texto = f.decrypt(dados_criptografados).decode()
    host, user, password, database, port = texto.split("|")

    return {
        "host": host,
        "user": user,
        "password": password,
        "database": database,
        "port": int(port)
    }

# =========================
# CONEXÃO CENTRAL
# =========================
def conectar():
    return mysql.connector.connect(**_obter_config())

# =========================
# HELPERS
# =========================
def executar_select(query, params=None):
    conn = conectar()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    dados = cursor.fetchall()
    cursor.close()
    conn.close()
    return dados

def executar_comando(query, params=None):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    cursor.close()
    conn.close()

def executar_insert(query, params=None):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    row_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return row_id
