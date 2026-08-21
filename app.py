import logging
import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging to write to server.log
logging.basicConfig(
    filename="logs/server.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__())

app = FastAPI()

def get_template(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "templates", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    try:
        user_data = {"username": "admin", "role": "superuser"}
        # INTENTIONAL BUG: "user_name" is a typo, the correct key is "username"
        greeting = f"Hello, {user_data['username']}!"
        content = get_template("index.html")
        return HTMLResponse(content=content or f"<h1>{greeting}</h1>", status_code=200)
    except Exception as e:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(f"Unhandled exception in /:\n{tb_str}")
        err_content = get_template("error_500.html")
        return HTMLResponse(content=err_content or "<h1>500 Internal Server Error</h1>", status_code=500)

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