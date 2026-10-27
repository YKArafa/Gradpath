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
from src.shared.models import Degree, Major, Student, Advisor


async def run_transcript_tests():
    print("==================================================")
    print("TESTING FASTAPI TRANSCRIPT CONTROLLER (GET, ADD, EDIT)")
    print("==================================================")

    # 1. Initialize database schema
    await init_db()

    # 2. Seed student for transcript tests if needed
    async with AsyncSessionLocal() as session:
        # Check degree
        degree_res = await session.execute(select(Degree).limit(1))
        test_degree = degree_res.scalar_one_or_none()
        if not test_degree:
            test_degree = Degree(name="Bachelor of Science in Engineering", courses=["CS101", "CS102"])
            session.add(test_degree)
            await session.commit()
            await session.refresh(test_degree)

        # Check student
        student_res = await session.execute(select(Student).limit(1))
        test_student = student_res.scalar_one_or_none()
        if not test_student:
            test_student = Student(
                name="Katherine Johnson",
                email=f"kjohnson_{int(datetime.now().timestamp())}@student.edu",
                institution="NASA Langley Research Center",
                time_of_enrollment=datetime.now(timezone.utc),
                degree_id=test_degree.id,
                major_id=None,
                preferences={"focus": "orbital mechanics"},
                gpa=3.99,
            )
            session.add(test_student)
            await session.commit()
            await session.refresh(test_student)

        student_id = test_student.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Test Unauthenticated Requests (Every method must return 401 Unauthorized)
        print("\n1. Verifying 401 Unauthorized for Unauthenticated Requests on ALL Methods:")

        # POST /transcripts without auth
        unauth_post = await client.post("/transcripts", json={"student_id": student_id, "semesters": []})
        assert unauth_post.status_code == 401, f"Expected 401, got {unauth_post.status_code}"
        print("  [OK] POST /transcripts without auth returned 401 Unauthorized.")

        # GET /transcripts without auth
        unauth_list = await client.get("/transcripts")
        assert unauth_list.status_code == 401, f"Expected 401, got {unauth_list.status_code}"
        print("  [OK] GET /transcripts without auth returned 401 Unauthorized.")

        # GET /transcripts/{id} without auth
        unauth_get = await client.get("/transcripts/1")
        assert unauth_get.status_code == 401, f"Expected 401, got {unauth_get.status_code}"
        print("  [OK] GET /transcripts/{id} without auth returned 401 Unauthorized.")

        # GET /transcripts/student/{student_id} without auth
        unauth_get_student = await client.get(f"/transcripts/student/{student_id}")
        assert unauth_get_student.status_code == 401, f"Expected 401, got {unauth_get_student.status_code}"
        print("  [OK] GET /transcripts/student/{student_id} without auth returned 401 Unauthorized.")

        # PUT /transcripts/{id} without auth
        unauth_put = await client.put("/transcripts/1", json={"semesters": []})
        assert unauth_put.status_code == 401, f"Expected 401, got {unauth_put.status_code}"
        print("  [OK] PUT /transcripts/{id} without auth returned 401 Unauthorized.")

        # PATCH /transcripts/{id} without auth
        unauth_patch = await client.patch("/transcripts/1", json={"semesters": []})
        assert unauth_patch.status_code == 401, f"Expected 401, got {unauth_patch.status_code}"
        print("  [OK] PATCH /transcripts/{id} without auth returned 401 Unauthorized.")

        # DELETE /transcripts/{id} without auth
        unauth_delete = await client.delete("/transcripts/1")
        assert unauth_delete.status_code == 401, f"Expected 401, got {unauth_delete.status_code}"
        print("  [OK] DELETE /transcripts/{id} without auth returned 401 Unauthorized.")

        # 4. Authenticate an advisor
        print("\n2. Authenticating Advisor...")
        timestamp = int(datetime.now().timestamp())
        advisor_email = f"transcript_advisor_{timestamp}@university.edu"
        reg_res = await client.post(
            "/register",
            json={
                "name": "Prof. Alan Kay",
                "email": advisor_email,
                "password": "AdvisorPassword123!",
                "institution": "Smalltalk University",
            }
        )
        assert reg_res.status_code == 201, f"Advisor registration failed: {reg_res.text}"
        auth_data = reg_res.json()
        advisor_token = auth_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {advisor_token}"}
        print(f"  [OK] Advisor authenticated: {auth_data['advisor']['name']}")

        # 5. Test Add / Create Transcript
        print("\n3. Testing Add Transcript (POST /transcripts):")
        initial_semesters = [
            {
                "semester": "Fall 2024",
                "courses": {
                    "101": 4.0,
                    "102": 3.7
                }
            }
        ]
        add_res = await client.post(
            "/transcripts",
            json={
                "student_id": student_id,
                "semesters": initial_semesters
            },
            headers=auth_headers
        )
        assert add_res.status_code == 201, f"Failed to add transcript: {add_res.text}"
        t_data = add_res.json()
        transcript_id = t_data["id"]
        assert t_data["student_id"] == student_id
        assert len(t_data["semesters"]) == 1
        assert t_data["semesters"][0]["semester"] == "Fall 2024"
        assert t_data["student_name"] is not None
        print(f"  [OK] Created Transcript: ID {transcript_id} for Student '{t_data['student_name']}'")

        # 6. Test Non-Existent Student Error on Add (Expected 404)
        print("\n4. Testing Add Transcript for Non-Existent Student (Expected 404):")
        bad_add = await client.post(
            "/transcripts",
            json={
                "student_id": 999999,
                "semesters": []
            },
            headers=auth_headers
        )
        assert bad_add.status_code == 404, f"Expected 404, got {bad_add.status_code}"
        print(f"  [OK] Non-existent student rejected with 404: {bad_add.json()['detail']}")

        # 7. Test Get Transcript by ID (GET /transcripts/{id})
        print(f"\n5. Testing Get Transcript by ID (GET /transcripts/{transcript_id}):")
        get_res = await client.get(f"/transcripts/{transcript_id}", headers=auth_headers)
        assert get_res.status_code == 200, f"Failed to get transcript: {get_res.text}"
        get_data = get_res.json()
        assert get_data["id"] == transcript_id
        assert get_data["student_id"] == student_id
        assert len(get_data["semesters"]) == 1
        print(f"  [OK] Successfully retrieved transcript: ID {get_data['id']}, student_name='{get_data['student_name']}'")

        # 8. Test Non-Existent Transcript ID on Get (Expected 404)
        print("\n6. Testing Get Non-Existent Transcript ID (Expected 404):")
        bad_get = await client.get("/transcripts/999999", headers=auth_headers)
        assert bad_get.status_code == 404, f"Expected 404, got {bad_get.status_code}"
        print(f"  [OK] Non-existent transcript returned 404: {bad_get.json()['detail']}")

        # 9. Test Get Transcripts by Student ID (GET /transcripts/student/{student_id})
        print(f"\n7. Testing Get Transcripts by Student ID (GET /transcripts/student/{student_id}):")
        stu_res = await client.get(f"/transcripts/student/{student_id}", headers=auth_headers)
        assert stu_res.status_code == 200, f"Failed to get transcripts for student: {stu_res.text}"
        stu_transcripts = stu_res.json()
        assert isinstance(stu_transcripts, list)
        assert any(t["id"] == transcript_id for t in stu_transcripts)
        print(f"  [OK] Successfully retrieved {len(stu_transcripts)} transcript(s) for student ID {student_id}")

        # 10. Test Get Transcripts for Non-Existent Student (Expected 404)
        print("\n8. Testing Get Transcripts for Non-Existent Student (Expected 404):")
        bad_stu_get = await client.get("/transcripts/student/999999", headers=auth_headers)
        assert bad_stu_get.status_code == 404, f"Expected 404, got {bad_stu_get.status_code}"
        print(f"  [OK] Non-existent student returned 404: {bad_stu_get.json()['detail']}")

        # 11. Test List Transcripts with Filtering & Pagination (GET /transcripts)
        print("\n9. Testing List Transcripts (GET /transcripts):")
        list_res = await client.get("/transcripts?skip=0&limit=10", headers=auth_headers)
        assert list_res.status_code == 200, f"Failed to list transcripts: {list_res.text}"
        all_transcripts = list_res.json()
        assert len(all_transcripts) >= 1
        print(f"  [OK] Listed transcripts successfully: count={len(all_transcripts)}")

        # 12. Test Partial Edit Transcript (PATCH /transcripts/{id})
        print(f"\n10. Testing Partial Edit Transcript (PATCH /transcripts/{transcript_id}):")
        patch_semesters = [
            {
                "semester": "Fall 2024",
                "courses": {"101": 4.0, "102": 3.8}
            },
            {
                "semester": "Spring 2025",
                "courses": {"201": 3.9}
            }
        ]
        patch_res = await client.patch(
            f"/transcripts/{transcript_id}",
            json={"semesters": patch_semesters},
            headers=auth_headers
        )
        assert patch_res.status_code == 200, f"Failed to patch transcript: {patch_res.text}"
        patched_data = patch_res.json()
        assert len(patched_data["semesters"]) == 2
        assert patched_data["semesters"][1]["semester"] == "Spring 2025"
        print(f"  [OK] PATCH succeeded: semesters_count={len(patched_data['semesters'])}")

        # 13. Test Full Edit Transcript (PUT /transcripts/{id})
        print(f"\n11. Testing Full Edit Transcript (PUT /transcripts/{transcript_id}):")
        put_semesters = [
            {
                "semester": "Fall 2024",
                "courses": {"101": 4.0}
            }
        ]
        put_res = await client.put(
            f"/transcripts/{transcript_id}",
            json={"semesters": put_semesters},
            headers=auth_headers
        )
        assert put_res.status_code == 200, f"Failed to put transcript: {put_res.text}"
        put_data = put_res.json()
        assert len(put_data["semesters"]) == 1
        print(f"  [OK] PUT succeeded: semesters_count={len(put_data['semesters'])}")

        # 14. Test Edit with Invalid Student ID (Expected 404)
        print("\n12. Testing Edit with Non-Existent Student ID (Expected 404):")
        bad_edit = await client.patch(
            f"/transcripts/{transcript_id}",
            json={"student_id": 999999},
            headers=auth_headers
        )
        assert bad_edit.status_code == 404, f"Expected 404, got {bad_edit.status_code}"
        print(f"  [OK] Non-existent student on edit rejected with 404: {bad_edit.json()['detail']}")

        # 15. Test Append Semester Record (POST /transcripts/{id}/semesters)
        print(f"\n13. Testing Append Semester Record (POST /transcripts/{transcript_id}/semesters):")
        append_res = await client.post(
            f"/transcripts/{transcript_id}/semesters",
            json={
                "semester": "Summer 2025",
                "courses": {"301": 3.95}
            },
            headers=auth_headers
        )
        assert append_res.status_code == 200, f"Failed to append semester: {append_res.text}"
        appended_data = append_res.json()
        assert len(appended_data["semesters"]) == 2
        assert appended_data["semesters"][-1]["semester"] == "Summer 2025"
        print(f"  [OK] Appended semester successfully: latest='{appended_data['semesters'][-1]['semester']}'")

        # 16. Test Delete Transcript (DELETE /transcripts/{id})
        print(f"\n14. Testing Delete Transcript (DELETE /transcripts/{transcript_id}):")
        del_res = await client.delete(f"/transcripts/{transcript_id}", headers=auth_headers)
        assert del_res.status_code == 200, f"Failed to delete transcript: {del_res.text}"
        print(f"  [OK] Delete succeeded: {del_res.json()['message']}")

        # Verify it's gone
        get_deleted = await client.get(f"/transcripts/{transcript_id}", headers=auth_headers)
        assert get_deleted.status_code == 404
        print("  [OK] Verified deleted transcript returns 404 Not Found.")

    print("\n==================================================")
    print("ALL TRANSCRIPT CONTROLLER (GET, ADD, EDIT) TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    try:
        asyncio.run(run_transcript_tests())
    finally:
        asyncio.run(engine.dispose())
