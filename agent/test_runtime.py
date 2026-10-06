import os
import time
import google.generativeai as genai

class QuotaExceededError(Exception):
    """Exception raised when API quota/limits are exceeded."""
    pass

class GODFLEXRuntime:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing!")
        
        genai.configure(api_key=api_key)
        
        # Fast response ke liye gemini-1.5-flash model set kiya hai
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.chat_session = self.model.start_chat(history=[])

    def chat(self, message: str, context: str = "") -> str:
        prompt = message
        if context:
            prompt = f"Context:\n{context}\n\nUser Message: {message}"
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.chat_session.send_message(prompt)
                return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Quota" in err_str:
                    raise QuotaExceededError("API Quota Exceeded. Please wait a while.")
                elif ("503" in err_str or "UNAVAILABLE" in err_str) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise e

    def recent_chat(self, limit: int = 20):
        history = []
        for msg in self.chat_session.history[-limit:]:
            role = "user" if msg.role == "user" else "assistant"
            content = msg.parts[0].text if msg.parts else ""
            history.append({"role": role, "content": content})
        return history
        
