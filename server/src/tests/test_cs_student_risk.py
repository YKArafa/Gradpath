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

import httpx
from sqlalchemy import select
from src.main import app
from src.shared.database import init_db, AsyncSessionLocal
from src.shared.models import Degree, Major, Student, Course, Transcript
from src.analysis_controller import general_risk_analysis


async def run_cs_risk_simulation():
    print("==================================================")
    print("CS STUDENT RISK SIMULATION (NO MAJOR, 75% COURSES, 2 FAILED)")
    print("==================================================")

    await init_db()

    # Define the exact courses requested by the user:
    courses_spec = [
        # 8 credit hour (2 courses)
        ("Mathematics I", 8.0, "MATH101"),
        ("Programming II", 8.0, "CS102"),
        # 6 credit hour (3 courses)
        ("Programming I", 6.0, "CS101"),
        ("Databases", 6.0, "CS202"),
        ("Data Structures & Algorithms", 6.0, "CS201"),
        # 5 credit hour (6 courses)
        ("Operating Systems", 5.0, "CS301"),
        ("Theoretical Computer Science", 5.0, "CS302"),
        ("Computer Organization", 5.0, "CS203"),
        ("Computer Networks", 5.0, "CS303"),
        ("Physics", 5.0, "PHYS101"),
        ("Digital Logic Design", 5.0, "ENGR101"),
        # 4 credit hour (8 courses)
        ("Mathematics II", 4.0, "MATH102"),
        ("Mathematics III", 4.0, "MATH201"),
        ("Mathematics IV", 4.0, "MATH202"),
        ("Software Engineering", 4.0, "SE301"),
        ("Analysis and Design of Algorithms", 4.0, "CS304"),
        ("Information Security", 4.0, "CS401"),
        ("Introduction to Data Science", 4.0, "CS402"),
        ("Introduction to Media Informatics", 4.0, "CS403"),
        # 2 credit hour (8 courses)
        ("English for Academic Purposes and Study Skills", 2.0, "LANG101"),
        ("German 1", 2.0, "GER101"),
        ("Scientific Methods", 2.0, "GEN101"),
        ("German 2", 2.0, "GER102"),
        ("Communication and Presentation Skills", 2.0, "GEN102"),
        ("German 3", 2.0, "GER201"),
        ("Research Paper Writing", 2.0, "GEN201"),
        ("German 4", 2.0, "GER202"),
    ]

    total_courses_count = len(courses_spec)
    assert total_courses_count == 27, f"Expected 27 courses, got {total_courses_count}"
    total_degree_credits = sum(c[1] for c in courses_spec)
    print(f"Total courses in Degree: {total_courses_count}")
    print(f"Total credit hours in Degree: {total_degree_credits} credits")

    async with AsyncSessionLocal() as session:
        # 1. Create Course records in DB
        for title, credits, code in courses_spec:
            stmt = select(Course).where(Course.code == code)
            c_db = (await session.execute(stmt)).scalar_one_or_none()
            if not c_db:
                c_db = Course(
                    code=code,
                    title=title,
                    credit_hours=credits,
                    difficulty_level="medium",
                )
                session.add(c_db)
            else:
                c_db.title = title
                c_db.credit_hours = credits
        await session.commit()

        # 2. Create Degree with all 27 courses
        degree_name = "Bachelor of Science in Computer Science"
        deg_stmt = select(Degree).where(Degree.name == degree_name).limit(1)
        cs_degree = (await session.execute(deg_stmt)).scalars().first()
        degree_courses_list = [c[0] for c in courses_spec]  # List of course titles
        if not cs_degree:
            cs_degree = Degree(
                name=degree_name,
                courses=degree_courses_list,
            )
            session.add(cs_degree)
            await session.commit()
            await session.refresh(cs_degree)
        else:
            cs_degree.courses = degree_courses_list
            await session.commit()
            await session.refresh(cs_degree)

        # 3. Create Student (Computer Science, NO MAJOR)
        # 75% of 27 courses = 20 courses in transcript (round(27 * 0.75) = 20)
        # 7 courses remaining not taken (27 - 20 = 7)
        courses_in_transcript = courses_spec[:20]  # First 20 courses taken
        courses_remaining = courses_spec[20:]      # Remaining 7 courses not taken

        # 2 failed courses out of the 20:
        # e.g., Theoretical Computer Science (5.0 credits) and Mathematics II (4.0 credits)
        failed_course_1 = courses_in_transcript[6]   # Theoretical Computer Science (5.0)
        failed_course_2 = courses_in_transcript[11]  # Mathematics II (4.0)
        failed_credits_expected = failed_course_1[1] + failed_course_2[1]  # 5 + 4 = 9.0 credits

        remaining_courses_credits = sum(c[1] for c in courses_remaining)
        # Remaining 7 courses:
        # Information Security (4), Intro Data Science (4), Intro Media Informatics (4),
        # Communication & Presentation (2), German 3 (2), Research Paper Writing (2), German 4 (2)
        # Sum = 4 + 4 + 4 + 2 + 2 + 2 + 2 = 20 credits

        ts = int(datetime.now().timestamp())
        student = Student(
            name="John Doe (CS Student)",
            email=f"cs_student_{ts}@univ.edu",
            institution="Faculty of Media Engineering & Technology",
            time_of_enrollment=datetime(2024, 10, 1, tzinfo=timezone.utc),  # Enrolled Winter 2024
            degree_id=cs_degree.id,
            major_id=None,  # NO MAJOR!
            preferences={"finish_semester": "Spring 2028"},
            gpa=2.5,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)

        # 4. Build Transcript across semesters:
        # Semester 1 (Winter 2024): 4 courses
        # Semester 2 (Spring 2025): 4 courses
        # Semester 3 (Summer 2025): 2 courses (Summer courses checked too)
        # Semester 4 (Winter 2025): 4 courses
        # Semester 5 (Spring 2026): 3 courses
        # Semester 6 (Winter 2026 - Current): 3 courses (including 2 failed courses)
        s1_courses = {courses_in_transcript[0][0]: 3.5, courses_in_transcript[1][0]: 3.0, courses_in_transcript[2][0]: 3.7, courses_in_transcript[3][0]: 3.3}
        s2_courses = {courses_in_transcript[4][0]: 3.0, courses_in_transcript[5][0]: 3.2, courses_in_transcript[7][0]: 3.0, courses_in_transcript[8][0]: 3.5}
        s3_courses = {courses_in_transcript[9][0]: 3.0, courses_in_transcript[10][0]: 2.8}  # Summer
        s4_courses = {courses_in_transcript[12][0]: 3.0, courses_in_transcript[13][0]: 3.5, courses_in_transcript[14][0]: 3.2, courses_in_transcript[15][0]: 3.0}
        s5_courses = {courses_in_transcript[16][0]: 3.0, courses_in_transcript[17][0]: 3.5, courses_in_transcript[18][0]: 3.0}
        # Semester 6 (Winter 2026): includes the 2 failed courses (grade 0.0)
        s6_courses = {
            courses_in_transcript[19][0]: 3.0,
            failed_course_1[0]: 0.0,  # FAILED Theoretical Computer Science (5.0 credits)
            failed_course_2[0]: 0.0,  # FAILED Mathematics II (4.0 credits)
        }

        transcript = Transcript(
            student_id=student.id,
            semesters=[
                {"semester": "Fall 2024", "courses": s1_courses},
                {"semester": "Spring 2025", "courses": s2_courses},
                {"semester": "Summer 2025", "courses": s3_courses},
                {"semester": "Winter 2025", "courses": s4_courses},
                {"semester": "Spring 2026", "courses": s5_courses},
                {"semester": "Winter 2026", "courses": s6_courses},
            ],
        )
        session.add(transcript)
        await session.commit()

        # 5. Execute general_risk_analysis
        result = await general_risk_analysis(
            student_id=student.id,
            session=session,
            now=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
            finish_semester="Spring 2028",
        )

        print("\n--- RESULTS OF RISK ANALYSIS ---")
        print(f"Student: {result.student_name} (ID: {result.student_id})")
        print(f"Current Semester: {result.current_semester} (Semester #{result.current_semester_index})")
        print(f"Target Finish Semester: {result.finish_semester}")
        print(f"Has Begun Current Semester: {result.has_begun_current_semester}")
        print(f"Semesters Left: {result.semesters_left}")
        print(f"Remaining Regular Semesters: {result.remaining_semesters}")
        print(f"Credit Score Counter: {result.credit_score_counter:.2f} credits")
        print(f"  - Failed Courses Credits: {result.breakdown['failed_courses_credits']:.2f}")
        print(f"  - Remaining Degree Courses Credits: {result.breakdown['remaining_degree_credits']:.2f}")
        print(f"  - Undeclared Major Addition: {result.breakdown['major_credits_added']:.2f}")
        print(f"Credits Needed Per Remaining Semester: {result.credits_per_semester_needed:.2f} credits/sem")
        print(f"Standard Load: {result.standard_credits_per_semester:.2f} credits/sem")
        print(f"Risk Level: {result.risk_level}")
        print(f"Summary: {result.summary}")

        return result


if __name__ == "__main__":
    asyncio.run(run_cs_risk_simulation())

