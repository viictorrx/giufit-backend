import logging
import os
import secrets
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("giufit")

# Cria as tabelas (e o arquivo giufit.db quando for SQLite local)
models.Base.metadata.create_all(bind=engine)

# ----------------------------------------------------
# CONFIGURAÇÃO (tudo vem de variáveis de ambiente)
# ----------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 12:
    raise RuntimeError(
        "Defina a variável de ambiente ADMIN_TOKEN com pelo menos 12 caracteres."
    )

# Lista separada por vírgula. Ex: https://giufit.vercel.app,http://localhost:5173
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="GiuFit API",
    description="API para catálogo de marmitas",
    docs_url=None if os.getenv("ENV") == "production" else "/docs",
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)  # aplica o limite padrão (120/min) em todas as rotas

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # nunca "*" aqui
    allow_credentials=False,  # usamos header Authorization, não cookies
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ----------------------------------------------------
# SCHEMAS (validação rigorosa de entrada)
# ----------------------------------------------------
class OpcaoTamanho(BaseModel):
    tamanho: str = Field(min_length=1, max_length=20)
    preco: float = Field(gt=0, lt=10000)


class PratoBase(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao: str = Field(default="", max_length=500)
    ativo: bool = True
    opcoes: List[OpcaoTamanho] = Field(min_length=1, max_length=10)


class PratoCreate(PratoBase):
    pass


class PratoUpdate(PratoBase):
    pass


# ----------------------------------------------------
# DEPENDÊNCIAS
# ----------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(request: Request, authorization: str = Header(default="")):
    """Exige 'Authorization: Bearer <ADMIN_TOKEN>' (comparação em tempo constante)."""
    esperado = f"Bearer {ADMIN_TOKEN}"
    if not secrets.compare_digest(authorization.encode(), esperado.encode()):
        log.warning("Acesso admin negado: ip=%s rota=%s", get_remote_address(request), request.url.path)
        raise HTTPException(status_code=401, detail="Não autorizado")


def _serializar(p: models.PratoDB) -> dict:
    return {
        "id": p.id,
        "nome": p.nome,
        "descricao": p.descricao,
        "ativo": p.ativo,
        "opcoes": [{"tamanho": o.tamanho, "preco": o.preco} for o in p.opcoes],
    }


# ----------------------------------------------------
# ROTAS PÚBLICAS
# ----------------------------------------------------
@app.get("/")
def home():
    return {"mensagem": "API da GiuFit rodando perfeitamente!"}


@app.get("/pratos")
def listar_pratos(db: Session = Depends(get_db)):
    """Lista as marmitas ativas (cardápio público)."""
    pratos = db.query(models.PratoDB).filter(models.PratoDB.ativo.is_(True)).all()
    return [_serializar(p) for p in pratos]


# ----------------------------------------------------
# ROTAS ADMIN (protegidas)
# ----------------------------------------------------
@app.post("/admin/login", status_code=204)
@limiter.limit("5/minute")
def admin_login(request: Request, authorization: str = Header(default="")):
    """Só confirma se o token está correto.

    A checagem é feita aqui dentro (e não como dependência) para que TODA
    tentativa, certa ou errada, conte no limite de 5/minuto contra força bruta.
    """
    require_admin(request, authorization)
    return None


@app.get("/admin/pratos", dependencies=[Depends(require_admin)])
def listar_todos(db: Session = Depends(get_db)):
    """Lista todas as marmitas, inclusive as inativas."""
    return [_serializar(p) for p in db.query(models.PratoDB).all()]


@app.post("/pratos", status_code=201, dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def criar_prato(request: Request, prato: PratoCreate, db: Session = Depends(get_db)):
    """Cadastra uma nova marmita (tudo numa única transação)."""
    try:
        novo = models.PratoDB(nome=prato.nome, descricao=prato.descricao, ativo=prato.ativo)
        novo.opcoes = [
            models.OpcaoTamanhoDB(tamanho=o.tamanho, preco=o.preco) for o in prato.opcoes
        ]
        db.add(novo)
        db.commit()
        db.refresh(novo)
    except Exception:
        db.rollback()
        log.exception("Erro ao criar prato")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar")
    log.info("Prato criado id=%s", novo.id)
    return {"mensagem": "Marmita cadastrada com sucesso!", "id_prato": novo.id}


@app.put("/pratos/{prato_id}", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def atualizar_prato(
    request: Request, prato_id: int, dados: PratoUpdate, db: Session = Depends(get_db)
):
    """Edita dados e preços de uma marmita (transação única com rollback)."""
    prato = db.query(models.PratoDB).filter(models.PratoDB.id == prato_id).first()
    if not prato:
        raise HTTPException(status_code=404, detail="Marmita não encontrada")
    try:
        prato.nome = dados.nome
        prato.descricao = dados.descricao
        prato.ativo = dados.ativo
        prato.opcoes = [
            models.OpcaoTamanhoDB(tamanho=o.tamanho, preco=o.preco) for o in dados.opcoes
        ]  # delete-orphan remove as antigas
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Erro ao atualizar prato id=%s", prato_id)
        raise HTTPException(status_code=500, detail="Erro interno ao salvar")
    log.info("Prato atualizado id=%s", prato_id)
    return {"mensagem": f"Marmita ID {prato_id} atualizada com sucesso!"}


@app.delete("/pratos/{prato_id}", dependencies=[Depends(require_admin)])
@limiter.limit("30/minute")
def deletar_prato(request: Request, prato_id: int, db: Session = Depends(get_db)):
    """Exclui uma marmita e seus tamanhos."""
    prato = db.query(models.PratoDB).filter(models.PratoDB.id == prato_id).first()
    if not prato:
        raise HTTPException(status_code=404, detail="Marmita não encontrada")
    try:
        db.delete(prato)  # cascade remove os tamanhos
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Erro ao excluir prato id=%s", prato_id)
        raise HTTPException(status_code=500, detail="Erro interno ao excluir")
    log.info("Prato excluído id=%s", prato_id)
    return {"mensagem": f"Marmita ID {prato_id} excluída com sucesso!"}
