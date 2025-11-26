import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from mangum import Mangum

app = FastAPI(title="LLM Analysis Quiz Endpoint")

# Simple test endpoint
@app.get("/test")
async def test():
    return {"status": "ok", "message": "API is working!"}

@app.post("/task")
async def task_endpoint(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Received payload: {payload}")
        
        # Basic validation
        if not isinstance(payload, dict) or "email" not in payload or "secret" not in payload or "url" not in payload:
            raise HTTPException(status_code=400, detail="Missing required fields")
            
        # Verify secret (temporarily disabled for testing)
        # if str(payload.get("secret")) != os.getenv("SECRET", "default-secret"):
        #     return JSONResponse(
        #         status_code=403,
        #         content={"status": "error", "detail": "Invalid secret"}
        #     )
            
        return {"status": "success", "message": "Request received", "data": payload}
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)}
        )

# Vercel handler
handler = Mangum(app)
