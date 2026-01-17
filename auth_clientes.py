from fastapi import Request, HTTPException
import jwt

CHAVE = "ironexecutions_super_secreto_2025"

async def verificar_token_cliente(request: Request):

    auth_header = request.headers.get("authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Token não enviado")

    try:
        tipo, token = auth_header.split()

        if tipo.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")

        payload = jwt.decode(token, CHAVE, algorithms=["HS256"])

        # ===============================
        # VALIDAÇÃO SEGURA DO PAYLOAD
        # ===============================
        # Não altera o token
        # Não cria dados
        # Apenas garante que o backend não quebre
        campos_obrigatorios = ["id", "funcao"]

        for campo in campos_obrigatorios:
            if campo not in payload:
                raise HTTPException(
                    status_code=401,
                    detail=f"Token inválido: campo '{campo}' ausente"
                )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")

    except HTTPException:
        raise

    except Exception as e:
        print("ERRO JWT:", str(e))
        raise HTTPException(status_code=401, detail="Token inválido")
