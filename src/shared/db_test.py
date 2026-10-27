import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Psycopg 3 async requires WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from src.shared.database import engine, AsyncSessionLocal, init_db
from src.shared.models import Degree, Major, Advisor, Course, Student, Transcript


EXPECTED_TABLES = {"advisor", "student", "course", "transcript", "major", "degree"}


async def verify_tables_in_database() -> None:
    """Check that all 6 required tables exist in the PostgreSQL schema."""
    print("\n--- Verifying Tables in Database ---")
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
            )
        )
        existing_tables = {row[0] for row in result.fetchall()}
        print(f"Tables currently in database: {sorted(list(existing_tables))}")

        missing = EXPECTED_TABLES - existing_tables
        if missing:
            raise RuntimeError(f"Missing required tables in database: {missing}")

        for tbl in sorted(list(EXPECTED_TABLES)):
            print(f"  [OK] Table '{tbl}' exists.")


async def verify_table_columns() -> None:
    """Verify columns for each of the 6 tables."""
    print("\n--- Verifying Columns for Each Table ---")
    async with engine.connect() as conn:
        for tbl in sorted(list(EXPECTED_TABLES)):
            res = await conn.execute(
                text(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :t "
                    "ORDER BY ordinal_position;"
                ),
                {"t": tbl}
            )
            cols = res.fetchall()
            col_summary = ", ".join([f"{c[0]} ({c[1]})" for c in cols])
            print(f"  [OK] '{tbl}' columns: {col_summary}")


async def test_crud_and_constraints() -> None:
    """Test inserting and querying data across all 6 tables."""
    print("\n--- Testing Data Insertion, Queries & Constraints ---")
    
    async with AsyncSessionLocal() as session:
        # 1. Degree
        test_degree = Degree(
            name="Bachelor of Science in Computer Science",
            courses=["CS101", "CS102", "MATH101"]
        )
        session.add(test_degree)
        await session.flush()
        print(f"  [OK] Inserted Degree: id={test_degree.id}, name='{test_degree.name}', courses={test_degree.courses}")

        # 2. Major (references Degree)
        test_major = Major(
            name="Artificial Intelligence & Machine Learning",
            degree_id=test_degree.id,
            required_courses=["CS101", "CS201", "MATH101"]
        )
        session.add(test_major)
        await session.flush()
        print(
            f"  [OK] Inserted Major: id={test_major.id}, name='{test_major.name}', "
            f"required_courses={test_major.required_courses}"
        )

        # 3. Advisor (unique email)
        unique_email = f"ada.lovelace_{int(datetime.now().timestamp())}@university.edu"
        test_advisor = Advisor(
            name="Dr. Ada Lovelace",
            email=unique_email,
            password_hash="argon2id$v=19$m=65536,t=3,p=4$hashed_secret_placeholder",
            institution="University of Computing",
        )
        session.add(test_advisor)
        await session.flush()
        print(f"  [OK] Inserted Advisor: id={test_advisor.id}, email='{test_advisor.email}'")

        # 4. Courses
        course_1 = Course(
            code=f"CS101_{int(datetime.now().timestamp()) % 10000}",
            title="Introduction to Programming & Problem Solving",
            description="Core concepts of imperative and functional programming",
            credit_hours=3.0,
            difficulty_level="low",
            prerequisites=[]
        )
        course_2 = Course(
            code=f"CS201_{int(datetime.now().timestamp()) % 10000}",
            title="Data Structures & Algorithms",
            description="Advanced data organization and algorithmic efficiency",
            credit_hours=4.0,
            difficulty_level="hard",
            prerequisites=[course_1.code]
        )
        session.add_all([course_1, course_2])
        await session.flush()
        print(
            f"  [OK] Inserted Courses: {course_1.code} ({course_1.credit_hours} cr, diff={course_1.difficulty_level}), "
            f"{course_2.code} ({course_2.credit_hours} cr, diff={course_2.difficulty_level})"
        )

        # 5. Student (references Advisor, Degree, Major)
        test_student = Student(
            advisor_id=test_advisor.id,
            name="Grace Hopper",
            email="grace.hopper@student.edu",
            institution="University of Computing",
            time_of_enrollment=datetime.now(timezone.utc),
            degree_id=test_degree.id,
            major_id=test_major.id,  # Optional major included
            preferences={
                "preferred_mode": "hybrid",
                "focus_area": "compilers",
                "max_credits_per_semester": 18
            },
            gpa=3.95
        )
        session.add(test_student)
        await session.flush()
        print(
            f"  [OK] Inserted Student: id={test_student.id}, name='{test_student.name}', "
            f"GPA={test_student.GPA}, preferences={test_student.preferences}"
        )

        # 5b. Student with major_id=None (testing optional major_id)
        test_student_no_major = Student(
            advisor_id=test_advisor.id,
            name="Alan Turing",
            email="alan.turing@student.edu",
            institution="University of Computing",
            time_of_enrollment=datetime.now(timezone.utc),
            degree_id=test_degree.id,
            major_id=None,  # Optional major omitted
            preferences={"focus_area": "cryptography"},
            gpa=4.0
        )
        session.add(test_student_no_major)
        await session.flush()
        print(f"  [OK] Inserted Student with optional major_id=None: id={test_student_no_major.id}")

        # 6. Transcript (references Student)
        # Array containing semester (string) and map of course_id and numeric grade value
        transcript_data = [
            {
                "semester": "Fall 2024",
                "courses": {
                    str(course_1.id): 4.0
                }
            },
            {
                "semester": "Spring 2025",
                "courses": {
                    str(course_2.id): 3.9
                }
            }
        ]
        test_transcript = Transcript(
            student_id=test_student.id,
            semesters=transcript_data
        )
        session.add(test_transcript)
        await session.flush()
        print(
            f"  [OK] Inserted Transcript: id={test_transcript.id}, student_id={test_transcript.student_id}, "
            f"semesters_count={len(test_transcript.semesters)}"
        )

        await session.commit()
        print("  [OK] All records committed successfully.")

        # Test query and relationships
        stmt = select(Student).where(Student.id == test_student.id)
        res = await session.execute(stmt)
        queried_student = res.scalar_one()
        assert queried_student.name == "Grace Hopper"
        assert queried_student.GPA == 3.95
        assert len(queried_student.preferences) == 3
        print(f"  [OK] Verified queried student data matches inserted data.")

        # Test unique email constraint on Advisor
        duplicate_advisor = Advisor(
            name="Duplicate Advisor",
            email=unique_email,  # duplicate email
            password_hash="hash",
            institution="Another Uni"
        )
        session.add(duplicate_advisor)
        try:
            await session.flush()
            raise RuntimeError("Unique email constraint test failed: duplicate was allowed!")
        except IntegrityError:
            await session.rollback()
            print("  [OK] Unique constraint on Advisor.email properly enforced.")


async def main() -> None:
    print("==================================================")
    print("GRADPATH DATABASE INITIALIZATION & VERIFICATION")
    print("==================================================")
    
    # 1. Initialize tables (creates degree, major, advisor, course, student, transcript)
    print("\nStep 1: Running init_db()...")
    await init_db()
    print("Database tables created / verified successfully.")

    # 2. Check table existence
    print("\nStep 2: Verifying table schemas...")
    await verify_tables_in_database()
    await verify_table_columns()

    # 3. Test insertions and constraints
    print("\nStep 3: Running CRUD and constraint tests...")
    await test_crud_and_constraints()

    print("\n==================================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(engine.dispose())
