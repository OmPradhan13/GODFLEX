import os
import time
import google.generativeai as genai
from google.api_core import exceptions

class QuotaExceededError(Exception):
    """Exception raised when API quota/limits are exceeded."""
    pass

class GODFLEXRuntime:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing!")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.chat_history = []

    def chat(self, message: str, context: str = "") -> str:
        prompt = message
        if context:
            prompt = f"Context:\n{context}\n\nUser Message: {message}"
            
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Direct generate_content call with full session history
                messages = []
                for msg in self.chat_history:
                    messages.append({"role": msg["role"], "parts": [msg["content"]]})
                messages.append({"role": "user", "parts": [prompt]})

                response = self.model.generate_content(messages)
                
                # Save to history
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "model", "content": response.text})
                
                # Keep history bounded to last 20 messages
                if len(self.chat_history) > 20:
                    self.chat_history = self.chat_history[-20:]

                return response.text

            except (exceptions.ServiceUnavailable, exceptions.InternalServerError) as e:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential wait: 2s, 4s, 6s, 8s
                    continue
                raise Exception("Gemini servers are currently overloaded. Please try again in a moment.") from e
            except exceptions.ResourceExhausted as e:
                raise QuotaExceededError("API Quota Exceeded. Please wait a while.") from e
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise e

    def recent_chat(self, limit: int = 20):
        return self.chat_history[-limit:]
                    
