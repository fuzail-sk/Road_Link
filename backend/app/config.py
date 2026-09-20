import os
from pathlib import Path


# backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# backend/assets/
ASSETS_DIR = BASE_DIR / "assets"

# backend/assets/models/
MODELS_DIR = ASSETS_DIR / "models"

# backend/assets/videos/
VIDEOS_DIR = ASSETS_DIR / "videos"

# backend/storage/
STORAGE_DIR = BASE_DIR / "storage"

# backend/storage/outputs/
OUTPUTS_DIR = STORAGE_DIR / "outputs"


# --------------------------------------------------------
# Model paths
# --------------------------------------------------------

YOLO_MODEL_PATH = os.getenv(
    "ROADLINK_YOLO_MODEL",
    str(MODELS_DIR / "yolo11n.pt")
)

PLATE_MODEL_PATH = os.getenv(
    "ROADLINK_PLATE_MODEL",
    str(
        MODELS_DIR
        / "plate_detector"
        / "best.pt"
    )
)


# --------------------------------------------------------
# Vehicle classes from COCO
# --------------------------------------------------------

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


# --------------------------------------------------------
# Traffic configuration
# --------------------------------------------------------

DENSITY_LOW_MAX = 3
DENSITY_MODERATE_MAX = 7
DENSITY_HIGH_MAX = 12

SPEED_FREE_FLOW_MIN = 30.0
SPEED_SLOWING_MIN = 20.0
SPEED_SLOW_MIN = 10.0


# --------------------------------------------------------
# Speed estimation
# --------------------------------------------------------

REFERENCE_DISTANCE_METERS = 10.0
REFERENCE_IMAGE_DISTANCE_PIXELS = 100.0

SPEED_MAX_VALID_KMH = 120.0


# --------------------------------------------------------
# Application
# --------------------------------------------------------

APP_NAME = "RoadLink"
APP_VERSION = "1.0.0"

API_PREFIX = "/api"
