import asyncio

from app.db.base import Base
from app.db.session import engine

# Import ORM Models
# SQLAlchemy 只有在 Model 被 import 后，
# 才能把表注册进 Base.metadata。
import app.db.models.resource  # noqa: F401
import app.db.models.work_session  # noqa: F401
import app.db.models.conversation  # noqa: F401


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    print("database initialized")


if __name__ == "__main__":
    asyncio.run(main())
