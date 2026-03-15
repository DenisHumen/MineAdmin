from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    core_type = Column(String(50), nullable=False)
    mc_version = Column(String(20), nullable=False)
    port = Column(Integer, default=25565)
    max_players = Column(Integer, default=20)
    memory_min = Column(String(10), default="1G")
    memory_max = Column(String(10), default="2G")
    java_path = Column(String(500), default="java")
    jvm_args = Column(Text, default="")
    server_dir = Column(String(500), nullable=False)
    jar_file = Column(String(200), nullable=False)
    status = Column(String(20), default="stopped")
    pid = Column(Integer, nullable=True)
    auto_restart = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    extra_config = Column(JSON, default=dict)


class AppSettings(Base):
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
