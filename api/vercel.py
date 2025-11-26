from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os

app = FastAPI(title="LLM Analysis Quiz API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "LLM Analysis Quiz API is running"}

@app.get("/test")
async def test():
    return {"status": "ok", "message": "Test endpoint is working"}

@app.post("/task")
async def task():
    return {"status": "success", "message": "Task endpoint is working"}

# Vercel handler
handler = Mangum(app, lifespan="off")
