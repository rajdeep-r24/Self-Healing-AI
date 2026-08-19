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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

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
    total_budget_sec = 80.0 
    
    models_to_try = [("PRIMARY", primary_model)]
    if fallback_model:
        models_to_try.append(("FALLBACK", fallback_model))
        
    for attempt_idx, (role, current_model) in enumerate(models_to_try):
        elapsed = time.time() - global_start
        remaining = total_budget_sec - elapsed
        
        if remaining <= 0:
            print("[AI] Gemini request timed out (Total time limit reached)")
            raise RuntimeError("AI_SERVICE_UNAVAILABLE")
            
        current_req_timeout = min(30.0, remaining)
        current_req_timeout_ms = int(current_req_timeout * 1000)
        
        client = genai.Client(api_key=api_key, http_options={'timeout': current_req_timeout_ms})

        try:
            print(f"[AI] Gemini request attempt {attempt_idx+1}/{len(models_to_try)}")
            if role == "FALLBACK":
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
            
            # Print the error
            if is_timeout:
                print("[AI] Gemini request timed out")
            else:
                print(f"[AI] Gemini API error ({role}): {e}")
                
            # Decide if retryable
            is_retryable = any(x in err_str_lower for x in ["429", "503", "404", "resourceexhausted", "unavailable", "timeout", "network error"])
            
            if not is_retryable:
                print("[AI] Non-retryable error encountered.")
                raise RuntimeError("AI diagnosis failed safely")
                
            # If we exhausted all configured models
            if attempt_idx == len(models_to_try) - 1:
                print(f"[AI] Gemini temporarily unavailable after {len(models_to_try)} attempts.")
                if is_eval:
                    if is_timeout:
                        print("[AI] Gemini request timed out")
                    else:
                        print(f"[AI] Gemini API unavailable during evaluation: {e}")
                raise RuntimeError("AI_SERVICE_UNAVAILABLE")
                
            # Otherwise loop continues to the fallback model
