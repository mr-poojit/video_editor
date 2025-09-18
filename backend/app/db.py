# backend/app/db.py
from sqlmodel import create_engine, SQLModel, Session
import os

DB_FILE = os.environ.get("DB_FILE", "sqlite:///./jobs.db")
engine = create_engine(DB_FILE, echo=False, connect_args={"check_same_thread": False} if DB_FILE.startswith("sqlite") else {})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
