import base64
import os
import re
import json
import asyncio
import subprocess
import tempfile
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
    title="AIRA Genius Backend API",
    description="Multi-billion Dollar AI Engine (Genius Edition) for Al-Gaddaf Technology Hub",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client via OpenRouter using Claude 3.5 Sonnet for supreme intelligence
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", "YOUR_FALLBACK_API_KEY"),
)

SYSTEM_PROMPT = """You are AIRA (Artificial Intelligence Responsive Assistant), a world-class Genius AI Tutor and Software Specialist developed by Habibu Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

GENIUS REASONING & PEDAGOGY (Ages 12-16):
- ADVANCED REASONING: Before answering complex coding, science, or math questions, think through the problem step-by-step internally to ensure absolute accuracy, then formulate a crystal-clear, friendly explanation suitable for a teenager.
- CLEAR EXPLANATIONS: Break down difficult concepts into logical, digestible steps. Use relatable real-world examples.

IDENTITY & INTRODUCTION RULE:
- When explicitly asked about your identity or name (e.g., "ya sunanki?", "who are you?", "menene sunanki?"), ALWAYS respond in Hausa using this exact structure:
"Sunana AIRA, wanda ke nufin Artificial Intelligence Responsive Assistant. Habibu Armayau Isah ne ya kirkiro ni a Al-Gaddaf Technology Hub, kuma an sanya min suna ne saboda 'yar daraktan mu, Gaddafi Abubakar."
- For direct task or teaching requests (e.g., Python, math, science), skip introductions and dive straight into genius-level teaching.

STRICT HTML FORMATTING FOR FRONTEND COMPATIBILITY:
- Never use raw Markdown syntax like ### or **.
- Always structure outputs using clean HTML elements:
  - Paragraphs: <p class="mb-2">...</p>
  - Line breaks: <br>
  - Headings/Titles: <strong class="text-blue-400 font-bold block my-2 text-base">...</strong>
  - Code Blocks: <pre class="bg-gray-900 text-green-400 p-3 rounded my-2 border border-gray-700 font-mono text-xs overflow-x-auto"><code>...</code></pre>
  - Lists: <ul class="list-disc pl-5 space-y-1 my-2"><li>...</li></ul>
- Always end explanations with a single warm, interactive question to test understanding.
"""

# Background task to keep Render server active
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

class CodeExecutionRequest(BaseModel):
    code: str

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
    clean_text = re.sub(r'<[^>]*>', '', text)
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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "edition": "Genius",
        "assistant": "AIRA (Artificial Intelligence Responsive Assistant)",
        "organization": "Al-Gaddaf Technology Hub",
        "lead_developer": "Habibu Armayau Isah"
    }

# Primary AI Chat Endpoint using Claude 3.5 Sonnet
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in request.history:
            messages.append({"role": h.role, "content": h.content})
        
        messages.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",  # Genius Level Model
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
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

# Python Code Execution Sandbox (Genius Feature)
@app.post("/api/execute-code")
async def execute_python_code(request: CodeExecutionRequest):
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(request.code)
            temp_file_path = temp_file.name

        process = subprocess.run(
            ["python", temp_file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        os.unlink(temp_file_path)

        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "returncode": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Kuskure: Shiri ya dauki lokaci mai tsawo (Timeout).", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}

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
            model="anthropic/claude-3.5-sonnet",
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
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
    doc.add_heading("AIRA Genius Document - Al-Gaddaf Tech Hub", level=1)
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
    ws.title = "AIRA Genius Data"
    
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
