import asyncio
from sqlalchemy import text
from src.shared.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        d = (await s.execute(text("SELECT id, name FROM degree"))).fetchall()
        m = (await s.execute(text("SELECT id, name, degree_id FROM major"))).fetchall()
        print("DEGREES_COUNT:", len(d), d)
        print("MAJORS_COUNT:", len(m), m)

if __name__ == "__main__":
    asyncio.run(check())

