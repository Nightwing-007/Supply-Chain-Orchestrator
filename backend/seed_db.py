import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def seed():
    url = os.getenv("DATABASE_URL")
    print(f"Connecting to default postgres db to recreate supply_chain...")
    try:
        # First connect to postgres DB to create supply_chain if needed
        sys_url = url.rsplit("/", 1)[0] + "/postgres"
        conn = await asyncpg.connect(sys_url)
        # Cannot drop database while in a transaction block, need to use connection without transaction
        await conn.execute("DROP DATABASE IF EXISTS supply_chain WITH (FORCE)")
        await conn.execute("CREATE DATABASE supply_chain")
        await conn.close()
        
        print(f"Connecting to {url} to apply schema and seed data...")
        # Now connect to supply_chain and run schema + seed
        conn = await asyncpg.connect(url)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, "db", "schema.sql")
        seed_path = os.path.join(script_dir, "db", "seed.sql")

        with open(schema_path, "r", encoding="utf-8") as f:
            await conn.execute(f.read())
        print("Schema applied successfully.")
        
        with open(seed_path, "r", encoding="utf-8") as f:
            await conn.execute(f.read())
        print("Seed data inserted successfully.")
        
        await conn.close()
        print("Database seeding complete!")
    except Exception as e:
        print(f"Error during seeding: {e}")

if __name__ == "__main__":
    asyncio.run(seed())
