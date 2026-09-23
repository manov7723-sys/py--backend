# setup_db.py
from db import Base, engine
from models.evaluation import Evaluation
from models.user_progress import UserProgress
print('delete tabe')
Base.metadata.drop_all(bind=engine) 
print("📦 Creating tables...")
Base.metadata.create_all(bind=engine)
print("✅ Done.")
