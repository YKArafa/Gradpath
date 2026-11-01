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
from src.shared.models import Degree, Major, Student, Course, Transcript, Advisor
from src.analysis_controller import general_risk_analysis


async def run_analysis_tests():
    print("==================================================")
    print("TESTING FASTAPI ANALYSIS CONTROLLER (GENERAL RISK ANALYSIS)")
    print("==================================================")

    # 1. Initialize DB
    await init_db()

    # 2. Seed Test Courses
    async with AsyncSessionLocal() as session:
        # Create courses if not present
        courses_data = [
            {"code": "CS101", "title": "Programming I", "credit_hours": 6.0},
            {"code": "CS102", "title": "Programming II", "credit_hours": 6.0},
            {"code": "CS201", "title": "Data Structures", "credit_hours": 6.0},
            {"code": "MATH101", "title": "Calculus I", "credit_hours": 6.0},
            {"code": "MATH102", "title": "Calculus II", "credit_hours": 6.0},
            {"code": "SE301", "title": "Software Architecture", "credit_hours": 6.0},
        ]
        for c_data in courses_data:
            stmt = select(Course).where(Course.code == c_data["code"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                new_c = Course(
                    code=c_data["code"],
                    title=c_data["title"],
                    credit_hours=c_data["credit_hours"],
                    difficulty_level="medium",
                )
                session.add(new_c)
        await session.commit()

        # Create Degree with courses
        deg_stmt = select(Degree).where(Degree.name == "B.Sc. Computer Science")
        test_degree = (await session.execute(deg_stmt)).scalar_one_or_none()
        if not test_degree:
            test_degree = Degree(
                name="B.Sc. Computer Science",
                courses=["CS101", "CS102", "CS201", "MATH101", "MATH102"],
            )
            session.add(test_degree)
            await session.commit()
            await session.refresh(test_degree)

        # Create Major
        maj_stmt = select(Major).where(Major.name == "Software Engineering Major")
        test_major = (await session.execute(maj_stmt)).scalar_one_or_none()
        if not test_major:
            test_major = Major(
                name="Software Engineering Major",
                degree_id=test_degree.id,
                required_courses=["SE301"],
            )
            session.add(test_major)
            await session.commit()
            await session.refresh(test_major)

        # Student A: Enrolled Winter 2024, No Major, Transcript has Winter 2026 (begun), failed MATH101
        # Target finish: Spring 2028
        student_a_email = f"student_a_{int(datetime.now().timestamp())}@university.edu"
        student_a = Student(
            name="Alice Smith",
            email=student_a_email,
            institution="Tech Institute",
            time_of_enrollment=datetime(2024, 10, 1, tzinfo=timezone.utc),
            degree_id=test_degree.id,
            major_id=None,  # Undeclared major -> will add 122
            preferences={"finish_semester": "Spring 2028"},
            gpa=2.8,
        )
        session.add(student_a)
        await session.commit()
        await session.refresh(student_a)

        # Add transcript for Student A:
        # - Fall 2024 (Winter 2024): CS101 passed (4.0)
        # - Spring 2025: CS102 passed (3.5)
        # - Summer 2025: MATH101 failed (0.0) -> summer courses checked!
        # - Winter 2026: CS201 passed (3.0) -> current semester begun!
        transcript_a = Transcript(
            student_id=student_a.id,
            semesters=[
                {"semester": "Fall 2024", "courses": {"CS101": 4.0}},
                {"semester": "Spring 2025", "courses": {"CS102": 3.5}},
                {"semester": "Summer 2025", "courses": {"MATH101": 0.0}},
                {"semester": "Winter 2026", "courses": {"CS201": 3.0}},
            ],
        )
        session.add(transcript_a)
        await session.commit()

        # Student B: Enrolled Winter 2024, Has Major, Current Semester NOT begun in transcript
        student_b_email = f"student_b_{int(datetime.now().timestamp())}@university.edu"
        student_b = Student(
            name="Bob Jones",
            email=student_b_email,
            institution="Tech Institute",
            time_of_enrollment=datetime(2024, 10, 1, tzinfo=timezone.utc),
            degree_id=test_degree.id,
            major_id=test_major.id,  # Declared major
            preferences={"finish_semester": "Spring 2028"},
            gpa=3.5,
        )
        session.add(student_b)
        await session.commit()
        await session.refresh(student_b)

        # Transcript only up to Spring 2026 (Winter 2026 not begun yet)
        transcript_b = Transcript(
            student_id=student_b.id,
            semesters=[
                {"semester": "Fall 2024", "courses": {"CS101": 4.0}},
                {"semester": "Spring 2025", "courses": {"CS102": 3.5}},
            ],
        )
        session.add(transcript_b)
        await session.commit()

        student_a_id = student_a.id
        student_b_id = student_b.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Test Unauthenticated Request -> 401
        print("\n1. Verifying 401 Unauthorized for Unauthenticated Request:")
        unauth_res = await client.get(f"/analysis/general-risk-analysis/{student_a_id}")
        assert unauth_res.status_code == 401, f"Expected 401, got {unauth_res.status_code}"
        print("  [OK] GET /analysis/general-risk-analysis without auth returned 401 Unauthorized.")

        # 4. Authenticate Advisor
        print("\n2. Authenticating Advisor:")
        ts = int(datetime.now().timestamp())
        reg_res = await client.post(
            "/register",
            json={
                "name": "Prof. Ada Lovelace",
                "email": f"advisor_analysis_{ts}@univ.edu",
                "password": "Password123!",
                "institution": "Tech Institute",
            },
        )
        assert reg_res.status_code == 201, f"Advisor registration failed: {reg_res.text}"
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [OK] Advisor authenticated successfully.")

        # 5. Test Student A Risk Analysis (The Exact User Example Scenario)
        print("\n3. Testing Student A (Exact User Example Scenario):")
        # Reference date: October 30, 2026 (Winter 2026)
        ref_date = "2026-10-30T12:00:00Z"
        res_a = await client.get(
            f"/analysis/general-risk-analysis/{student_a_id}?now={ref_date}&finish_semester=Spring+2028",
            headers=headers,
        )
        assert res_a.status_code == 200, f"Expected 200, got {res_a.status_code}: {res_a.text}"
        data_a = res_a.json()

        print(f"  Current Semester: {data_a['current_semester']}")
        print(f"  Current Semester Index: {data_a['current_semester_index']}")
        print(f"  Has Begun Current Semester: {data_a['has_begun_current_semester']}")
        print(f"  Semesters Left: {data_a['semesters_left']}")
        print(f"  Remaining Semesters List: {data_a['remaining_semesters']}")
        print(f"  Credit Score Counter: {data_a['credit_score_counter']}")
        print(f"  Credits Per Semester Needed: {data_a['credits_per_semester_needed']}")
        print(f"  Risk Level: {data_a['risk_level']}")

        # Verify assertions:
        # Enrolled Winter 2024, Now is Winter 2026 -> Semester 5
        assert data_a["current_semester"] == "Winter 2026"
        assert data_a["current_semester_index"] == 5
        # Begun: Winter 2026 is in transcript -> True
        assert data_a["has_begun_current_semester"] is True
        # Exact prompt example: Winter 2026 begun, finishes Spring 2028 -> exactly 3 semesters!
        assert data_a["semesters_left"] == 3
        assert data_a["remaining_semesters"] == ["Spring 2027", "Winter 2027", "Spring 2028"]

        # Credits calculation:
        # - Failed course in summer: MATH101 (6.0 credits)
        # - Degree remaining: MATH102 (6.0 credits). (CS101, CS102, CS201 passed; MATH101 failed).
        # - No major: add 122.0
        # Total counter = 6.0 (failed) + 6.0 (MATH102 remaining) + 122.0 (no major) = 134.0
        # Credits per semester = 134.0 / 3 = 44.67
        assert data_a["breakdown"]["failed_courses_credits"] == 6.0
        assert data_a["breakdown"]["remaining_degree_credits"] == 6.0
        assert data_a["breakdown"]["major_credits_added"] == 122.0
        assert data_a["credit_score_counter"] == 134.0
        assert data_a["credits_per_semester_needed"] == 44.67
        assert data_a["risk_level"] == "High"
        print("  [OK] Student A verification passed with 100% accuracy matching prompt specifications.")

        # 6. Test Student B (Declared Major, Current Semester Not Begun)
        print("\n4. Testing Student B (Declared Major, Current Semester Not Begun):")
        res_b = await client.get(
            f"/analysis/general-risk-analysis/{student_b_id}?now={ref_date}&finish_semester=Spring+2028",
            headers=headers,
        )
        assert res_b.status_code == 200, f"Expected 200, got {res_b.status_code}: {res_b.text}"
        data_b = res_b.json()

        print(f"  Current Semester: {data_b['current_semester']}")
        print(f"  Has Begun Current Semester: {data_b['has_begun_current_semester']}")
        print(f"  Semesters Left: {data_b['semesters_left']}")
        print(f"  Remaining Semesters List: {data_b['remaining_semesters']}")
        print(f"  Credit Score Counter: {data_b['credit_score_counter']}")
        print(f"  Credits Per Semester Needed: {data_b['credits_per_semester_needed']}")

        # Assertions for Student B:
        # Not begun Winter 2026 -> remaining semesters starts at Winter 2026:
        # Winter 2026, Spring 2027, Winter 2027, Spring 2028 -> 4 semesters!
        assert data_b["has_begun_current_semester"] is False
        assert data_b["semesters_left"] == 4
        assert data_b["remaining_semesters"] == ["Winter 2026", "Spring 2027", "Winter 2027", "Spring 2028"]

        # Has Major: SE301 (6.0 credits). Degree remaining: CS201, MATH101, MATH102 (3 * 6.0 = 18.0).
        # Total counter = 18.0 + 6.0 = 24.0. No 122 added!
        assert data_b["has_major"] is True
        assert data_b["breakdown"]["major_credits_added"] == 6.0
        assert data_b["credit_score_counter"] == 24.0
        assert data_b["credits_per_semester_needed"] == 6.0  # 24.0 / 4 = 6.0
        assert data_b["risk_level"] == "Low"
        print("  [OK] Student B verification passed: major checked, unbegun semester included in count.")

        # 7. Test Direct Python Call
        print("\n5. Testing Direct Python Function Call (general_risk_analysis):")
        async with AsyncSessionLocal() as session:
            direct_result = await general_risk_analysis(
                student_id=student_a_id,
                session=session,
                now=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
                finish_semester="Spring 2028",
            )
            assert direct_result.student_id == student_a_id
            assert direct_result.semesters_left == 3
            assert direct_result.credit_score_counter == 134.0
            print("  [OK] Direct Python method call succeeded with expected results.")

        # 8. Test 404 for Non-Existent Student
        print("\n6. Testing 404 for Non-Existent Student:")
        bad_res = await client.get("/analysis/general-risk-analysis/999999", headers=headers)
        assert bad_res.status_code == 404
        print("  [OK] Returned 404 for non-existent student.")

    print("\n==================================================")
    print("ALL GENERAL RISK ANALYSIS TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_analysis_tests())

