from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    quota_bytes = Column(BigInteger, default=52428800) # 50 MB default
    used_bytes = Column(BigInteger, default=0)

class Game(Base):
    __tablename__ = "games"
    id = Column(String, primary_key=True, index=True) # e.g. ULUS10566
    title = Column(String)

class Save(Base):
    __tablename__ = "saves"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_id = Column(String, ForeignKey("games.id"))
    version = Column(Integer, default=1)
    file_hash = Column(String) # MD5 or SHA256 of the zip
    file_path = Column(String)
    file_size = Column(BigInteger)
    updated_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
