from fastapi import APIRouter


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


@router.get("")
def alerts():

    return {
        "alerts": [],
        "count": 0,
    }
