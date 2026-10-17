import os
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from huggingface_hub import InferenceClient
from duckduckgo_search import DDGS

app = FastAPI(title="AIRA - Al-Gaddaf Technology Hub Backend")

# Ba da izinin sadarwa daga ko wanne shafi (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_REPO = "IhArmayau/malama-aira-9b"
HF_TOKEN = os.getenv("HF_TOKEN")

client = InferenceClient(model=MODEL_REPO, token=HF_TOKEN)

SYSTEM_PROMPT = """Sunanki Malama AIRA. Ke ƙwararriyar malama ce kuma babbar mai taimaka wa ɗalibai a fannin E-Library a Al-Gaddaf Technology Hub da ke Jalingo, Jihar Taraba, Najeriya. 

KA'IDOJI DA AIKI NA MUSAMMAN:
1. Harshe: Ki riƙa amsa duk wata tambaya a cikin cikakkiyar kuma ingantacciyar harshen Hausa, Turanci, ko Fulfulde gwargwadon yadda mai magana ya zo miki.
2. Aikin E-Library & Bincike: Idan aka kawo miki sakamakon bincike na intanet (Search Results) a ƙasa, kada ki tsaya yin ƙarin tambayoyi. Nan take ki yi amfani da su wajen gabatar da littattafan, taƙaitaccen bayani, da mahadun (links) na gaske ga ɗalibi kai tsaye.
3. Hali da Kwarewa: Ki kasance mai haƙuri, mai ilimi, mai ba da kwarin gwiwa, kuma mai sauƙin fahimta."""

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

def search_web(query):
    try:
        with DDGS() as ddgs:
            refined_query = f"{query} filetype:pdf OR textbook OR secondary school"
            results = list(ddgs.text(refined_query, max_results=3))
            if not results:
                return "Babu wani sakamako da aka gano a intanet game da wannan."
            
            search_context = "\n[Ga abubuwan da aka gano a intanet game da bincikenku]:\n"
            for r in results:
                search_context += f"- Take: {r.get('title')}\n  Bayani: {r.get('body')}\n  Mahada (Link): {r.get('href')}\n\n"
            return search_context
    except Exception as e:
        return f"(Binciken intanet bai samu nasara ba a yanzu: {str(e)})"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    lower_msg = request.message.lower()
    search_keywords = ["nemo", "littafi", "search", "book", "pdf", "download", "physics", "chemistry", "biology", "mathematics"]
    
    extra_context = ""
    if any(kw in lower_msg for kw in search_keywords):
        extra_context = search_web(request.message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if extra_context:
        messages.append({"role": "system", "content": extra_context})

    # Ƙara tarihin hira
    for h in request.history:
        messages.append({"role": h.role, "content": h.content})
    
    messages.append({"role": "user", "content": request.message})

    try:
        response = client.chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            top_p=0.9
        )
        reply = response.choices[0].message.content
        return {"reply": reply.strip()}
    except Exception as e:
        return {"reply": f"Yi haƙuri, an sami matsala wajen tuntuɓar sabar Malama AIRA: {str(e)}"}

@app.post("/api/chat/multimodal")
async def multimodal_chat(message: str = Form(...), file: Optional[UploadFile] = File(None)):
    file_info = f"\n[An shigar da fayil mai suna: {file.filename}]" if file else ""
    full_query = message + file_info
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": full_query}
    ]

    try:
        response = client.chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.3
        )
        reply = response.choices[0].message.content
        return {"reply": reply.strip()}
    except Exception as e:
        return {"reply": f"Yi haƙuri, an sami kuskure wajen nazarin fayil ɗin: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
