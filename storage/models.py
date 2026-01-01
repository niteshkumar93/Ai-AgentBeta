from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from .database import Base

class Baseline(Base):
    __tablename__ = "baselines"

    id = Column(Integer, primary_key=True)
    project = Column(String, index=True)
    label = Column(String, nullable=True)
    platform = Column(String)  # "provar" | "automation_api"
    data = Column(Text)        # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
