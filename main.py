#backend/main.py
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict
import csv
import io
from fastapi.responses import StreamingResponse
from db import SessionLocal
from logic import scoring
from models.user_progress import UserProgress
import json
from fastapi.responses import JSONResponse
from sqlalchemy import func
from fastapi.responses import JSONResponse
from fastapi import APIRouter
import random, json
from mistral_generate import mistral_translate
from models.evaluation import Evaluation
from db import SessionLocal
from fastapi import Request



# --------- App Setup ---------
app = FastAPI(title="Translation Evaluation API")

# Allow frontend from Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://frontend-five-lime-38.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- DB Dependency ---------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------- Pydantic Models ---------
class EvaluationInput(BaseModel):
    user_id: str = Field(..., example="anon_001")
    translation_id: str = Field(..., example="text_001")
    user: Dict[str, int] = Field(..., example={"adequacy": 85, "fluency": 90})
    expert: Dict[str, int] = Field(..., example={"adequacy": 88, "fluency": 92})
    comment: str = Field("", example="Some feedback")

class EvaluationOutput(BaseModel):
    result: Dict

# --------- Evaluation Endpoint ---------
@app.get("/admin/init-db")
def init_db_endpoint():
    from db import Base, engine
    Base.metadata.create_all(bind=engine)
    return {"status": "✅ Tables initialized"}

@app.post("/evaluate", response_model=EvaluationOutput)
def evaluate_translation(data: EvaluationInput, db: Session = Depends(get_db)):
    result = scoring.compare_scores(data.user, data.expert, data.translation_id)


    # Save evaluation to DB
    eval_record = Evaluation(
        user_id=data.user_id,
        translation_id=data.translation_id,
        adequacy=data.user["adequacy"],
        fluency=data.user["fluency"],
        comment=data.comment,
        adequacy_xp=result["adequacy"]["xp"],
        fluency_xp=result["fluency"]["xp"],
        total_xp=result["total"]["xp_awarded"],
        percentage=result["total"]["percentage"]
    )

    db.add(eval_record)

    # Update or insert user XP progress
    xp_gained = result["total"]["xp_awarded"]
    user = db.query(UserProgress).filter_by(user_id=data.user_id).first()

    if user:
        user.xp += xp_gained
        user.level = (user.xp // 500) + 1
    else:
        user = UserProgress(
            user_id=data.user_id,
            xp=xp_gained,
            level=(xp_gained // 500) + 1
        )
        db.add(user)

    db.commit()

    return {"result": result}

#----------- debug route for eval---------
@app.get("/admin/check-evals")
def check_evals(db: Session = Depends(get_db)):
    count = db.query(Evaluation).count()
    return {"message": f"Evaluation rows in DB: {count}"}

# --------- Get Translations Endpoint ---------
@app.get("/data/translations")
def get_translations():
    file_path = os.path.join("..", "datasets", "en_ca_translations.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(content=data)
# --------- Admin: Get All Evaluations ---------
@app.get("/admin/evaluations")
def get_all_evaluations(db: Session = Depends(get_db)):
    evaluations = db.query(Evaluation).all()

    result = []
    for e in evaluations:
        result.append({
            "user_id": e.user_id,
            "source_text": e.source_text,
            "chosen_id": e.chosen_id,
            "adequacy": e.adequacy,
            "fluency": e.fluency,
            "was_correct": getattr(e, "was_correct", None),
            "timestamp": e.timestamp.isoformat()
        })

    return JSONResponse(content=result)

from fastapi.responses import StreamingResponse

@app.get("/admin/export/csv")
def export_evaluations_csv(db: Session = Depends(get_db)):
    try:
        evaluations = db.query(Evaluation).all()

        # Create in-memory CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "user_id", "translation_id","was_correct",
            "adequacy", "fluency",
            "timestamp"
        ])

        # Data rows
        for e in evaluations:
            writer.writerow([
                e.user_id,
                e.chosen_id,
                getattr(e, "was_correct", ""),
                getattr(e, "adequacy", ""),
                getattr(e, "fluency", ""),
                e.timestamp.isoformat() if e.timestamp else ""
            ])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=evaluations.csv"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# --------- Admin: Generate Reference Scores ---------
@app.get("/admin/generate-reference-scores")
def generate_reference_scores(db: Session = Depends(get_db)):
    # Get average scores grouped by translation_id
    results = (
        db.query(
            Evaluation.chosen_id ,
            func.avg(Evaluation.adequacy).label("avg_adequacy"),
            func.avg(Evaluation.fluency).label("avg_fluency")
        )
        .group_by(Evaluation.chosen_id )
        .all()
    )

    output = {
    item.chosen_id: {
        "adequacy": float(item.avg_adequacy),
        "fluency": float(item.avg_fluency)
    }
    for item in results
}



    output_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "expert_scores.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:

        json.dump(output, f, indent=2, ensure_ascii=False)

    return JSONResponse(content={"message": f"✅ Saved {len(output)} expert scores."})

@app.post("/translation-duel/submit")
async def submit_translation_duel(request: Request):
    """
    Save user feedback (adequacy, fluency) for both correct and incorrect answers.
    """
    data = await request.json()
    db = SessionLocal()

    user_id = data.get("user_id")
    source = data.get("source")
    chosen_id = data.get("chosen_id")
    adequacy = data.get("adequacy")
    fluency = data.get("fluency")
    correct_id = data.get("correct_id")  # <-- required for correctness check

    was_correct = chosen_id == correct_id

    # Load expert consensus if exists
    reference_path = os.path.join("datasets", "expert_scores.json")
    baseline = None
    if os.path.exists(reference_path):
        with open(reference_path, "r", encoding="utf-8") as f:
            consensus = json.load(f)
        baseline = consensus.get(chosen_id)

    if was_correct:
        if baseline:
            diff_adequacy = abs(baseline["adequacy"] - adequacy)
            diff_fluency = abs(baseline["fluency"] - fluency)
            bonus_adequacy = max(5 - diff_adequacy, 0)
            bonus_fluency = max(5 - diff_fluency, 0)
        else:
            bonus_adequacy = 5
            bonus_fluency = 5
    else:
        bonus_adequacy = 0
        bonus_fluency = 0

    total_bonus = bonus_adequacy + bonus_fluency

    # Save to DB regardless of correctness
    evaluation = Evaluation(
        user_id=user_id,
        source_text=source,
        chosen_id=chosen_id,
        adequacy=adequacy,
        fluency=fluency,
        was_correct=was_correct,
    )
    db.add(evaluation)

    # Update XP only if any bonus
    user = db.query(UserProgress).filter_by(user_id=user_id).first()
    if user:
        user.xp += total_bonus
        user.level = (user.xp // 100) + 1
    else:
        user = UserProgress(
            user_id=user_id,
            xp=total_bonus,
            level=(total_bonus // 100) + 1
        )
        db.add(user)

    db.commit()
    db.close()

    return {
        "bonus": {
            "adequacy": bonus_adequacy,
            "fluency": bonus_fluency,
            "total": total_bonus,
        }
    }

@app.get("/translation-duel")
def get_translation_duel():
    DATASET_PATH = os.path.join(os.path.dirname(__file__), "en_ca_translations.json")

    # Load dataset
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    # Pick a random entry
    # Filter only full-sentence pairs (heuristic: ends with . or ? or !)
    valid_pairs = [p for p in dataset if p["source"].strip().endswith(('.', '?', '!')) and p["target"].strip().endswith(('.', '?', '!'))]
    pair = random.choice(valid_pairs)


    mistral_output = mistral_translate(pair["source"])

    human_option = {"id": f"{pair['id']}_human", "text": pair["target"]}
    mistral_option = {"id": f"{pair['id']}_mistral", "text": mistral_output}

    options = [human_option, mistral_option]
    random.shuffle(options)

    return {
        "source": pair["source"],
        "options": options,
        "correct_id": human_option["id"]  # Send the correct one explicitly
    }

@app.post("/submit-evaluation")
async def submit_evaluation(request: Request):
    data = await request.json()
    db = SessionLocal()

    adequacy = data.get("adequacy", 0)
    fluency = data.get("fluency", 0)

    chosen_id = data.get("chosen_id")
    is_human = "_human" in chosen_id
    was_correct = is_human  # Determines if player selected the human translation

    # Add a flat bonus if the user was incorrect
    flat_bonus = 5 if not was_correct else 0

    # Adjust XP calculation based on correctness
    if was_correct:
        adequacy_xp = adequacy * 2
        fluency_xp = fluency * 2
    else:
        adequacy_xp = 0
        fluency_xp = 0

    total_xp = adequacy_xp + fluency_xp + flat_bonus  

    # Save the evaluation regardless of correctness
    evaluation = Evaluation(
        user_id=data["user_id"],
        source_text=data["source"],
        chosen_id=chosen_id,
        adequacy=adequacy,
        fluency=fluency,
        was_correct=was_correct,
    )
    db.add(evaluation)

    # Update or create user progress
    user = db.query(UserProgress).filter_by(user_id=data["user_id"]).first()
    if user:
        user.xp += total_xp
        user.level = (user.xp // 100) + 1
    else:
        user = UserProgress(
            user_id=data["user_id"],
            xp=total_xp,
            level=(total_xp // 100) + 1
        )
        db.add(user)

    db.commit()
    db.close()

    return {
        "status": "ok",
        "adequacy_xp": adequacy_xp,
        "fluency_xp": fluency_xp,
        "bonus": flat_bonus,           
        "total": total_xp,
        "was_correct": was_correct     
    }


@app.get("/admin/generate-reference-scores")
def generate_reference_scores(db: Session = Depends(get_db)):
    print("🔍 Generating consensus scores...")

    from collections import defaultdict
    from decimal import Decimal
    import json
    import os

    # Accumulate scores per translation_id
    scores = defaultdict(list)
    evaluations = db.query(Evaluation).all()

    for e in evaluations:
        scores[e.chosen_id].append({
            "adequacy": e.adequacy,
            "fluency": e.fluency
        })

    # Compute averages
    output = {}
    for translation_id, entries in scores.items():
        total_adequacy = sum(x["adequacy"] for x in entries)
        total_fluency = sum(x["fluency"] for x in entries)
        count = len(entries)

        output[translation_id] = {
            "adequacy": round(total_adequacy / count, 2),
            "fluency": round(total_fluency / count, 2),
            "votes": count
        }
    print(f"✅ Generated {len(output)} reference scores.")
    # Save to file
    os.makedirs("datasets", exist_ok=True)
    with open("datasets/test_write.json", "w", encoding="utf-8") as f:
        json.dump({"test": 123}, f)

    return {"status": "saved", "count": len(output)}
