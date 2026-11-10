from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
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


class OpcaoTamanhoDB(Base):
    __tablename__ = "opcoes_tamanho"

    id = Column(Integer, primary_key=True, index=True)
    tamanho = Column(String)  # Ex: "250g", "350g"
    preco = Column(Float)
    
    # Chave estrangeira ligando esse tamanho a um prato específico
    prato_id = Column(Integer, ForeignKey("pratos.id"))
    
    # Relacionamento reverso
    prato = relationship("PratoDB", back_populates="opcoes")