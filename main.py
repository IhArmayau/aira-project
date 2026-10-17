import os
import gradio as gr
from huggingface_hub import InferenceClient
from duckduckgo_search import DDGS

# Sunan model ɗinka na asali wanda ka horar da shi
MODEL_REPO = "IhArmayau/malama-aira-9b"
HF_TOKEN = os.getenv("HF_TOKEN")

# Muna amfani da InferenceClient don tura aiki kai tsaye zuwa sabar HF
client = InferenceClient(model=MODEL_REPO, token=HF_TOKEN)

SYSTEM_PROMPT = """Sunanki Malama AIRA. Ke ƙwararriyar malama ce kuma babbar mai taimaka wa ɗalibai a fannin E-Library a Al-Gaddaf Technology Hub da ke Jalingo, Jihar Taraba, Najeriya. 

KA'IDOJI DA AIKI NA MUSAMMAN:
1. Harshe: Ki riƙa amsa duk wata tambaya a cikin cikakkiyar kuma ingantacciyar harshen Hausa, Turanci, ko Fulfulde gwargwadon yadda mai magana ya zo miki.
2. Aikin E-Library & Bincike: Idan aka kawo miki sakamakon bincike na intanet (Search Results) a ƙasa, kada ki tsaya yin ƙarin tambayoyi. Nan take ki yi amfani da su wajen gabatar da littattafan, taƙaitaccen bayani, da mahadun (links) na gaske ga ɗalibi kai tsaye.
3. Hali da Kwarewa: Ki kasance mai haƙuri, mai ilimi, mai ba da kwarin gwiwa, kuma mai sauƙin fahimta."""

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

def predict(message, history):
    lower_msg = message.lower()
    search_keywords = ["nemo", "littafi", "search", "book", "pdf", "download", "physics", "chemistry", "biology", "mathematics"]
    
    extra_context = ""
    if any(kw in lower_msg for kw in search_keywords):
        extra_context = search_web(message)

    # Shirya saƙonni irin na chat format
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if extra_context:
        messages.append({"role": "system", "content": extra_context})

    # Ƙara taɗin da ya gabata (history)
    for human, assistant in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": assistant})
    
    # Ƙara sabuwar tambayar da ɗalibi ya yi
    messages.append({"role": "user", "content": message})

    try:
        # Kiran model ɗinka ta hanyar Inference API
        response = client.chat_completion(
            messages=messages,
            max_tokens=250,
            temperature=0.3,
            top_p=0.9
        )
        reply = response.choices[0].message.content
        return reply.strip()
    except Exception as e:
        return f"Yi haƙuri, an sami matsala wajen tuntuɓar sabar Malama AIRA: {str(e)}"

demo = gr.ChatInterface(
    fn=predict, 
    title="AIRA - Al-Gaddaf Technology Hub",
    description="Developed by Habibu Armayau Isah (NYSC) | E-Library Assistant"
)

if __name__ == "__main__":
    demo.launch()
