import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

def log_server_error(msg: str):
    os.makedirs("logs", exist_ok=True)
    with open("logs/server.log", "a", encoding="utf-8") as f:
        f.write(f"ERROR - {msg}\n")
        f.flush()

app = FastAPI(title="Enterprise Self-Healing AI")

@app.get("/process_data")
async def process_data():
    try:
        user_data = {"username": "admin", "role": "superuser"}
        # INTENTIONAL BUG: "user_name" is a typo, the correct key is "username"
        greeting = f"Hello, {user_data['username']}!"
        return {"message": greeting}
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_server_error(f"Unhandled exception in /process_data:\n{tb_str}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

    