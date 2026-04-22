"""MongoDB accessor — shared singleton (module-level init)."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Instantiate once at import-time; safe because motor is lazy-connecting.
_client: AsyncIOMotorClient = AsyncIOMotorClient(os.environ["MONGO_URL"])


def get_db():
    return _client[os.environ["DB_NAME"]]
