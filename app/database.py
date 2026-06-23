from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

import os

# LOAD ENV
load_dotenv()

# POSTGRESQL CONFIG
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_DB = os.getenv("PG_DB")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")

# CUSTOM SCHEMA
DB_SCHEMA = "mechanics_db_schema"

# DATABASE URL
DATABASE_URL = (
    f"postgresql://{PG_USER}:{PG_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# ENGINE
engine = create_engine(

    DATABASE_URL,

    connect_args={
        "options": f"-csearch_path={DB_SCHEMA}"
    },

    pool_pre_ping=True,
)

# SESSION
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# BASE
Base = declarative_base()


# DATABASE DEPENDENCY
def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()