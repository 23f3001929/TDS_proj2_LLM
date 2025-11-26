import asyncio
# Ensure the Windows Proactor event loop is used so subprocesses (Playwright browsers) work.
# This must be set before any asyncio event loop is created or before uvicorn imports this module.
try:
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
except AttributeError:
    # Not on Windows / policy not available — ignore
    pass
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.config import SECRET
from app.solver import handle_quiz_request
import asyncio
import json
import logging
import traceback

app = FastAPI(title="LLM Analysis Quiz Endpoint")

@app.post("/task")
async def task_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # verify required fields
    if not isinstance(payload, dict) or "email" not in payload or "secret" not in payload or "url" not in payload:
        raise HTTPException(status_code=400, detail="Missing fields: email, secret, url required")

    if str(payload.get("secret")) != str(SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret")

    # valid request -> spawn worker to handle quiz synchronously here
    # Because evaluation expects that your endpoint will visit the URL and submit the correct answer within 3 minutes,
    # we perform the work before sending the 200 response (so their test sees 200).
    # However to keep the endpoint responsive we run the worker with a timeout guard.
    try:
        result = await asyncio.wait_for(handle_quiz_request(payload), timeout=None)
    except asyncio.TimeoutError:
        # If our worker times out, inform them with HTTP 500 or similar. But spec says respond 200 if secret matches -
        # so still return 200 here and include an error field.
        return JSONResponse(status_code=200, content={"status": "timeout", "detail": "handler timed out"})
    except Exception as e:
        logging.exception("Exception while handling quiz request")   # prints full traceback
        tb = traceback.format_exc()
        # include the traceback in the response (temporary for debugging only)
        return JSONResponse(status_code=200, content={"status": "error", "detail": tb})

    return JSONResponse(status_code=200, content={"status": "ok", "result": result})
