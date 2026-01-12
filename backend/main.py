import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers import chat

log_level = logging.DEBUG if settings.api_debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

for logger_name in ['backend', 'backend.services', 'backend.routers', 'backend.models']:
    logging.getLogger(logger_name).setLevel(log_level)

logger = logging.getLogger(__name__)
logger.info(f"Logging configurato con livello: {logging.getLevelName(log_level)}")

app = FastAPI(
    title="SmartOrder AI Backend",
    description="Backend FastAPI per sistema ordini basato su AI",
    version="1.0.0",
    debug=settings.api_debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "SmartOrder AI Backend",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "openai": "configured"
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level="info" if not settings.api_debug else "debug"
    )
