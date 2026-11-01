import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure server directory is in sys.path
SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Psycopg 3 async requires WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.shared.database import init_db
from src.auth_controller import router as auth_router
from src.student_controller import router as student_router
from src.course_controller import router as course_router
from src.transcript_controller import router as transcript_router
from src.analysis_controller import router as analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield


app = FastAPI(
    title="GradPath API",
    description="Academic degree planning and advising backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(course_router)
app.include_router(transcript_router)
app.include_router(analysis_router)




@app.get("/", tags=["Health"])
async def root():
    return {"message": "GradPath API is running", "status": "healthy"}
