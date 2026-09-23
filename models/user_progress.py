# backend/models/user_progress.py

from sqlalchemy import Column, String, Integer, DateTime, func
from db import Base

class UserProgress(Base):
    __tablename__ = "user_progress"

    user_id = Column(String, primary_key=True, index=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
