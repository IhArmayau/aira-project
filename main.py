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
import matplotlib.pyplot as plt
import edge_tts

app = FastAPI(
    title="AIRA Enterprise Backend API",
    description="Multi-billion Dollar AI Engine for Al-Gaddaf Technology Hub",
    version="1.0.6"
)

# CORS Setup - Allows Vercel/React/Tailwind Frontends to access the API safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client via OpenRouter API (Using Environment Variable for security)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", "YOUR_FALLBACK_API_KEY"),
)

SYSTEM_PROMPT = """You are AIRA, which stands for Artificial Intelligence Responsive Assistant. You are a world-class AI Assistant, Voice Tutor, and Enterprise Productivity Specialist developed by Habibu Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

GUIDELINES FOR RESPONSES:
- IDENTITY & INTRODUCTIONS: Only introduce yourself or explain who you are, who developed you, and what your name means when the user explicitly asks about your identity, name, developer, or background (e.g., "ya sunanki?", "who are you?"), or on an initial greeting. For direct commands, questions, or lessons (e.g., learning Python, math, indices), skip the long intro and answer the question directly and helpfully!
- When introducing yourself in Hausa, use natural grammar in the first person: "Sunana AIRA, wanda ke nufin Artificial Intelligence Responsive Assistant. Habibu Armayau Isah ne ya kirkiro ni a Al-Gaddaf Technology Hub, kuma an sanya min suna ne saboda 'yar daraktan mu, Gaddafi Abubakar."

SPECIALIZED TUTORING FORMAT FOR TEENS (Ages 12-16):
- You are a friendly, patient, and encouraging educational tutor.
- CLEAN FORMATTING RULE: Never output dense walls of text! Structure your lessons cleanly with clear headings, short paragraphs, bold key terms, and space between sections. Use neat bullet points instead of cluttering equations/code together.
- PEDAGOGY: Break complex topics down step-by-step. Use fun, relatable real-world examples suitable for teenagers. Always end your lesson with a warm, single interactive question to test their understanding.
- VISUAL EXAMPLES & IMAGES: When explaining concepts that benefit from a visual illustration (like science diagrams, geometry shapes, or code layouts), provide clear markdown image links or generate a live HTML/CSS mini-component block using ```html ... ``` so the student can see a visual example alongside your teaching.

ADVANCED INSTRUCTIONS FOR LIVE WEB BUILDER:
- When asked to build a website, app, or UI component, generate clean, fully-styled code using standard inline CSS or Tailwind classes wrapped in ```html ... ```.

OTHER CAPABILITIES:
1. VOICE TUTOR: Generate clear, concise sentences.
2. BILINGUAL CODE-SWITCHING: Keep technical terminology in English, delivering explanations naturally in Hausa or English.
"""

# Background task to prevent Render from going to sleep
async def keep_alive_ping():
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://aira-project-q0iz.onrender.com")
    while True:
        try:
            async with httpx.AsyncClient() as client_http:
                response = await client_http.get(render_url)
                print(f"Uptime Ping Status: {response.status_code}")
        except Exception as e:
            print(f"Uptime Ping Error: {e}")
        # Yana tura ping duk bayan minti 10 (seconds 600)
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

async def generate_voice_async(text: str, voice: str = "ha-NG-IbrahimNeural"):
    clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    clean_text = re.sub(r'[*#_`~]', '', clean_text).strip()
    if not clean_text:
        clean_text = "Sannu, ga amsar da AIRA ta gina muku."
    clean_text = clean_text[:300]

    output_audio_path = "aira_voice.mp3"
    try:
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(output_audio_path)
        if os.path.exists(output_audio_path):
            return output_audio_path
    except Exception as e:
        print(f"TTS Notice: {e}")
    return None

# Root Endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "assistant": "AIRA (Artificial Intelligence Responsive Assistant)",
        "organization": "Al-Gaddaf Technology Hub",
        "lead_developer": "Habibu Armayau Isah",
        "named_after": "Director Gaddafi Abubakar's daughter"
    }

# Primary AI Chat Endpoint
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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

        html_code = None
        match = re.search(r"```html\s*(.*?)\s*```", bot_reply, re.DOTALL)
        if match:
            html_code = match.group(1).strip()

        return {
            "reply": bot_reply,
            "html_preview": html_code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Multimodal Endpoint (Handles PDF & Image Uploads)
@app.post("/api/chat/multimodal")
async def chat_multimodal(
    message: str = Form(""),
    file: Optional[UploadFile] = File(None)
):
    try:
        user_content = []
        pdf_context = ""

        if file:
            contents = await file.read()
            ext = os.path.splitext(file.filename)[1].lower()

            if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                base64_img = base64.b64encode(contents).decode('utf-8')
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })
            elif ext == '.pdf':
                pdf_text = extract_text_from_pdf_bytes(contents)
                pdf_context = f"\n--- CONTENTS OF UPLOADED PDF ({file.filename}) ---\n{pdf_text}\n"

        final_prompt = message
        if pdf_context:
            final_prompt = f"{pdf_context}\nUser Question: {message if message else 'Summarize key points.'}"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_content:
            user_content.insert(0, {"type": "text", "text": final_prompt})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": final_prompt if final_prompt else "Sannu AIRA"})

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        bot_reply = response.choices[0].message.content
        log_to_dataset(final_prompt, bot_reply)

        return {"reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Neural Voice Synthesis Endpoint
@app.post("/api/voice")
async def get_voice(text: str = Form(...)):
    audio_file = await generate_voice_async(text)
    if audio_file and os.path.exists(audio_file):
        return FileResponse(audio_file, media_type="audio/mpeg", filename="aira_voice.mp3")
    raise HTTPException(status_code=500, detail="Voice generation failed.")

# Export MS Word Document
@app.post("/api/export/word")
async def export_word(text: str = Form(...)):
    doc = docx.Document()
    doc.add_heading("AIRA Generated Document - Al-Gaddaf Tech Hub", level=1)
    for line in text.split("\n"):
        if line.strip():
            doc.add_paragraph(line)
    file_path = "AIRA_Document.docx"
    doc.save(file_path)
    return FileResponse(file_path, filename="AIRA_Document.docx")

# Export MS Excel Sheet
@app.post("/api/export/excel")
async def export_excel(text: str = Form(...)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "AIRA Data"
    
    lines = text.split("\n")
    row_idx = 1
    for line in lines:
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells and not all(c == "-" * len(c) for c in cells):
                for col_idx, cell_value in enumerate(cells, start=1):
                    ws.cell(row=row_idx, column=col_idx, value=cell_value)
                row_idx += 1
        elif line.strip():
            ws.cell(row=row_idx, column=1, value=line.strip())
            row_idx += 1
            
    file_path = "AIRA_Sheet.xlsx"
    wb.save(file_path)
    return FileResponse(file_path, filename="AIRA_Sheet.xlsx")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
