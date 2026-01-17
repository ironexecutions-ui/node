from cryptography.fernet import Fernet
import os

CHAVE_CRIPTO = os.getenv("PIX_CRYPTO_KEY")

if not CHAVE_CRIPTO:
    raise RuntimeError("PIX_CRYPTO_KEY não definida")

fernet = Fernet(CHAVE_CRIPTO.encode())

def criptografar(texto: str) -> bytes:
    return fernet.encrypt(texto.encode())

def descriptografar(valor: bytes) -> str:
    return fernet.decrypt(valor).decode()
