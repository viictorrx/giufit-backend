from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from database import engine, SessionLocal
import models
from fastapi.middleware.cors import CORSMiddleware

# Cria o arquivo giufit.db e as tabelas!
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="GiuFit API", description="API para catálogo de marmitas")

# Configuração do CORS para o React conseguir acessar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# SCHEMAS (Modelos de validação de dados)
# ----------------------------------------------------
class OpcaoTamanho(BaseModel):
    tamanho: str  
    preco: float  

class PratoCreate(BaseModel):
    nome: str
    descricao: str
    ativo: bool = True
    opcoes: List[OpcaoTamanho]

class PratoUpdate(BaseModel):
    nome: str
    descricao: str
    ativo: bool = True
    opcoes: List[OpcaoTamanho]

# ----------------------------------------------------
# FUNÇÃO PARA CONEXÃO COM O BANCO (Colocada antes das rotas!)
# ----------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------
# ROTAS DA API
# ----------------------------------------------------
@app.get("/")
def home():
    return {"mensagem": "API da GiuFit rodando perfeitamente!"}

@app.post("/pratos")
def criar_prato(prato: PratoCreate, db: Session = Depends(get_db)):
    """Rota para CADASTRAR uma nova marmita"""
    novo_prato = models.PratoDB(
        nome=prato.nome, 
        descricao=prato.descricao, 
        ativo=prato.ativo
    )
    db.add(novo_prato)
    db.commit()
    db.refresh(novo_prato)

    for opcao in prato.opcoes:
        novo_tamanho = models.OpcaoTamanhoDB(
            tamanho=opcao.tamanho, 
            preco=opcao.preco, 
            prato_id=novo_prato.id
        )
        db.add(novo_tamanho)
    
    db.commit()
    return {"mensagem": "Marmita cadastrada com sucesso!", "id_prato": novo_prato.id}

@app.get("/pratos")
def listar_pratos(db: Session = Depends(get_db)):
    """Rota para LISTAR todas as marmitas"""
    pratos = db.query(models.PratoDB).all()
    resultado = []
    
    for p in pratos:
        resultado.append({
            "id": p.id,
            "nome": p.nome,
            "descricao": p.descricao,
            "ativo": p.ativo,
            "opcoes": [{"tamanho": o.tamanho, "preco": o.preco} for o in p.opcoes]
        })
    return resultado

@app.put("/pratos/{prato_id}")
def atualizar_prato(prato_id: int, prato_atualizado: PratoUpdate, db: Session = Depends(get_db)):
    """Rota para EDITAR os dados e os PREÇOS de uma marmita"""
    prato_existente = db.query(models.PratoDB).filter(models.PratoDB.id == prato_id).first()
    
    if not prato_existente:
        raise HTTPException(status_code=404, detail="Marmita não encontrada")
    
    # 1. Atualiza os dados principais
    prato_existente.nome = prato_atualizado.nome
    prato_existente.descricao = prato_atualizado.descricao
    prato_existente.ativo = prato_atualizado.ativo
    
    # 2. Atualiza os tamanhos (Apaga os antigos e cria os novos com os preços atualizados)
    db.query(models.OpcaoTamanhoDB).filter(models.OpcaoTamanhoDB.prato_id == prato_id).delete()
    for opcao in prato_atualizado.opcoes:
        novo_tamanho = models.OpcaoTamanhoDB(
            tamanho=opcao.tamanho, 
            preco=opcao.preco, 
            prato_id=prato_id
        )
        db.add(novo_tamanho)
    
    db.commit()
    return {"mensagem": f"Marmita ID {prato_id} atualizada com sucesso!"}

@app.delete("/pratos/{prato_id}")
def deletar_prato(prato_id: int, db: Session = Depends(get_db)):
    """Rota para EXCLUIR uma marmita e seus tamanhos associados"""
    prato = db.query(models.PratoDB).filter(models.PratoDB.id == prato_id).first()
    
    if not prato:
        raise HTTPException(status_code=404, detail="Marmita não encontrada")
    
    # 1. Remove primeiro os tamanhos atrelados a essa marmita
    db.query(models.OpcaoTamanhoDB).filter(models.OpcaoTamanhoDB.prato_id == prato_id).delete()
    
    # 2. Remove o prato principal
    db.delete(prato)
    db.commit()
    
    return {"mensagem": f"Marmita ID {prato_id} excluída com sucesso!"}