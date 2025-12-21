import os
from pathlib import Path

import asyncpg


class Database:
    """Database connection manager."""
    
    _pool: asyncpg.Pool | None = None
    _sql_cache: dict[str, str] = {}
    
    @classmethod
    async def connect(cls) -> None:
        """Create database connection pool and initialize schema."""
        cls._pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "svoyachello"),
        )
    
    @classmethod
    async def disconnect(cls) -> None:
        """Close database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
    
    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """Get the connection pool."""
        if cls._pool is None:
            raise RuntimeError("Database not connected. Call Database.connect() first.")
        return cls._pool
    
    @classmethod
    def load_sql(cls, filename: str) -> str:
        """Load SQL from file and cache it."""
        if filename not in cls._sql_cache:
            sql_dir = Path(__file__).parent.parent / "sql"
            sql_path = sql_dir / filename
            cls._sql_cache[filename] = sql_path.read_text()
        return cls._sql_cache[filename]

