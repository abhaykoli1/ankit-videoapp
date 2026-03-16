from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_instance = Database()

async def connect_db():
    # MongoDB Atlas ke liye tlsAllowInvalidCertificates nahi chahiye
    # motor automatically Atlas SRV handle karta hai
    db_instance.client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=10000,  # 10 sec timeout
        connectTimeoutMS=10000,
        tls=True,
        tlsAllowInvalidCertificates=False,
    )
    db_instance.db = db_instance.client[settings.DATABASE_NAME]

    # Connection test
    await db_instance.client.admin.command("ping")
    print(f"✅ MongoDB Atlas Connected — DB: {settings.DATABASE_NAME}")

    # Indexes banao
    try:
        await db_instance.db.users.create_index("username", unique=True)
        await db_instance.db.users.create_index("mobile", sparse=True)
        await db_instance.db.host_users.create_index("name")
        await db_instance.db.transactions.create_index("user_id")
        await db_instance.db.call_logs.create_index([("caller_id", 1), ("created_at", -1)])
        await db_instance.db.gifts.create_index("category")
        print("✅ Indexes created")
    except Exception as e:
        print(f"⚠️  Index warning (non-fatal): {e}")

async def close_db():
    if db_instance.client:
        db_instance.client.close()
        print("MongoDB Disconnected")

def get_db():
    return db_instance.db
