# backend/models/evaluation.py
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from datetime import datetime
from db import Base

class Evaluation(Base):
    __tablename__ = "evaluation"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    source_text = Column(String)
    chosen_id = Column(String)
    adequacy = Column(Integer, nullable=True)
    fluency = Column(Integer, nullable=True)
    was_correct = Column(Boolean, default=None)  # NEW
    timestamp = Column(DateTime, default=datetime.utcnow)
