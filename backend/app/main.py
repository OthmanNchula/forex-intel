import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, market, analysis, risk, journal, alerts
from app.websocket.price_feed import handle_price_websocket, price_broadcast_loop


# Create all database tables on startup
def create_tables():
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Creates DB tables and starts the price broadcast background task.
    """
    # Startup
    print("Starting Forex Intel API...")
    create_tables()
    print("Database tables created.")

    # Start background price broadcast loop
    broadcast_task = asyncio.create_task(price_broadcast_loop())
    print("Price broadcast loop started.")

    yield

    # Shutdown
    broadcast_task.cancel()
    print("Forex Intel API shutting down.")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-Powered Forex Trading Intelligence Platform",
    lifespan=lifespan,
)

# CORS — allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(market.router)
app.include_router(analysis.router)
app.include_router(risk.router)
app.include_router(journal.router)
app.include_router(alerts.router)


# WebSocket endpoint
@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    await handle_price_websocket(websocket)


# Health check
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "disclaimer": "This platform is for decision support only. Not financial advice.",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}