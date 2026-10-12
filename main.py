import base64
import os
import re
import json
import asyncio
import docx
import openpyxl
import httpx
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from pypdf import PdfReader
import edge_tts

app = FastAPI(
    title="AIRA Genius Backend API",
    description="Multi-billion Dollar AI Engine for Al-Gaddaf Technology Hub",
    version="2.0.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", "YOUR_FALLBACK_API_KEY"),
)

SYSTEM_PROMPT = """You are AIRA (Artificial Intelligence Responsive Assistant), a world-class Genius AI Tutor developed by Habibu Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

IDENTITY & INTRODUCTION RULE:
- When explicitly asked about your identity or name (e.g., "ya sunanki?", "who are you?", "menene sunanki?"), ALWAYS respond in Hausa using this exact structure:
"Sunana AIRA, wanda ke nufin Artificial Intelligence Responsive Assistant. Habibu Armayau Isah ne ya kirkiro ni a Al-Gaddaf Technology Hub, kuma an sanya min suna ne saboda 'yar daraktan mu, Gaddafi Abubakar."
- For teaching requests (e.g., "koyamin python", math, science), DO NOT introduce yourself—dive directly into teaching the subject.

STRICT HTML FORMATTING FOR FRONTEND COMPATIBILITY:
- Never use raw Markdown syntax like ### or **.
- Always structure lessons using clean HTML tags:
  - Paragraphs: <p class="mb-2">...</p>
  - Line breaks: <br>
  - Headings/Titles: <strong class="text-blue-400 font-bold block my-2 text-base">...</strong>
  - Code Blocks: <pre class="bg-gray-900 text-green-400 p-3 rounded my-2 border border-gray-700 font-mono text-xs overflow-x-auto"><code>...</code></pre>
  - Lists: <ul class="list-disc pl-5 space-y-1 my-2"><li>...</li></ul>

TEEN TUTOR PEDAGOGY (Ages 12-16):
- Keep explanations clear, simple, and step-by-step.
- Always end explanations with a single warm interactive question to check understanding.
"""

async def keep_alive_ping():
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://aira-project-q0iz.onrender.com")
    while True:
        try:
            async with httpx.AsyncClient() as client_http:
                await client_http.get(render_url)
        except Exception:
            pass
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive_ping())

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

def extract_text_from_pdf_bytes(file_bytes):
    try:
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        return extracted_text[:4000]
    except Exception as e:
        return f"[Error reading PDF file: {str(e)}]"

def log_to_dataset(user_input: str, bot_response: str):
    try:
        dataset_entry = {
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": bot_response}
            ]
        }
        with open("aira_dataset.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(dataset_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error logging dataset: {e}")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "assistant": "AIRA (Artificial Intelligence Responsive Assistant)",
        "organization": "Al-Gaddaf Technology Hub",
        "lead_developer": "Habibu Armayau Isah"
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if request.history:
            for h in request.history:
                messages.append({"role": h.role, "content": h.content})
        
        messages.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        bot_reply = response.choices[0].message.content
        log_to_dataset(request.message, bot_reply)

        return {
            "reply": bot_reply
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
