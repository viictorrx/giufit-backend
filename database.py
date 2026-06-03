from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cria o arquivo do banco de dados chamado "giufit.db" na mesma pasta
SQLALCHEMY_DATABASE_URL = "sqlite:///./giufit.db"

# Motor que faz a conexão 
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Sessão do banco 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe base para criarmos nossas tabelas 
Base = declarative_base()