import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./simcard.db")

# Railway sends postgres:// — SQLAlchemy 2.x needs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import simcard, user  # noqa
    Base.metadata.create_all(bind=engine)
    _seed_admin()


def _seed_admin():
    from app.models.user import User
    from passlib.context import CryptContext
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin = User(
                username="admin",
                password_hash=pwd_ctx.hash("admin1234"),
                role="admin",
                email="admin@karndiy.com",
            )
            db.add(admin)
            db.commit()
            print("Default admin created (admin / admin1234)")
    finally:
        db.close()
