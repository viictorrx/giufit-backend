import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Puxa o link da nuvem (Variável de Ambiente). Se não achar, usa o SQLite local
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./giufit.db")

# O SQLite precisa do "check_same_thread", mas o PostgreSQL não.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Sessão do banco 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe base para criarmos nossas tabelas 
Base = declarative_base()