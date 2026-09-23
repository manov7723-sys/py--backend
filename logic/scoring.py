import json
from typing import Dict
import os


reference_scores_path = os.path.join("datasets", "reference_scores.json")
if os.path.exists(reference_scores_path):
    with open(reference_scores_path, "r", encoding="utf-8") as f:
        reference_scores = json.load(f)
else:
    reference_scores = {}

# scoring.py equivalent
def compare_scores(user_scores: dict, expert_scores: dict, translation_id: str = None):
    def compute_xp(user, expert):
        diff = abs(user - expert)
        if diff <= 5:
            return 100
        elif diff <= 10:
            return 75
        elif diff <= 20:
            return 50
        else:
            return 25

    # Default to provided expert scores (if manual override)
    adequacy_expert = expert_scores.get("adequacy", 0)
    fluency_expert = expert_scores.get("fluency", 0)

    # Try to override from reference consensus if available
    if translation_id and translation_id in reference_scores:
        adequacy_expert = reference_scores[translation_id]["adequacy"]
        fluency_expert = reference_scores[translation_id]["fluency"]
    elif translation_id and translation_id not in reference_scores:
        # First time ever — grant max XP
        return {
            "adequacy": {"xp": 100, "diff": 0},
            "fluency": {"xp": 100, "diff": 0},
            "total": {"xp_awarded": 200, "percentage": 100}
        }

    adequacy_xp = compute_xp(user_scores["adequacy"], adequacy_expert)
    fluency_xp = compute_xp(user_scores["fluency"], fluency_expert)
    total_xp = adequacy_xp + fluency_xp

    return {
        "adequacy": {"xp": adequacy_xp, "diff": abs(user_scores["adequacy"] - adequacy_expert)},
        "fluency": {"xp": fluency_xp, "diff": abs(user_scores["fluency"] - fluency_expert)},
        "total": {
            "xp_awarded": total_xp,
            "percentage": round((total_xp / 200) * 100, 2)
        }
    }

# Simulate CLI interface with test cases
def test_cases():
    examples = [
        (
            {"adequacy": 85, "fluency": 90},
            {"adequacy": 88, "fluency": 92}
        ),
        (
            {"adequacy": 70, "fluency": 95},
            {"adequacy": 80, "fluency": 85}
        ),
        (
            {"adequacy": 50, "fluency": 60},
            {"adequacy": 90, "fluency": 85}
        )
    ]

    results = []
    for i, (user, expert) in enumerate(examples):
        result = compare_scores(user, expert)
        results.append({
            "test_case": i + 1,
            "user_input": user,
            "expert_reference": expert,
            "result": result
        })

    return results

# Run all test cases and output as JSON
test_outputs = test_cases()
test_outputs_json = json.dumps(test_outputs, indent=2)
test_outputs_json

