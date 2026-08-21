import logging
import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging to write to server.log
logging.basicConfig(
    filename="logs/server.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Self-Healing AI Portal</h1>"

@app.get("/process_data")
async def process_data():
    try:
        user_data = {"username": "admin", "role": "superuser"}
        # INTENTIONAL BUG: "user_name" is a typo, the correct key is "username"
        greeting = f"Hello, {user_data['username']}!"
        return {"message": greeting, "status": "healthy", "user": user_data["username"]}
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Unhandled exception in /process_data:\n{tb_str}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

    
# Dummy change
