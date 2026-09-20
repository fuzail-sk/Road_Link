from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import VIDEOS_DIR
from app.services.video_intelligence import (
    VideoIntelligenceService,
)

router = APIRouter(
    prefix="/api/video",
    tags=["Video"],
)

_service = None


def get_service() -> VideoIntelligenceService:
    global _service

    if _service is None:
        _service = VideoIntelligenceService(
            persistence_required=3
        )

    return _service


@router.get("/sample")
def get_sample_video() -> dict[str, Any]:

    video_path = (
        VIDEOS_DIR
        / "ParkingVideo.mp4"
    )

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sample video not found: "
                f"{video_path}"
            ),
        )

    return {
        "status": "ok",
        "video": "ParkingVideo.mp4",
        "path": str(video_path),
        "exists": True,
    }


@router.post("/analyze-sample")
def analyze_sample_video() -> dict[str, Any]:

    video_path = (
        VIDEOS_DIR
        / "ParkingVideo.mp4"
    )

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Sample video not found: "
                f"{video_path}"
            ),
        )

    try:

        service = get_service()

        analysis = service.analyze(
            video_path
        )

        return {
            "status": "ok",
            "message": (
                "Sample video processed through "
                "RoadLink end-to-end intelligence pipeline."
            ),
            "analysis": analysis,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Video intelligence analysis "
                f"failed: {exc}"
            ),
        )
