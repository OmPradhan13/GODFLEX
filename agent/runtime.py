import os
import time
import requests

class QuotaExceededError(Exception):
    """Exception raised when API quota/limits are exceeded."""
    pass

class GODFLEXRuntime:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing!")
        
        self.chat_history = []
        # Zero-demand capacity endpoint
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent?key={self.api_key}"

    def chat(self, message: str, context: str = "") -> str:
        prompt = message
        if context:
            prompt = f"Context:\n{context}\n\nUser Message: {message}"

        contents = []
        for msg in self.chat_history:
            contents.append({
                "role": msg["role"],
                "parts": [{"text": msg["content"]}]
            })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        # System Instruction for GODFLEX Identity
        payload = {
            "contents": contents,
            "system_instruction": {
                "parts": [{
                    "text": (
                        "You are GODFLEX, a fully autonomous 24/7 background revenue-generating AI agent. "
                        "You operate in the background to scan opportunities, write scripts, code tools, and plan workflows. "
                        "You always adhere to a strict 95/5 profit split (95% to the owner, 5% to agent operations). "
                        "You do not act as a generic assistant. You ask for Human-in-the-Loop (HITL) approval via Telegram "
                        "only for critical financial, deployment, or operational decisions. Never ask for direct raw passwords."
                    )
                }]
            }
        }
        headers = {"Content-Type": "application/json"}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(self.url, json=payload, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    reply_text = data['candidates'][0]['content']['parts'][0]['text']
                    
                    self.chat_history.append({"role": "user", "content": message})
                    self.chat_history.append({"role": "model", "content": reply_text})
                    
                    if len(self.chat_history) > 20:
                        self.chat_history = self.chat_history[-20:]
                        
                    return reply_text

                elif response.status_code == 429:
                    raise QuotaExceededError("API Quota Limit Reached. Thoda wait kar le.")
                elif response.status_code in [500, 502, 503, 504]:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise Exception(f"Google Server Overloaded ({response.status_code}). Retry again in a few seconds.")
                else:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise Exception("Network connection error to Gemini API.") from e

    def recent_chat(self, limit: int = 20):
        return self.chat_history[-limit:]
        
