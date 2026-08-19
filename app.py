import logging
import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging to write to server.log
logging.basicConfig(
    filename="logs/server.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enterprise Self-Healing AI")

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"message": "Enterprise Self-Healing AI API"}

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
        logger.error(f"Unhandled exception in /process_data:\n{tb_str}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})