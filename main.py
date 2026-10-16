import base64
import os
import re
import json
import asyncio
import urllib.parse
from pathlib import Path
import docx
import openpyxl
import httpx
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from duckduckgo_search import DDGS
from pypdf import PdfReader

app = FastAPI(
    title="Malama AIRA E-Library API",
    description="Trilingual Autonomous AI E-Library & Higher-Education Teacher for Al-Gaddaf Technology Hub",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. LOAD YOUR CUSTOM HUGGING FACE MODEL ---
MODEL_REPO = "IhArmayau/malama-aira-trilingual-1.5b"
print(f"--- Loading Malama AIRA Model: {MODEL_REPO} ---")
tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_REPO, 
    torch_dtype=torch.float16, 
    device_map="auto"
)

# --- 2. LOCAL BOOK LIBRARY SETUP ---
BOOK_LIBRARY_DIR = "aira_full_library"
os.makedirs(BOOK_LIBRARY_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are Malama AIRA, an advanced trilingual e-library digital teacher and higher-education assistant supporting English, Hausa, and Jalingo Fulfulde, developed by Habibu Armayau Isah at Al-Gaddaf Technology Hub, named after Director Gaddafi Abubakar's daughter.

CRITICAL LANGUAGE RULE:
- Match the user's language precisely (English for English, Hausa for Hausa).
- Never mix up local geography: Jalingo is strictly in Taraba State, Nigeria.
- Structure answers clearly using clean HTML tags (<p>, <pre><code>, <strong>, <ul><li>) as requested by the frontend interface."""

def search_local_book_library(query):
    """Searches through downloaded textbooks offline"""
    extracted_context = ""
    library_path = Path(BOOK_LIBRARY_DIR)
    if not list(library_path.glob("*.pdf")):
        return ""
    
    try:
        for pdf_file in library_path.glob("*.pdf"):
            reader = PdfReader(pdf_file)
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if any(kw.lower() in text.lower() for kw in query.split()[:3]):
                    extracted_context += f"\n[Source Book: {pdf_file.name}, Page {page_num+1}]\n{text[:400]}\n"
    except Exception:
        pass
    return extracted_context

def autonomous_web_search(query):
    """Fetches live context from the web autonomously"""
    results_text = ""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            for r in results:
                results_text += f"Source Title: {r.get('title')}\nExcerpt: {r.get('body')}\n\n"
    except Exception:
        pass
    return results_text

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

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    lang: Optional[str] = "en"

@app.get("/")
def read_root():
    return {
        "status": "online",
        "assistant": "Malama AIRA E-Library & Problem Solver Agent",
        "model": MODEL_REPO,
        "organization": "Al-Gaddaf Technology Hub",
        "lead_developer": "Habibu Armayau Isah"
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Step 1: Check local offline textbook library first
        context = search_local_book_library(request.message)
        
        # Step 2: If no local book found, search web autonomously
        if not context.strip():
            context = autonomous_web_search(request.message)
            
        if not context.strip():
            context = "General academic knowledge base for Malama AIRA."

        # Step 3: Build prompt sequence for your local model
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        if request.history:
            for h in request.history:
                messages.append({"role": h.role, "content": h.content})
                
        user_full_prompt = f"RESEARCH CONTEXT:\n{context}\n\nSTUDENT QUESTION: {request.message}"
        messages.append({"role": "user", "content": user_full_prompt})
        
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")
        
        outputs = model.generate(
            **inputs, 
            max_new_tokens=400, 
            do_sample=True, 
            temperature=0.3, 
            repetition_penalty=1.2,
            pad_token_id=tokenizer.eos_token_id
        )
        
        bot_reply = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        log_to_dataset(request.message, bot_reply)
        
        return {"reply": bot_reply}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/multimodal")
async def chat_multimodal(
    message: str = Form(""),
    file: Optional[UploadFile] = File(None)
):
    try:
        pdf_context = ""
        if file:
            contents = await file.read()
            ext = os.path.splitext(file.filename)[1].lower()
            if ext == '.pdf':
                pdf_text = extract_text_from_pdf_bytes(contents)
                pdf_context = f"\n--- CONTENTS OF UPLOADED PDF ({file.filename}) ---\n{pdf_text}\n"

        final_prompt = message
        if pdf_context:
            final_prompt = f"{pdf_context}\nUser Question: {message if message else 'Summarize key points and solve any issues found.'}"

        # Search local or web for additional context if query requires it
        context = search_local_book_library(final_prompt)
        if not context.strip():
            context = autonomous_web_search(final_prompt)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nPROMPT:\n{final_prompt}"}
        ]
        
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")
        
        outputs = model.generate(
            **inputs, 
            max_new_tokens=400, 
            do_sample=True, 
            temperature=0.3, 
            repetition_penalty=1.2,
            pad_token_id=tokenizer.eos_token_id
        )
        
        bot_reply = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        log_to_dataset(final_prompt, bot_reply)

        return {"reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/books/download")
async def api_download_book(book_url: str = Form(...), book_name: str = Form(...)):
    """Autonomously downloads and indexes full textbooks into local storage"""
    safe_filename = "".join([c if c.isalnum() else "_" for c in book_name]) + ".pdf"
    file_path = Path(BOOK_LIBRARY_DIR) / safe_filename
    
    if file_path.exists():
        return {"status": "success", "message": f"Book '{book_name}' is already in local storage."}
        
    try:
        response = httpx.get(book_url, timeout=30)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return {"status": "success", "message": f"Successfully downloaded and indexed '{book_name}' locally."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    raise HTTPException(status_code=400, detail="Failed to download book from the given URL.")

@app.get("/api/books/list")
async def list_local_books():
    """Lists all locally stored offline textbooks"""
    library_path = Path(BOOK_LIBRARY_DIR)
    books = [f.name for f in library_path.glob("*.pdf")]
    return {"local_library": books}

@app.post("/api/export/word")
async def export_word(text: str = Form(...)):
    doc = docx.Document()
    doc.add_heading("Malama AIRA E-Library Report - Al-Gaddaf Tech Hub", level=1)
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
