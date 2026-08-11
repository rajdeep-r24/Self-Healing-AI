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
from google.genai.errors import APIError

def diagnose_and_fix(traceback_text: str, source_code: str) -> dict:
    """
    Sends the traceback and source code to the AI engine to get a fix.
    Returns a dictionary with 'diagnosis' and 'fixed_code'.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set.")

    primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")
    
    client = genai.Client(api_key=api_key)
    
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

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
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
            
            data = json.loads(response.text)
            print("[AI] Analysis successful")
            return data
            
        except Exception as e:
            if attempt < max_attempts:
                # Check for 503 or generic retryable
                wait_time = 2 ** attempt
                print(f"[AI] Gemini API error (Attempt {attempt}): {e}")
                print(f"[AI] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"[AI] Gemini temporarily unavailable after {max_attempts} attempts.")
                raise RuntimeError("AI diagnosis failed safely")
