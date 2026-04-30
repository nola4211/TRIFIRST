"""Application entry point for running the TriFirst FastAPI app."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from trifirst.api.routes import router
from trifirst.database.db import init_db

app = FastAPI(title="TriFirst API")

# CORS middleware lets a browser frontend call this API from a different origin safely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# This startup event runs once when the server boots so required tables exist.
@app.on_event("startup")
def on_startup() -> None:
    """Initialize database schema at application startup."""
    init_db()


if __name__ == "__main__":
    # uvicorn is the web server that runs this FastAPI app locally or in production.
    uvicorn.run("trifirst.main:app", host="0.0.0.0", port=8000)
