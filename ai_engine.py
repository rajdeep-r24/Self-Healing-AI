import os
import json
from google import genai
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class AIResponse(BaseModel):
    diagnosis: str
    fixed_code: str

import time
import os
import re
from google.genai.errors import APIError

def diagnose_and_fix(traceback_text: str, source_code: str) -> dict:
    """
    Sends the traceback and source code to the AI engine to get a fix.
    Returns a dictionary with 'diagnosis' and 'fixed_code'.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is not set.")

    primary_model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")
    
    prompt = f"""
    You are an autonomous AI Software Engineer. Your goal is to FIX a broken file.
    
    You will receive:
    1. A traceback showing the error.
    2. The current source code of the file.

    **YOUR MANDATORY CHECKLIST:**
    1. Analyze the traceback and the provided source code.
    2. Identify the root cause and find the specific line causing the error.
    3. Produce the smallest safe correction to fix the logic error.
    4. Preserve existing functionality. Do not invent unrelated features or remove working functionality.
    5. Return the COMPLETE corrected source code in your response.
    
    **Traceback:**
    {traceback_text}
    
    **Source Code:**
    ```python
    {source_code}
    ```
    """

    global_start = time.time()
    max_attempts = 3
    # We aim to stay well under the 90-second evaluation limit
    total_budget_sec = 80.0 
    
    for attempt in range(1, max_attempts + 1):
        elapsed = time.time() - global_start
        remaining = total_budget_sec - elapsed
        
        if remaining <= 0:
            print("[AI] Gemini request timed out (Total time limit reached)")
            raise RuntimeError("AI_SERVICE_UNAVAILABLE")
            
        # The prompt says 30s is a reasonable timeout per request.
        # But if we have less than 30s remaining, we should use the remaining time to not exceed the global limit.
        current_req_timeout = min(30.0, remaining)
        current_req_timeout_ms = int(current_req_timeout * 1000)
        
        # Prefer configuring the client with explicit HttpOptions timeout in milliseconds
        client = genai.Client(api_key=api_key, http_options={'timeout': current_req_timeout_ms})

        try:
            print(f"[AI] Gemini request attempt {attempt}/{max_attempts}")
            
            # Switch to fallback model on the last attempt if configured
            current_model = primary_model
            if attempt == max_attempts and fallback_model:
                current_model = fallback_model
                print(f"[AI] Switching to fallback model: {current_model}")
            
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AIResponse,
                    temperature=0.1
                )
            )
            
            raw_text = response.text
            # Strip markdown fences if present
            raw_text = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
            raw_text = re.sub(r"```$", "", raw_text.strip(), flags=re.MULTILINE)
            
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                raise ValueError("AI response was not valid JSON")

            if "fixed_code" not in data or not data["fixed_code"]:
                raise ValueError("Missing or empty fixed_code in AI response")
            if "diagnosis" not in data or not data["diagnosis"]:
                raise ValueError("Missing or empty diagnosis in AI response")

            print("[AI] Analysis successful")
            return data
            
        except Exception as e:
            err_str = str(e)
            is_eval = os.getenv("EVALUATION_MODE", "false").lower() == "true"
            
            err_str_lower = err_str.lower()
            is_timeout = "timeout" in err_str_lower
            
            if any(x in err_str_lower for x in ["429", "503", "404", "resourceexhausted", "unavailable", "timeout", "network error"]):
                if is_eval:
                    if is_timeout:
                        print("[AI] Gemini request timed out")
                    else:
                        print(f"[AI] Gemini API unavailable during evaluation: {e}")
                    raise RuntimeError("AI_SERVICE_UNAVAILABLE")
                    
            if attempt < max_attempts:
                # Check for 503 or generic retryable
                wait_time = 2 ** attempt
                print(f"[AI] Gemini API error (Attempt {attempt}): {e}")
                
                if time.time() + wait_time - global_start > total_budget_sec:
                    if is_timeout:
                        print("[AI] Gemini request timed out")
                    print("[AI] Total evaluation time limit exceeded before retry.")
                    raise RuntimeError("AI_SERVICE_UNAVAILABLE")
                    
                print(f"[AI] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"[AI] Gemini temporarily unavailable after {max_attempts} attempts.")
                if is_timeout:
                    print("[AI] Gemini request timed out")
                    raise RuntimeError("AI_SERVICE_UNAVAILABLE")
                raise RuntimeError("AI diagnosis failed safely")
