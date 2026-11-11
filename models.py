from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String,
)
from sqlalchemy.orm import deferred, relationship
from database import Base

class PratoDB(Base):
    __tablename__ = "pratos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    descricao = Column(String)
    ativo = Column(Boolean, default=True)
    
    # Isso faz a ligação (Relacionamento) com a tabela de tamanhos
    opcoes = relationship(
        "OpcaoTamanhoDB", back_populates="prato", cascade="all, delete-orphan"
    )

    # Foto do prato (tabela separada: assim não precisa alterar a tabela "pratos")
    foto = relationship(
        "FotoPratoDB",
        back_populates="prato",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )


class OpcaoTamanhoDB(Base):
    __tablename__ = "opcoes_tamanho"

    id = Column(Integer, primary_key=True, index=True)
    tamanho = Column(String)  # Ex: "250g", "350g"
    preco = Column(Float)
    
    # Chave estrangeira ligando esse tamanho a um prato específico
    prato_id = Column(Integer, ForeignKey("pratos.id"))
    
    # Relacionamento reverso
    prato = relationship("PratoDB", back_populates="opcoes")


class FotoPratoDB(Base):
    __tablename__ = "fotos_prato"

    prato_id = Column(Integer, ForeignKey("pratos.id"), primary_key=True)
    tipo = Column(String(20), nullable=False)  # image/jpeg, image/png, image/webp
    # deferred: a listagem do cardápio NÃO carrega os bytes da imagem
    conteudo = deferred(Column(LargeBinary, nullable=False))
    atualizado_em = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    prato = relationship("PratoDB", back_populates="foto")
