from fastapi import APIRouter

router = APIRouter(
    prefix="/api/health",
    tags=["Health"],
)


@router.get("")
def health():
    return {
        "product": "RoadLink",
        "service": "Traffic Intelligence API",
        "status": "online",
    }
