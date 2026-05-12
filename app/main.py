import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import init_db
from app.routers import auth, dashboard, simcards, export, notifications, guide, import_sim

load_dotenv()

app = FastAPI(title="SIM Card Management", version="1.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(simcards.router)
app.include_router(export.router)
app.include_router(notifications.router)
app.include_router(guide.router)
app.include_router(import_sim.router)


@app.on_event("startup")
async def startup_event():
    init_db()
    from app.routers.notifications import start_scheduler
    start_scheduler()
    print("SIM Card Management started!")


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
