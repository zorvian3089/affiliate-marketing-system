import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes import dashboard, agents, content, links, webhooks
from api.routes.dashboard import products_router
from api.routes import wp_auth, system
from agents.orchestrator import get_orchestrator
from database.database import init_db
from config.settings import APP_HOST, APP_PORT

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Affiliate Marketing System...")
    init_db()
    orchestrator = get_orchestrator()
    orchestrator.start()
    logger.info("System ready!")
    yield
    # Shutdown
    logger.info("Shutting down...")
    orchestrator.stop()


app = FastAPI(
    title="Affiliate Marketing System",
    description="AI-powered affiliate marketing automation with 9 agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(dashboard.router)
app.include_router(products_router)
app.include_router(agents.router)
app.include_router(content.router)
app.include_router(links.router)
app.include_router(webhooks.router)
app.include_router(wp_auth.router)
app.include_router(system.router)

# Serve dashboard UI
dashboard_dir = Path(__file__).parent.parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir / "static")), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(str(dashboard_dir / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "service": "affiliate-marketing-system"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=APP_HOST, port=APP_PORT, reload=False)
