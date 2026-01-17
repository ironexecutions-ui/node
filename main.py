from dotenv import load_dotenv
import os

load_dotenv()


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import executar_select, executar_comando
from vendas import router as vendas_router  # IMPORTA AQUI
from pix_mercado import router as v_router  # IMPORTA AQUI

app = FastAPI()

origins = [
    "*",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://alexsia-utilidades-8x70.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# REGISTRA AS ROTAS DE VENDAS
app.include_router(vendas_router)
app.include_router(v_router)

@app.get("/")
def raiz():
    return {"status": "API está funcionando"}

@app.get("/teste")
def teste():
    return {"mensagem": "Backend conectado com sucesso"}
