import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.config import load_config

logger = logging.getLogger("mineadmin.webapp")

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db()
        logger.info("MineAdmin started")
        yield
        logger.info("MineAdmin shutting down")

    app = FastAPI(
        title="MineAdmin",
        description="Minecraft Server Manager",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.routes.auth import router as auth_router
    from app.routes.servers import router as servers_router
    from app.routes.files import router as files_router
    from app.routes.terminal import router as terminal_router
    from app.routes.config_routes import router as config_router
    from app.routes.monitoring import router as monitoring_router
    from app.routes.backup import router as backup_router

    app.include_router(auth_router)
    app.include_router(servers_router)
    app.include_router(files_router)
    app.include_router(terminal_router)
    app.include_router(config_router)
    app.include_router(monitoring_router)
    app.include_router(backup_router)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def serve_spa(request: Request, path: str = ""):
        if path.startswith("api/") or path.startswith("ws/") or path.startswith("static/"):
            return
        return templates.TemplateResponse("index.html", {"request": request})

    return app
