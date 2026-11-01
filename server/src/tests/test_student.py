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
from src.shared.database import engine, init_db, AsyncSessionLocal
from src.shared.models import Degree, Major


async def run_student_tests():
    print("==================================================")
    print("TESTING FASTAPI STUDENT CONTROLLER AUTH ENFORCEMENT")
    print("==================================================")

    # 1. Initialize database schema
    await init_db()

    # 2. Seed a degree and major if needed
    async with AsyncSessionLocal() as session:
        degree_res = await session.execute(select(Degree).limit(1))
        test_degree = degree_res.scalar_one_or_none()
        if not test_degree:
            test_degree = Degree(name="Bachelor of Computer Science")
            session.add(test_degree)
            await session.commit()
            await session.refresh(test_degree)

        major_res = await session.execute(select(Major).where(Major.degree_id == test_degree.id).limit(1))
        test_major = major_res.scalar_one_or_none()
        if not test_major:
            test_major = Major(
                name="Software Engineering",
                degree_id=test_degree.id,
                required_courses=["CS101", "CS102"]
            )
            session.add(test_major)
            await session.commit()
            await session.refresh(test_major)

        degree_id = test_degree.id
        major_id = test_major.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Test Unauthenticated Requests (Every method must return 401 Unauthorized)
        print("\n1. Verifying 401 Unauthorized for Unauthenticated Requests on ALL Methods:")

        # POST /students without auth
        unauth_post = await client.post("/students", json={"name": "No Auth", "email": "noauth@test.edu", "degree_id": degree_id})
        assert unauth_post.status_code == 401, f"Expected 401, got {unauth_post.status_code}"
        print("  [OK] POST /students without auth returned 401 Unauthorized.")

        # GET /students without auth
        unauth_list = await client.get("/students")
        assert unauth_list.status_code == 401, f"Expected 401, got {unauth_list.status_code}"
        print("  [OK] GET /students without auth returned 401 Unauthorized.")

        # GET /students/{id} without auth
        unauth_get_id = await client.get("/students/1")
        assert unauth_get_id.status_code == 401, f"Expected 401, got {unauth_get_id.status_code}"
        print("  [OK] GET /students/{id} without auth returned 401 Unauthorized.")

        # GET /students/by-email/{email} without auth
        unauth_get_email = await client.get("/students/by-email/test@test.edu")
        assert unauth_get_email.status_code == 401, f"Expected 401, got {unauth_get_email.status_code}"
        print("  [OK] GET /students/by-email/{email} without auth returned 401 Unauthorized.")

        # GET /students/my/students without auth
        unauth_my = await client.get("/students/my/students")
        assert unauth_my.status_code == 401, f"Expected 401, got {unauth_my.status_code}"
        print("  [OK] GET /students/my/students without auth returned 401 Unauthorized.")

        # GET /students/advisor/{advisor_id} without auth
        unauth_adv = await client.get("/students/advisor/1")
        assert unauth_adv.status_code == 401, f"Expected 401, got {unauth_adv.status_code}"
        print("  [OK] GET /students/advisor/{advisor_id} without auth returned 401 Unauthorized.")

        # 4. Register and authenticate advisor
        print("\n2. Authenticating Advisor...")
        timestamp = int(datetime.now().timestamp())
        advisor_email = f"auth_advisor_{timestamp}@university.edu"
        reg_res = await client.post(
            "/register",
            json={
                "name": "Prof. Margaret Hamilton",
                "email": advisor_email,
                "password": "AdvisorPassword123!",
                "institution": "MIT CSAIL",
            }
        )
        assert reg_res.status_code == 201, f"Advisor registration failed: {reg_res.text}"
        auth_data = reg_res.json()
        advisor_token = auth_data["access_token"]
        advisor_id = auth_data["advisor"]["id"]
        auth_headers = {"Authorization": f"Bearer {advisor_token}"}
        print(f"  [OK] Advisor authenticated: ID {advisor_id}, Institution: MIT CSAIL")

        # 5. Test Authenticated Creation
        print("\n3. Testing Authenticated Student Creation:")
        student_email = f"student_{timestamp}@mit.edu"
        res = await client.post(
            "/students",
            json={
                "name": "John von Neumann",
                "email": student_email,
                "degree_id": degree_id,
                "major_id": major_id,
                "preferences": {"interests": ["computer architecture", "game theory"]},
                "GPA": 3.99,
            },
            headers=auth_headers
        )
        assert res.status_code == 201, f"Creation failed: {res.text}"
        student_data = res.json()
        student_id = student_data["id"]
        assert student_data["advisor_id"] == advisor_id
        assert student_data["institution"] == "MIT CSAIL"
        print(f"  [OK] Created student ID {student_id} successfully under authenticated advisor {advisor_id}.")

        # 6. Test Authenticated Getters
        print("\n4. Testing Authenticated Getter Methods:")
        # GET /students/{id}
        get_id_res = await client.get(f"/students/{student_id}", headers=auth_headers)
        assert get_id_res.status_code == 200
        assert get_id_res.json()["name"] == "John von Neumann"
        print(f"  [OK] Authenticated GET /students/{student_id} succeeded.")

        # GET /students/by-email/{email}
        get_email_res = await client.get(f"/students/by-email/{student_email}", headers=auth_headers)
        assert get_email_res.status_code == 200
        assert get_email_res.json()["id"] == student_id
        print(f"  [OK] Authenticated GET /students/by-email/{student_email} succeeded.")

        # GET /students/my/students
        my_res = await client.get("/students/my/students", headers=auth_headers)
        assert my_res.status_code == 200
        assert any(s["id"] == student_id for s in my_res.json())
        print(f"  [OK] Authenticated GET /students/my/students succeeded.")

        # GET /students/advisor/{advisor_id}
        adv_res = await client.get(f"/students/advisor/{advisor_id}", headers=auth_headers)
        assert adv_res.status_code == 200
        assert any(s["id"] == student_id for s in adv_res.json())
        print(f"  [OK] Authenticated GET /students/advisor/{advisor_id} succeeded.")

        # GET /students (list)
        list_res = await client.get("/students", headers=auth_headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1
        print(f"  [OK] Authenticated GET /students succeeded.")

        # 7. Test Student Editing (PUT & PATCH)
        print("\n5. Testing Student Editing (PUT & PATCH):")

        # Unauthenticated edit attempt (Expected 401)
        unauth_patch = await client.patch(f"/students/{student_id}", json={"GPA": 3.70})
        assert unauth_patch.status_code == 401, f"Expected 401, got {unauth_patch.status_code}"
        print("  [OK] Unauthenticated edit attempt correctly rejected with 401 Unauthorized.")

        # Partial edit via PATCH
        patch_payload = {
            "GPA": 4.0,
            "preferences": {"interests": ["quantum computing", "cybernetics"], "honors": True},
            "name": "Dr. John von Neumann (Updated)"
        }
        patch_res = await client.patch(f"/students/{student_id}", json=patch_payload, headers=auth_headers)
        assert patch_res.status_code == 200, f"PATCH failed: {patch_res.text}"
        patched_data = patch_res.json()
        assert patched_data["gpa"] == 4.0
        assert patched_data["name"] == "Dr. John von Neumann (Updated)"
        assert patched_data["preferences"]["honors"] is True
        print(f"  [OK] PATCH /students/{student_id} succeeded: GPA={patched_data['gpa']}, Name='{patched_data['name']}'")

        # Full edit via PUT
        put_payload = {
            "name": "John von Neumann",
            "email": student_email,
            "degree_id": degree_id,
            "major_id": None,  # unassign major
            "GPA": 3.98,
            "preferences": {"track": "systems"}
        }
        put_res = await client.put(f"/students/{student_id}", json=put_payload, headers=auth_headers)
        assert put_res.status_code == 200, f"PUT failed: {put_res.text}"
        put_data = put_res.json()
        assert put_data["major_id"] is None
        assert put_data["major_name"] is None
        assert put_data["gpa"] == 3.98
        print(f"  [OK] PUT /students/{student_id} succeeded: major unassigned, GPA updated to 3.98.")

        # Non-existent student edit (Expected 404)
        nf_edit = await client.patch("/students/999999", json={"GPA": 3.5}, headers=auth_headers)
        assert nf_edit.status_code == 404
        print(f"  [OK] Edit non-existent student correctly returned 404: {nf_edit.json()['detail']}")

    print("\n==================================================")
    print("ALL AUTH ENFORCEMENT, GETTER & EDIT TESTS PASSED!")

    print("==================================================")


if __name__ == "__main__":
    try:
        asyncio.run(run_student_tests())
    finally:
        asyncio.run(engine.dispose())
