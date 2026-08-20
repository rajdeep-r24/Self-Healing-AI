import os
import json
import time
from google import genai
from google.genai.errors import APIError
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class AIResponse(BaseModel):
    diagnosis: str
    fixed_code: str

def diagnose_and_fix(traceback_text: str, source_code: str) -> dict:
    """
    Sends the traceback and source code to the AI engine to get a fix.
    Returns a dictionary with 'diagnosis' and 'fixed_code'.
    Standardized strictly on GEMINI_* environment variables.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").replace("GEMINI_MODEL=", "").replace("=", "").strip() or "gemini-2.5-flash-lite"
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro").replace("GEMINI_FALLBACK_MODEL=", "").replace("=", "").strip() or "gemini-2.5-pro"
    demo_mode = os.getenv("SELF_HEALING_DEMO_MODE", "").lower() in ("true", "1", "yes")

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

    if demo_mode:
        # In Demo Mode: single primary attempt, single fallback attempt on error, no repeated retry loops
        models_to_try = [primary_model]
        if fallback_model and fallback_model != primary_model:
            models_to_try.append(fallback_model)

        last_error = None
        for attempt, model in enumerate(models_to_try, 1):
            try:
                print(f"[AI] Gemini request attempt {attempt}/{len(models_to_try)} (Model: {model})")
                response = client.models.generate_content(
                    model=model,
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
                last_error = e
                print(f"[AI] Attempt {attempt} failed: {e}")
                if attempt < len(models_to_try):
                    print(f"[AI] Switching to fallback model: {models_to_try[attempt]}")

        print(f"[AI] All models unavailable in demo mode.")
        if last_error and "503" in str(last_error):
            raise RuntimeError(f"AI_SERVICE_UNAVAILABLE: AI diagnosis failed safely: {last_error}")
        raise RuntimeError(f"AI diagnosis failed safely: {last_error}")

    else:
        # Normal production mode with exponential backoff retries
        max_attempts = 3
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"[AI] Gemini request attempt {attempt}/{max_attempts}")
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
                last_error = e
                if attempt < max_attempts:
                    wait_time = 2 ** attempt
                    print(f"[AI] Gemini API error (Attempt {attempt}): {e}")
                    print(f"[AI] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"[AI] Gemini temporarily unavailable after {max_attempts} attempts.")
                    if last_error and "503" in str(last_error):
                        raise RuntimeError(f"AI_SERVICE_UNAVAILABLE: AI diagnosis failed safely: {last_error}")
                    raise RuntimeError("AI diagnosis failed safely")
