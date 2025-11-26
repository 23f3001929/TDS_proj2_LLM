# app/main.py
# Entry point for FastAPI. Verifies secret and invokes solver.
import asyncio
# Ensure Windows Proactor event loop policy for subprocess support on Windows dev machines
try:
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
except Exception:
    pass

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.config import SECRET
from app.solver import handle_quiz_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Analysis Quiz Endpoint")


@app.post("/task")
async def task_endpoint(request: Request):
    """
    Endpoint required by the project.
    - Expects JSON with keys: email, secret, url
    - Returns HTTP 200 if secret matches (spec requirement).
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(payload, dict) or "email" not in payload or "secret" not in payload or "url" not in payload:
        raise HTTPException(status_code=400, detail="Missing fields: email, secret, url required")

    if str(payload.get("secret")) != str(SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        # Run the quiz handler. We run within asyncio and the solver uses asyncio.to_thread
        result = await handle_quiz_request(payload)
    except Exception:
        # Log the traceback to make it visible in provider logs
        logger.exception("Exception while handling quiz request")
        return JSONResponse(status_code=200, content={"status": "error", "detail": "internal error (see logs)"})

    return JSONResponse(status_code=200, content={"status": "ok", "result": result})
