import json
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.models import Base, User, Server, AppSettings
from app.config import load_config, get_sqlite_url, get_mysql_url, save_config

logger = logging.getLogger("mineadmin.database")

engine = None
async_session: async_sessionmaker[AsyncSession] | None = None


async def init_db():
    global engine, async_session
    cfg = load_config()
    db_type = cfg.get("db_type", "sqlite")

    if db_type == "mysql":
        try:
            url = get_mysql_url(cfg)
            engine = create_async_engine(url, echo=False, pool_pre_ping=True)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Connected to MySQL")
        except Exception as e:
            logger.warning(f"MySQL connection failed: {e}, falling back to SQLite")
            cfg["db_type"] = "sqlite"
            cfg["_mysql_error"] = str(e)
            save_config(cfg)
            url = get_sqlite_url()
            engine = create_async_engine(url, echo=False)
    else:
        url = get_sqlite_url()
        engine = create_async_engine(url, echo=False)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info(f"Database initialized ({cfg.get('db_type', 'sqlite')})")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def export_data(session: AsyncSession) -> dict:
    from sqlalchemy import select
    data = {"users": [], "servers": [], "settings": []}

    result = await session.execute(select(User))
    for u in result.scalars().all():
        data["users"].append({
            "id": u.id, "username": u.username,
            "password_hash": u.password_hash, "is_admin": u.is_admin
        })

    result = await session.execute(select(Server))
    for s in result.scalars().all():
        data["servers"].append({
            "id": s.id, "name": s.name, "core_type": s.core_type,
            "mc_version": s.mc_version, "port": s.port,
            "max_players": s.max_players, "memory_min": s.memory_min,
            "memory_max": s.memory_max, "java_path": s.java_path,
            "jvm_args": s.jvm_args, "server_dir": s.server_dir,
            "jar_file": s.jar_file, "status": "stopped",
            "auto_restart": s.auto_restart,
            "extra_config": s.extra_config or {}
        })

    result = await session.execute(select(AppSettings))
    for st in result.scalars().all():
        data["settings"].append({"key": st.key, "value": st.value})

    return data


async def import_data(session: AsyncSession, data: dict):
    from sqlalchemy import select

    for u_data in data.get("users", []):
        existing = await session.execute(
            select(User).where(User.username == u_data["username"])
        )
        if not existing.scalar_one_or_none():
            user = User(
                username=u_data["username"],
                password_hash=u_data["password_hash"],
                is_admin=u_data.get("is_admin", False)
            )
            session.add(user)

    for s_data in data.get("servers", []):
        existing = await session.execute(
            select(Server).where(Server.name == s_data["name"])
        )
        if not existing.scalar_one_or_none():
            srv = Server(**{k: v for k, v in s_data.items() if k != "id"})
            session.add(srv)

    for st_data in data.get("settings", []):
        existing = await session.execute(
            select(AppSettings).where(AppSettings.key == st_data["key"])
        )
        row = existing.scalar_one_or_none()
        if row:
            row.value = st_data["value"]
        else:
            session.add(AppSettings(key=st_data["key"], value=st_data["value"]))

    await session.commit()
