import os
import sys
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Load environment variables from server root or project root
SERVER_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
if SERVER_ENV.exists():
    load_dotenv(SERVER_ENV)
load_dotenv()

# Psycopg 3 async requires WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql:"):
    DATABASE_URL = re.sub(r"^postgresql:", "postgresql+psycopg:", DATABASE_URL)

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True)


from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession
from src.shared.models import Base, Degree, Major, Course

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


def get_engine() -> AsyncEngine:
    return engine


async def get_session() -> AsyncSession:
    """Dependency / generator for async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def seed_default_academic_programs() -> None:
    """Seeds default academic degree programs, courses, and majors if the degree table is empty."""
    async with AsyncSessionLocal() as session:
        # Check if degrees already exist
        res = await session.execute(select(func.count(Degree.id)))
        degree_count = res.scalar() or 0
        if degree_count > 0:
            return

        # 1. Baseline Courses
        baseline_courses = [
            ("CS101", "Introduction to Computer Science", 4.0),
            ("CS102", "Data Structures & Algorithms", 4.0),
            ("CS201", "Object-Oriented Programming", 4.0),
            ("CS202", "Computer Architecture & Organization", 4.0),
            ("CS203", "Operating Systems", 4.0),
            ("CS301", "Database Systems", 4.0),
            ("CS302", "Computer Networks", 4.0),
            ("CS303", "Software Engineering", 4.0),
            ("MATH101", "Calculus I", 4.0),
            ("MATH102", "Calculus II", 4.0),
            ("MATH201", "Linear Algebra", 3.0),
            ("MATH202", "Discrete Mathematics", 3.0),
            ("SE301", "Software Architecture & Design", 4.0),
            ("SE302", "Software Testing & QA", 4.0),
            ("SE401", "Cloud Computing & DevOps", 4.0),
            ("AI301", "Artificial Intelligence Fundamentals", 4.0),
            ("AI302", "Machine Learning", 4.0),
            ("AI401", "Deep Learning & NLP", 4.0),
            ("CYB301", "Information Security & Cryptography", 4.0),
            ("CYB302", "Network & Systems Security", 4.0),
            ("BBI101", "Business Informatics Principles", 4.0),
            ("BBI102", "Enterprise Architecture & ERP", 4.0),
            ("BBI201", "Business Process Management", 4.0),
            ("ME101", "Engineering Mechanics & Statics", 4.0),
            ("ME102", "Thermodynamics & Fluid Dynamics", 4.0),
            ("ME201", "Materials Science", 4.0),
        ]

        for code, title, credits in baseline_courses:
            existing = await session.scalar(select(Course).where(Course.code == code))
            if not existing:
                session.add(Course(code=code, title=title, credit_hours=credits, difficulty_level="medium"))
        await session.flush()

        # 2. Baseline Degrees
        cs_degree = Degree(
            name="Bachelor of Computer Science",
            courses=[
                "CS101", "CS102", "CS201", "CS202", "CS203", "CS301",
                "CS302", "CS303", "MATH101", "MATH102", "MATH201", "MATH202"
            ],
        )
        bbi_degree = Degree(
            name="Bachelor of Business Informatics",
            courses=["BBI101", "BBI102", "BBI201", "CS101", "CS301", "MATH201"],
        )
        me_degree = Degree(
            name="Bachelor of Mechanical Engineering",
            courses=["ME101", "ME102", "ME201", "MATH101", "MATH102", "MATH201"],
        )
        session.add_all([cs_degree, bbi_degree, me_degree])
        await session.flush()

        # 3. Baseline Majors linked to corresponding Degree IDs
        baseline_majors = [
            Major(
                name="Software Engineering Major",
                degree_id=cs_degree.id,
                required_courses=["SE301", "SE302", "SE401"],
            ),
            Major(
                name="Artificial Intelligence & Data Science Major",
                degree_id=cs_degree.id,
                required_courses=["AI301", "AI302", "AI401"],
            ),
            Major(
                name="Cybersecurity & Networks Major",
                degree_id=cs_degree.id,
                required_courses=["CYB301", "CYB302"],
            ),
            Major(
                name="Enterprise Systems & Analytics Major",
                degree_id=bbi_degree.id,
                required_courses=["BBI102", "CS301"],
            ),
            Major(
                name="Mechatronics & Robotics Major",
                degree_id=me_degree.id,
                required_courses=["ME101", "CS101"],
            ),
        ]
        session.add_all(baseline_majors)
        await session.commit()


async def init_db() -> None:
    """Create all tables registered with Base.metadata if they do not exist and seed catalog."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE degree ADD COLUMN IF NOT EXISTS courses JSONB NOT NULL DEFAULT '[]'::jsonb;")
        )
        await conn.execute(
            text("ALTER TABLE course ADD COLUMN IF NOT EXISTS difficulty_level VARCHAR(20) NOT NULL DEFAULT 'medium';")
        )

    # Seed baseline academic degrees & majors if empty
    await seed_default_academic_programs()


async def async_main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("select 'hello world'"))
        print(result.fetchall())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(async_main())