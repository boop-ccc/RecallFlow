from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


# AsyncEngine:
# 管理数据库访问基础设施。
engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
)


# Session Factory:
# 每次调用都会创建一个独立 AsyncSession。
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# FastAPI Dependency:
# 每个请求获取独立 Session，请求结束后自动关闭。
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session