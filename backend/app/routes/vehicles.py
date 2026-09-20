from fastapi import APIRouter


router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicles"],
)


@router.get("")
def vehicles():

    return {
        "vehicles": [],
        "count": 0,
        "message": (
            "Vehicle intelligence service "
            "will be connected in the next "
            "integration step."
        ),
    }
