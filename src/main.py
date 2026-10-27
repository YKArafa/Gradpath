import sys
import asyncio
from contextlib import asynccontextmanager
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(course_router)
app.include_router(transcript_router)




@app.get("/", tags=["Health"])
async def root():
    return {"message": "GradPath API is running", "status": "healthy"}
