import sys
import asyncio
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Psycopg 3 async requires WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import httpx
from src.main import app
from src.shared.database import engine, init_db


async def run_course_tests():
    print("==================================================")
    print("TESTING FASTAPI COURSE CONTROLLER (ADD, EDIT, GET)")
    print("==================================================")

    # 1. Initialize database schema
    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Test Unauthenticated Requests (Every method must return 401 Unauthorized)
        print("\n1. Verifying 401 Unauthorized for Unauthenticated Requests:")

        # POST /courses without auth
        unauth_post = await client.post("/courses", json={"code": "CS101", "title": "Intro", "credit_hours": 3.0})
        assert unauth_post.status_code == 401, f"Expected 401, got {unauth_post.status_code}"
        print("  [OK] POST /courses without auth returned 401 Unauthorized.")

        # GET /courses without auth
        unauth_list = await client.get("/courses")
        assert unauth_list.status_code == 401, f"Expected 401, got {unauth_list.status_code}"
        print("  [OK] GET /courses without auth returned 401 Unauthorized.")

        # GET /courses/{id} without auth
        unauth_get = await client.get("/courses/1")
        assert unauth_get.status_code == 401, f"Expected 401, got {unauth_get.status_code}"
        print("  [OK] GET /courses/{id} without auth returned 401 Unauthorized.")

        # GET /courses/by-code/{code} without auth
        unauth_code = await client.get("/courses/by-code/CS101")
        assert unauth_code.status_code == 401, f"Expected 401, got {unauth_code.status_code}"
        print("  [OK] GET /courses/by-code/{code} without auth returned 401 Unauthorized.")

        # PATCH /courses/{id} without auth
        unauth_patch = await client.patch("/courses/1", json={"title": "Updated"})
        assert unauth_patch.status_code == 401, f"Expected 401, got {unauth_patch.status_code}"
        print("  [OK] PATCH /courses/{id} without auth returned 401 Unauthorized.")

        # 3. Authenticate an advisor
        print("\n2. Authenticating Advisor...")
        timestamp = int(datetime.now().timestamp())
        advisor_email = f"course_advisor_{timestamp}@university.edu"
        reg_res = await client.post(
            "/register",
            json={
                "name": "Prof. Donald Knuth",
                "email": advisor_email,
                "password": "AdvisorPassword123!",
                "institution": "Stanford University",
            }
        )
        assert reg_res.status_code == 201, f"Advisor registration failed: {reg_res.text}"
        auth_data = reg_res.json()
        advisor_token = auth_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {advisor_token}"}
        print(f"  [OK] Advisor authenticated: {auth_data['advisor']['name']}")

        # 4. Test Add / Create Course
        print("\n3. Testing Add Course (POST /courses):")
        code_1 = f"CS101_{timestamp % 10000}"
        course_1_payload = {
            "code": code_1,
            "title": "Introduction to Computer Science",
            "description": "Fundamental principles of programming and algorithms.",
            "credit_hours": 3.0,
            "prerequisites": [],
        }
        res1 = await client.post("/courses", json=course_1_payload, headers=auth_headers)
        assert res1.status_code == 201, f"Failed to add course: {res1.text}"
        c1_data = res1.json()
        c1_id = c1_data["id"]
        assert c1_data["code"] == code_1.upper()
        assert c1_data["title"] == "Introduction to Computer Science"
        assert c1_data["credit_hours"] == 3.0
        assert c1_data["difficulty_level"] == "medium"
        assert c1_data["prerequisites"] == []
        print(f"  [OK] Added Course 1: ID {c1_id}, Code {c1_data['code']}, Difficulty: {c1_data['difficulty_level']}")

        # Add Course 2 with prerequisites and difficulty
        code_2 = f"CS201_{timestamp % 10000}"
        course_2_payload = {
            "code": code_2,
            "title": "Data Structures & Algorithms",
            "description": "Trees, graphs, dynamic programming, and complexity analysis.",
            "credit_hours": 4.0,
            "difficulty_level": "hard",
            "prerequisites": [code_1],
        }
        res2 = await client.post("/courses", json=course_2_payload, headers=auth_headers)
        assert res2.status_code == 201, f"Failed to add course 2: {res2.text}"
        c2_data = res2.json()
        c2_id = c2_data["id"]
        assert c2_data["prerequisites"] == [code_1]
        assert c2_data["difficulty_level"] == "hard"
        print(f"  [OK] Added Course 2: ID {c2_id}, Code {c2_data['code']}, Difficulty: {c2_data['difficulty_level']}, Prerequisites: {c2_data['prerequisites']}")

        # Duplicate Code Rejection (Expected 409 Conflict)
        print("\n4. Testing Duplicate Course Code Rejection (Expected 409):")
        dup_res = await client.post("/courses", json=course_1_payload, headers=auth_headers)
        assert dup_res.status_code == 409, f"Expected 409, got {dup_res.status_code}"
        print(f"  [OK] Duplicate course code rejected with 409: {dup_res.json()['detail']}")

        # Validation test: invalid difficulty_level (Expected 422)
        print("\n5. Testing Validation on Invalid difficulty_level (Expected 422):")
        bad_diff = await client.post(
            "/courses",
            json={"code": "BAD_DIFF_01", "title": "Bad Diff", "credit_hours": 3.0, "difficulty_level": "extreme"},
            headers=auth_headers
        )
        assert bad_diff.status_code == 422
        print("  [OK] Invalid difficulty 'extreme' rejected with 422 validation error.")

        # Validation test: credit_hours <= 0 (Expected 422)
        print("\n6. Testing Validation on Invalid credit_hours <= 0 (Expected 422):")
        bad_credits = await client.post(
            "/courses",
            json={"code": "BAD01", "title": "Bad", "credit_hours": 0},
            headers=auth_headers
        )
        assert bad_credits.status_code == 422
        print("  [OK] Zero credit hours rejected with 422 validation error.")

        # 5. Test Get Course by ID
        print(f"\n7. Testing Get Course by ID: GET /courses/{c1_id}")
        get_id_res = await client.get(f"/courses/{c1_id}", headers=auth_headers)
        assert get_id_res.status_code == 200
        assert get_id_res.json()["id"] == c1_id
        assert get_id_res.json()["code"] == code_1.upper()
        assert get_id_res.json()["difficulty_level"] == "medium"
        print(f"  [OK] Retrieved by ID successfully: {get_id_res.json()['title']}, Difficulty={get_id_res.json()['difficulty_level']}")

        # Non-existent ID (Expected 404)
        nf_id = await client.get("/courses/999999", headers=auth_headers)
        assert nf_id.status_code == 404
        print(f"  [OK] Non-existent ID returned 404: {nf_id.json()['detail']}")

        # 6. Test Get Course by Code
        print(f"\n8. Testing Get Course by Code: GET /courses/by-code/{code_1.lower()}")
        get_code_res = await client.get(f"/courses/by-code/{code_1.lower()}", headers=auth_headers)
        assert get_code_res.status_code == 200
        assert get_code_res.json()["id"] == c1_id
        print(f"  [OK] Case-insensitive retrieval by code succeeded: {get_code_res.json()['code']}")

        # Non-existent Code (Expected 404)
        nf_code = await client.get("/courses/by-code/NONEXISTENT999", headers=auth_headers)
        assert nf_code.status_code == 404
        print(f"  [OK] Non-existent code returned 404: {nf_code.json()['detail']}")

        # 7. Test List Courses with search and filters (including difficulty)
        print("\n9. Testing List Courses: GET /courses with query parameters and difficulty filter")
        list_res = await client.get(
            "/courses",
            params={"search": "Structures", "min_credits": 3.0, "difficulty": "hard"},
            headers=auth_headers
        )
        assert list_res.status_code == 200
        courses = list_res.json()
        assert any(c["id"] == c2_id for c in courses)
        assert all(c["difficulty_level"] == "hard" for c in courses)
        print(f"  [OK] Search filter with difficulty=hard returned matching courses ({len(courses)} match).")

        # 8. Test Edit Course (PATCH & PUT)
        print(f"\n10. Testing Partial Edit (PATCH /courses/{c1_id}):")
        patch_payload = {
            "title": "Introduction to Computer Science (Honors)",
            "credit_hours": 3.5,
            "difficulty_level": "low",
            "description": "Accelerated foundational course with lab component."
        }
        patch_res = await client.patch(f"/courses/{c1_id}", json=patch_payload, headers=auth_headers)
        assert patch_res.status_code == 200, f"PATCH failed: {patch_res.text}"
        patched_course = patch_res.json()
        assert patched_course["title"] == "Introduction to Computer Science (Honors)"
        assert patched_course["credit_hours"] == 3.5
        assert patched_course["difficulty_level"] == "low"
        assert "lab component" in patched_course["description"]
        print(f"  [OK] PATCH succeeded: Title='{patched_course['title']}', Difficulty={patched_course['difficulty_level']}, Credits={patched_course['credit_hours']}")

        print(f"\n11. Testing Full Edit (PUT /courses/{c2_id}):")
        put_payload = {
            "code": code_2,
            "title": "Advanced Data Structures & Algorithms",
            "description": "Comprehensive algorithms study.",
            "credit_hours": 4.5,
            "prerequisites": [code_1, "MATH101"],
        }
        put_res = await client.put(f"/courses/{c2_id}", json=put_payload, headers=auth_headers)
        assert put_res.status_code == 200, f"PUT failed: {put_res.text}"
        put_course = put_res.json()
        assert put_course["title"] == "Advanced Data Structures & Algorithms"
        assert put_course["credit_hours"] == 4.5
        assert len(put_course["prerequisites"]) == 2
        print(f"  [OK] PUT succeeded: Title='{put_course['title']}', Prerequisites={put_course['prerequisites']}")

        # Duplicate Code Check on Edit (Expected 409)
        print("\n11. Testing Duplicate Code on Edit (Expected 409):")
        dup_edit = await client.patch(f"/courses/{c2_id}", json={"code": code_1}, headers=auth_headers)
        assert dup_edit.status_code == 409
        print(f"  [OK] Duplicate code on edit rejected with 409: {dup_edit.json()['detail']}")

    print("\n==================================================")
    print("ALL COURSE CONTROLLER (ADD, EDIT, GET) TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    try:
        asyncio.run(run_course_tests())
    finally:
        asyncio.run(engine.dispose())
