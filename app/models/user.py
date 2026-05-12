from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role          = Column(String(20), default="viewer")   # admin | viewer
    email         = Column(String(150))
    created_at    = Column(DateTime, default=datetime.utcnow)

    logs = relationship("ActivityLog", back_populates="user")
