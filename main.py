import base64
import os
import re
import json
import asyncio
import docx
import openpyxl
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
    version="1.0.0"
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

SYSTEM_PROMPT = """You are AIRA (Artificial Intelligence Responsive Assistant), a world-class AI Assistant, Voice Tutor, and Enterprise Productivity Specialist developed by Habeeb Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

ADVANCED INSTRUCTIONS FOR LIVE WEB BUILDER:
- When asked to build a website, app, or UI component, generate clean, fully-styled code. Use standard inline CSS styles or Tailwind classes.
- Wrap the complete, single-file HTML code block using ```html ... ``` so frontend applications can render it live.

OTHER CAPABILITIES:
1. VOICE TUTOR: Generate clear, concise sentences.
2. BILINGUAL CODE-SWITCHING: Keep technical terminology in English, delivering explanations naturally in Hausa or English.
"""

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

def generate_chart_from_data(labels, values, title="AIRA Data Analytics"):
    try:
        plt.figure(figsize=(6, 4))
        plt.bar(labels, values, color='#2b5c8f')
        plt.title(title)
        plt.xlabel("Categories")
        plt.ylabel("Values")
        plt.tight_layout()
        chart_path = "aira_chart.png"
        plt.savefig(chart_path)
        plt.close()
        return chart_path
    except Exception:
        return None

# Root Endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "assistant": "AIRA",
        "organization": "Al-Gaddaf Technology Hub",
        "lead_developer": "Habeeb Armayau Isah"
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

        # Extract HTML preview if present
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
