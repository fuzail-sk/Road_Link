from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import OUTPUTS_DIR

from app.routes.health import router as health_router
from app.routes.video import router as video_router
from app.routes.traffic import router as traffic_router
from app.routes.journeys import router as journeys_router
from app.routes.emergency import router as emergency_router


app = FastAPI(
    title="RoadLink API",
    version="1.0.0",
    description="RoadLink traffic intelligence and vehicle journey backend",
)




app.include_router(health_router)
app.include_router(video_router)
app.include_router(traffic_router)
app.include_router(journeys_router)
app.include_router(emergency_router)


OUTPUTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


app.mount(
    "/outputs",
    StaticFiles(
        directory=str(OUTPUTS_DIR)
    ),
    name="outputs",
)


@app.get("/")
def root():
    return {
        "name": "RoadLink",
        "status": "running",
        "version": "1.0.0",
    }

# RoadLink frontend CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://road-link-lime.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
