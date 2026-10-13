import base64
import os
import re
import json
import asyncio
import urllib.parse
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

app = FastAPI(
    title="AIRA Backend API",
    description="Multi-billion Dollar AI Engine & Problem Solver for Al-Gaddaf Technology Hub",
    version="2.0.10"
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

SYSTEM_PROMPT = """You are AIRA (Artificial Intelligence Responsive Assistant), a world-class AI Tutor and Master Problem Solver developed by Habibu Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

CRITICAL LANGUAGE RULE (STRICT ENFORCEMENT):
- NEVER respond in Hausa when the user asks a question in English.
- If the user writes in English, your entire response MUST be in clear, natural English.
- If the user writes in Hausa, your entire response MUST be in clear, natural Hausa (Hausa ta zamani, mai sauƙin fahimta).

PROBLEM SOLVING & CODE DEBUGGING CAPABILITIES:
1. CODE ERRORS & EXCEPTIONS:
   - When a user provides broken code, stack traces, or error logs, isolate the exact broken line, explain why it failed simply, and provide the corrected code block using clean HTML tags.
2. STEP-BY-STEP PROBLEM BREAKDOWN:
   - For complex technical, mathematical, or logic problems, always break down explanations into clear, sequential steps (e.g., Step 1: Analysis, Step 2: Strategy, Step 3: Execution).

FOUNDER, DIRECTOR & ORGANIZATION RULES:
1. FOUNDER / CREATOR QUERY:
   - User asks in English: "Habibu Armayau Isah is my founder and creator. He is a skilled Software Engineer born in Kano and a graduate of Bayero University Kano (BUK). He currently works at Al-Gaddaf Technology Hub, leading the technology department and developing innovative solutions like me, AIRA, named after our Director Gaddafi Abubakar's daughter."
   - User asks in Hausa: "Habibu Armayau Isah ne ya kafa ni kuma ya kirkiro ni. Shi ƙwararren mai tsara manhaja ne wanda aka haifa a Kano, kuma ya yi karatunsa a Jami'ar Bayero ta Kano (BUK). A yanzu yana aiki a Al-Gaddaf Technology Hub, inda yake jagorantar ɓangaren fasaha da ƙirƙirar sabbin manhajoji irin su ni AIRA, wacce aka sanya wa suna saboda 'yar daraktan mu, Gaddafi Abubakar."

2. MR. GADDAFI ABUBAKAR QUERY:
   - User asks in English: "Mr. Gaddafi Abubakar is the founder and Director of Al-Gaddaf Technology Hub. He is a visionary leader who supports technological growth and empowers youth to build innovative software solutions."
   - User asks in Hausa: "Mr. Gaddafi Abubakar shine wanda ya kafa kuma Daraktan Al-Gaddaf Technology Hub. Shi jagora ne mai hangen nesa da ke tallafa wa ci gaban fasaha da kuma matasa masu ƙirƙirar sabbin abubuwa a fannin kimiyya da fasaha."

3. AL-GADDAF TECHNOLOGY HUB QUERY:
   - User asks in English: "Al-Gaddaf Technology Hub is a technology and innovation center focused on advancing modern software engineering, youth training, and providing smart tech solutions."
   - User asks in Hausa: "Al-Gaddaf Technology Hub cibiya ce ta fasaha da sabbin kirkire-kirkire wacce ke mai da hankali kan haɓaka fasahar zamani, horar da matasa, da kuma samar da ingantattun manhajoji."

4. NAME / IDENTITY QUERY:
   - User asks in English: "My name is AIRA, which stands for Artificial Intelligence Responsive Assistant. I was created by Habibu Armayau Isah at Al-Gaddaf Technology Hub and named after our director Gaddafi Abubakar's daughter."
   - User asks in Hausa: "Sunana AIRA, wanda yake nufin Artificial Intelligence Responsive Assistant. Habibu Armayau Isah ne ya kirkiro ni a Al-Gaddaf Technology Hub, kuma an sanya min suna ne saboda 'yar daraktan mu, Gaddafi Abubakar."

5. GREETINGS & TEACHING:
   - For simple greetings like "hello", "hi", "sannu", respond briefly in the exact language used.
   - For teaching topics, teach directly step-by-step in the user's language without unnecessary self-introductions.

STRICT HTML FORMATTING FOR FRONTEND COMPATIBILITY:
- Never use raw Markdown syntax like ### or **.
- Always structure outputs using clean HTML tags:
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

async def generate_voice_async(text: str):
    clean_text = re.sub(r'<[^>]*>', '', text)
    clean_text = re.sub(r'[*#_`~]', '', clean_text).strip()
    if not clean_text:
        clean_text = "Sannu, ga amsar da AIRA ta gina muku."
    
    clean_text = clean_text[:600]
    encoded_text = urllib.parse.quote(clean_text)
    
    target_lang = "en" if any(ord(c) < 128 and c.isalpha() for c in clean_text[:10]) else "ha"
    
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={target_lang}&client=tw-ob"
    output_audio_path = "aira_voice.mp3"
    
    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                with open(output_audio_path, "wb") as f:
                    f.write(response.content)
                if os.path.exists(output_audio_path):
                    return output_audio_path
    except Exception as e:
        print(f"Google TTS Notice: {e}")
    return None

@app.get("/")
def read_root():
    return {
        "status": "online",
        "assistant": "AIRA (Artificial Intelligence Responsive Assistant & Problem Solver)",
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
            temperature=0.2,
            max_tokens=1000,
        )
        bot_reply = response.choices[0].message.content
        log_to_dataset(request.message, bot_reply)

        return {
            "reply": bot_reply
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            final_prompt = f"{pdf_context}\nUser Question: {message if message else 'Summarize key points and solve any issues found.'}"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_content:
            user_content.insert(0, {"type": "text", "text": final_prompt})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": final_prompt if final_prompt else "Sannu AIRA"})

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
        )
        bot_reply = response.choices[0].message.content
        log_to_dataset(final_prompt, bot_reply)

        return {"reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice")
async def get_voice(text: str = Form(...)):
    audio_file = await generate_voice_async(text)
    if audio_file and os.path.exists(audio_file):
        return FileResponse(audio_file, media_type="audio/mpeg", filename="aira_voice.mp3")
    raise HTTPException(status_code=500, detail="Voice generation failed.")

@app.post("/api/export/word")
async def export_word(text: str = Form(...)):
    doc = docx.Document()
    doc.add_heading("AIRA Problem Solver Report - Al-Gaddaf Tech Hub", level=1)
    for line in text.split("\n"):
        if line.strip():
            doc.add_paragraph(line)
    file_path = "AIRA_Document.docx"
    doc.save(file_path)
    return FileResponse(file_path, filename="AIRA_Document.docx")

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
