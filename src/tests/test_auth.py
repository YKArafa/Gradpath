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


async def run_auth_tests():
    print("==================================================")
    print("TESTING FASTAPI ADVISOR AUTH CONTROLLER")
    print("==================================================")

    # 1. Ensure DB schema is ready
    await init_db()

    # Create an async test client
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test root endpoint
        res = await client.get("/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        print("  [OK] Health check endpoint passed.")

        # Test registration
        timestamp = int(datetime.now().timestamp())
        advisor_email = f"advisor_{timestamp}@university.edu"
        password = "SecurePassword123!"

        reg_payload = {
            "name": "Dr. Sarah Connor",
            "email": advisor_email,
            "password": password,
            "institution": "MIT Department of Computer Science",
        }

        print(f"\n1. Testing Registration with email: {advisor_email}")
        res = await client.post("/register", json=reg_payload)
        assert res.status_code == 201, f"Registration failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "access_token" in data, "Token missing from response"
        assert data["token_type"] == "bearer"
        assert data["advisor"]["email"] == advisor_email.lower()
        assert data["advisor"]["name"] == "Dr. Sarah Connor"
        assert data["advisor"]["institution"] == "MIT Department of Computer Science"
        access_token = data["access_token"]
        advisor_id = data["advisor"]["id"]
        print(f"  [OK] Registration successful! Advisor ID: {advisor_id}, Token generated.")

        # Test duplicate registration (Conflict)
        print("\n2. Testing Duplicate Registration (Expected 409 Conflict)")
        dup_res = await client.post("/register", json=reg_payload)
        assert dup_res.status_code == 409, f"Expected 409, got {dup_res.status_code}"
        print(f"  [OK] Duplicate registration correctly rejected with 409 Conflict: {dup_res.json()['detail']}")

        # Test login with wrong password
        print("\n3. Testing Login with Wrong Password (Expected 401 Unauthorized)")
        bad_pw_res = await client.post("/login", json={"email": advisor_email, "password": "WrongPassword!"})
        assert bad_pw_res.status_code == 401, f"Expected 401, got {bad_pw_res.status_code}"
        print(f"  [OK] Wrong password correctly rejected with 401 Unauthorized.")

        # Test login with non-existent email
        print("\n4. Testing Login with Non-Existent Email (Expected 401 Unauthorized)")
        bad_email_res = await client.post("/login", json={"email": "nonexistent@univ.edu", "password": password})
        assert bad_email_res.status_code == 401, f"Expected 401, got {bad_email_res.status_code}"
        print(f"  [OK] Non-existent email correctly rejected with 401 Unauthorized.")

        # Test successful login
        print("\n5. Testing Successful Login")
        login_res = await client.post("/login", json={"email": advisor_email, "password": password})
        assert login_res.status_code == 200, f"Login failed: {login_res.status_code} - {login_res.text}"
        login_data = login_res.json()
        assert "access_token" in login_data
        assert login_data["advisor"]["id"] == advisor_id
        new_token = login_data["access_token"]
        print(f"  [OK] Login successful! Received valid JWT access token.")

        # Test protected /me endpoint with token
        print("\n6. Testing Protected /me Endpoint with Bearer Token")
        me_res = await client.get("/me", headers={"Authorization": f"Bearer {new_token}"})
        assert me_res.status_code == 200, f"Protected route failed: {me_res.status_code} - {me_res.text}"
        me_data = me_res.json()
        assert me_data["id"] == advisor_id
        assert me_data["email"] == advisor_email.lower()
        print(f"  [OK] Successfully retrieved profile for advisor: {me_data['name']}")

        # Test protected /me endpoint with invalid token
        print("\n7. Testing Protected /me Endpoint with Invalid Token (Expected 401)")
        invalid_res = await client.get("/me", headers={"Authorization": "Bearer invalid_fake_token"})
        assert invalid_res.status_code == 401, f"Expected 401, got {invalid_res.status_code}"
        print("  [OK] Invalid token correctly rejected with 401 Unauthorized.")

        # Test route prefix aliases /auth/register and /auth/login
        print("\n8. Testing /auth/* Route Aliases")
        alias_login_res = await client.post("/auth/login", json={"email": advisor_email, "password": password})
        assert alias_login_res.status_code == 200, f"Alias login failed: {alias_login_res.status_code}"
        print("  [OK] /auth/login alias returned 200 OK.")

    print("\n==================================================")
    print("ALL AUTH CONTROLLER TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    try:
        asyncio.run(run_auth_tests())
    finally:
        asyncio.run(engine.dispose())
