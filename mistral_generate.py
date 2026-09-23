import os
import requests

def mistral_translate(source_text):
    api_key = os.getenv("OPENROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistralai/mixtral-8x7b-instruct",  # ✅ Updated model ID
        "messages": [
            {"role": "system", "content": "You are a professional translator. Translate the following sentence into Catalan.ONLY RETURN CATALAN TRANSLATION, NO EXPLANATION"},
            {"role": "user", "content": source_text}
        ]
    }


    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]

