from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class SimStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    expired = "expired"


class SimCard(Base):
    __tablename__ = "simcards"

    id              = Column(Integer, primary_key=True, index=True)
    iccid           = Column(String(22), unique=True, nullable=False, index=True)
    phone_number    = Column(String(20), nullable=False)
    carrier         = Column(String(100), nullable=False)
    status          = Column(String(20), default="active", nullable=False)
    plan            = Column(String(150))
    assigned_to     = Column(String(150))
    department      = Column(String(150))
    activation_date = Column(Date, default=date.today)
    expiry_date     = Column(Date)
    monthly_cost    = Column(Numeric(10, 2), default=0)
    notes           = Column(Text)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs = relationship("ActivityLog", back_populates="simcard", cascade="all, delete-orphan")

    @property
    def days_until_expiry(self):
        if self.expiry_date:
            delta = self.expiry_date - date.today()
            return delta.days
        return None

    @property
    def expiry_status(self):
        days = self.days_until_expiry
        if days is None:
            return "none"
        if days < 0:
            return "expired"
        if days <= 7:
            return "critical"
        if days <= 30:
            return "warning"
        return "ok"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    sim_id     = Column(Integer, ForeignKey("simcards.id", ondelete="SET NULL"), nullable=True)
    action     = Column(String(200), nullable=False)
    detail     = Column(Text)
    timestamp  = Column(DateTime, default=datetime.utcnow)

    simcard = relationship("SimCard", back_populates="logs")
    user    = relationship("User", back_populates="logs")


class Budget(Base):
    __tablename__ = "budgets"

    id             = Column(Integer, primary_key=True, index=True)
    department     = Column(String(150), unique=True, nullable=False)
    monthly_budget = Column(Numeric(10, 2), default=0)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
