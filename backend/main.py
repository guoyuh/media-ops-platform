from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db
from api import (
    collect_router,
    users_router,
    message_router,
    accounts_router,
    dashboard_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collect_router)
app.include_router(users_router)
app.include_router(message_router)
app.include_router(accounts_router)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"message": "MediaOps Platform API", "docs": "/docs"}
