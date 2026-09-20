import cv2
import json
import math
import os
import uuid
from collections import defaultdict, deque, Counter
from datetime import datetime

from ultralytics import YOLO


# ============================================================
# ROADLINK — PHASE 2.2
# Traffic Intelligence / Congestion Detection
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "assets",
    "models",
    "yolo11n.pt"
)

VIDEO_PATH = os.path.join(
    BASE_DIR,
    "assets",
    "videos",
    "ParkingVideo.mp4"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "storage",
    "outputs"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ------------------------------------------------------------
# Prototype camera calibration
# ------------------------------------------------------------
# IMPORTANT:
# This is still prototype calibration.
# It must eventually be replaced with measured road/camera
# calibration for real-world km/h.
# ------------------------------------------------------------

REFERENCE_DISTANCE_METERS = 10.0
REFERENCE_PIXEL_DISTANCE = 100.0

METERS_PER_PIXEL = (
    REFERENCE_DISTANCE_METERS /
    REFERENCE_PIXEL_DISTANCE
)


# ------------------------------------------------------------
# Vehicle classes
# ------------------------------------------------------------

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

VEHICLE_CLASS_IDS = list(VEHICLE_CLASSES.keys())


# ------------------------------------------------------------
# Tracking / speed configuration
# ------------------------------------------------------------

CONFIDENCE = 0.35

POSITION_HISTORY_SIZE = 8
MIN_POSITION_SAMPLES = 4

SPEED_SMOOTHING_WINDOW = 5

MAX_VALID_SPEED_KMH = 120.0

MAX_POSITION_JUMP_PIXELS = 80.0


# ------------------------------------------------------------
# Traffic intelligence configuration
# ------------------------------------------------------------

# Vehicle count thresholds.
DENSITY_LOW = 3
DENSITY_MODERATE = 7
DENSITY_HIGH = 12

# Speed thresholds.
SPEED_GOOD = 30.0
SPEED_SLOW = 20.0
SPEED_VERY_SLOW = 10.0

# Persistence.
PERSISTENCE_FRAMES = 15

# Number of previous frames used for traffic trend.
TREND_WINDOW = 30


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def center_of_bbox(box):
    x1, y1, x2, y2 = box

    return (
        (x1 + x2) / 2.0,
        (y1 + y2) / 2.0
    )


def distance_pixels(p1, p2):
    return math.sqrt(
        (p2[0] - p1[0]) ** 2 +
        (p2[1] - p1[1]) ** 2
    )


def calculate_speed(history, fps):
    """
    Estimate speed from a track history.

    Uses multiple frames instead of one frame-to-frame
    measurement to reduce tracker noise.
    """

    if len(history) < MIN_POSITION_SAMPLES:
        return None

    oldest = history[0]
    newest = history[-1]

    frame_old, x_old, y_old = oldest
    frame_new, x_new, y_new = newest

    frame_delta = frame_new - frame_old

    if frame_delta <= 0:
        return None

    pixel_distance = distance_pixels(
        (x_old, y_old),
        (x_new, y_new)
    )

    # Reject obvious tracking jumps.
    allowed_jump = (
        MAX_POSITION_JUMP_PIXELS *
        max(1, frame_delta)
    )

    if pixel_distance > allowed_jump:
        return None

    meters = pixel_distance * METERS_PER_PIXEL

    seconds = frame_delta / fps

    if seconds <= 0:
        return None

    meters_per_second = meters / seconds

    speed_kmh = meters_per_second * 3.6

    if speed_kmh < 0:
        return None

    if speed_kmh > MAX_VALID_SPEED_KMH:
        return None

    return speed_kmh


# ------------------------------------------------------------
# Traffic Intelligence
# ------------------------------------------------------------

def calculate_density_category(active_count):
    """
    Density is the primary signal.

    A small number of vehicles cannot by itself create
    HIGH or CRITICAL congestion.
    """

    if active_count <= 3:
        return "LOW"

    if active_count <= 7:
        return "MODERATE"

    if active_count <= 12:
        return "HIGH"

    return "CRITICAL"


def calculate_speed_category(average_speed):
    """
    Speed describes how freely vehicles are moving.

    This is a supporting signal, not the primary congestion
    gate.
    """

    if average_speed is None:
        return "UNKNOWN"

    if average_speed >= 30:
        return "FREE_FLOW"

    if average_speed >= 20:
        return "SLOWING"

    if average_speed >= 10:
        return "SLOW"

    return "STOPPED_OR_CRAWLING"


def calculate_traffic_score(
    density_category,
    speed_category
):
    """
    Calculate a supporting traffic score.

    Density has substantially more influence than speed.
    """

    density_scores = {
        "LOW": 0,
        "MODERATE": 35,
        "HIGH": 70,
        "CRITICAL": 100,
    }

    speed_scores = {
        "FREE_FLOW": 0,
        "SLOWING": 25,
        "SLOW": 60,
        "STOPPED_OR_CRAWLING": 85,
        "UNKNOWN": 0,
    }

    density_score = density_scores[
        density_category
    ]

    speed_score = speed_scores[
        speed_category
    ]

    # Density is dominant.
    score = (
        density_score * 0.70 +
        speed_score * 0.30
    )

    return round(score, 2)


def determine_traffic_state(
    active_count,
    average_speed,
    previous_states
):
    """
    Refined traffic intelligence model.

    Rules:

    1. Density determines the maximum possible state.
    2. Speed modifies the state only within that density range.
    3. LOW density cannot become HIGH/CRITICAL merely
       because one vehicle is slow.
    4. HIGH/CRITICAL conditions require persistence.
    """

    density_category = calculate_density_category(
        active_count
    )

    speed_category = calculate_speed_category(
        average_speed
    )

    score = calculate_traffic_score(
        density_category,
        speed_category
    )

    recent = list(previous_states)

    moderate_or_worse = {
        "MODERATE",
        "HIGH",
        "CRITICAL",
    }

    high_or_worse = {
        "HIGH",
        "CRITICAL",
    }

    persistent_moderate = (
        sum(
            1
            for state in recent
            if state in moderate_or_worse
        )
        >= max(
            5,
            len(recent) // 2
        )
        if recent
        else False
    )

    persistent_high = (
        sum(
            1
            for state in recent
            if state in high_or_worse
        )
        >= max(
            5,
            len(recent) // 2
        )
        if recent
        else False
    )

    # --------------------------------------------------------
    # Density-gated state classification
    # --------------------------------------------------------

    if density_category == "LOW":

        # Even very slow traffic with only a few vehicles
        # remains LOW. This avoids false congestion.
        state = "LOW"

    elif density_category == "MODERATE":

        if speed_category in {
            "SLOW",
            "STOPPED_OR_CRAWLING"
        } and persistent_moderate:

            state = "MODERATE"

        else:
            state = "MODERATE"

    elif density_category == "HIGH":

        if (
            speed_category in {
                "SLOW",
                "STOPPED_OR_CRAWLING"
            }
            and persistent_high
        ):

            state = "HIGH"

        else:
            state = "MODERATE"

    else:
        # CRITICAL density.
        #
        # We still require poor speed conditions and
        # persistence before declaring CRITICAL.
        if (
            speed_category in {
                "SLOW",
                "STOPPED_OR_CRAWLING"
            }
            and persistent_high
        ):

            state = "CRITICAL"

        else:
            state = "HIGH"

    return {
        "state": state,
        "score": score,
        "density_category": density_category,
        "speed_category": speed_category,
        "density_score": (
            0
            if density_category == "LOW"
            else 35
            if density_category == "MODERATE"
            else 70
            if density_category == "HIGH"
            else 100
        ),
        "speed_score": (
            0
            if speed_category == "FREE_FLOW"
            else 25
            if speed_category == "SLOWING"
            else 60
            if speed_category == "SLOW"
            else 85
            if speed_category == "STOPPED_OR_CRAWLING"
            else 0
        ),
        "persistent_moderate": persistent_moderate,
        "persistent_high": persistent_high,
    }

# ------------------------------------------------------------
# Main analysis
# ------------------------------------------------------------

def analyze_video():

    analysis_id = uuid.uuid4().hex[:10]

    output_video = os.path.join(
        OUTPUT_DIR,
        f"roadlink-phase2-traffic-{analysis_id}.mp4"
    )

    report_path = os.path.join(
        OUTPUT_DIR,
        f"roadlink-phase2-traffic-{analysis_id}.json"
    )

    print()
    print("=" * 65)
    print("ROADLINK — PHASE 2.2 TRAFFIC INTELLIGENCE")
    print("=" * 65)
    print()

    print("Loading YOLO model...")
    model = YOLO(MODEL_PATH)

    print("Opening video...")
    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if not fps or fps <= 0:
        fps = 30.0

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    duration = (
        total_frames / fps
        if fps
        else 0
    )

    print(f"FPS: {fps:.2f}")
    print(f"Resolution: {width}x{height}")
    print(f"Frames: {total_frames}")
    print(f"Duration: {duration:.2f}s")
    print()

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        output_video,
        fourcc,
        fps,
        (width, height)
    )

    # Track -> position history
    histories = defaultdict(
        lambda: deque(
            maxlen=POSITION_HISTORY_SIZE
        )
    )

    # Track -> speed history
    speed_histories = defaultdict(
        lambda: deque(
            maxlen=SPEED_SMOOTHING_WINDOW
        )
    )

    # Recent traffic states
    recent_states = deque(
        maxlen=PERSISTENCE_FRAMES
    )

    # Traffic trend
    traffic_history = deque(
        maxlen=TREND_WINDOW
    )

    unique_vehicle_ids = set()

    traffic_state_counts = Counter()

    speed_values = []

    frame_records = []

    frame_index = 0

    start_time = datetime.now()

    print("Processing video...")
    print()

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_index += 1

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=CONFIDENCE,
            classes=VEHICLE_CLASS_IDS,
            verbose=False,
        )

        active_vehicles = []

        if results:

            result = results[0]

            if result.boxes is not None:

                boxes = result.boxes

                ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else []
                )

                xyxy = (
                    boxes.xyxy.cpu().tolist()
                    if boxes.xyxy is not None
                    else []
                )

                cls = (
                    boxes.cls.int().cpu().tolist()
                    if boxes.cls is not None
                    else []
                )

                confs = (
                    boxes.conf.cpu().tolist()
                    if boxes.conf is not None
                    else []
                )

                for index, track_id in enumerate(ids):

                    if index >= len(xyxy):
                        continue

                    box = xyxy[index]

                    vehicle_class = (
                        VEHICLE_CLASSES.get(
                            cls[index],
                            "unknown"
                        )
                        if index < len(cls)
                        else "unknown"
                    )

                    confidence = (
                        confs[index]
                        if index < len(confs)
                        else 0
                    )

                    center = center_of_bbox(box)

                    histories[track_id].append(
                        (
                            frame_index,
                            center[0],
                            center[1],
                        )
                    )

                    unique_vehicle_ids.add(
                        track_id
                    )

                    speed = calculate_speed(
                        histories[track_id],
                        fps
                    )

                    if speed is not None:

                        speed_histories[
                            track_id
                        ].append(speed)

                    smoothed_speed = None

                    if speed_histories[track_id]:

                        smoothed_speed = (
                            sum(
                                speed_histories[
                                    track_id
                                ]
                            )
                            /
                            len(
                                speed_histories[
                                    track_id
                                ]
                            )
                        )

                    active_vehicles.append(
                        {
                            "track_id": int(track_id),
                            "class": vehicle_class,
                            "confidence": round(
                                float(confidence),
                                3
                            ),
                            "speed_kmh": (
                                round(
                                    smoothed_speed,
                                    2
                                )
                                if smoothed_speed
                                is not None
                                else None
                            ),
                            "bbox": [
                                round(float(v), 2)
                                for v in box
                            ],
                        }
                    )

                    # Draw vehicle box.
                    x1, y1, x2, y2 = [
                        int(v)
                        for v in box
                    ]

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (255, 255, 255),
                        2
                    )

                    label = (
                        f"#{track_id} "
                        f"{vehicle_class}"
                    )

                    if smoothed_speed is not None:
                        label += (
                            f" "
                            f"{smoothed_speed:.1f}"
                            f"km/h"
                        )

                    cv2.putText(
                        frame,
                        label,
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA,
                    )

        # ----------------------------------------------------
        # Traffic metrics for this frame
        # ----------------------------------------------------

        active_count = len(active_vehicles)

        valid_speeds = [
            vehicle["speed_kmh"]
            for vehicle in active_vehicles
            if vehicle["speed_kmh"] is not None
        ]

        average_speed = (
            sum(valid_speeds) /
            len(valid_speeds)
            if valid_speeds
            else None
        )

        if valid_speeds:
            speed_values.extend(
                valid_speeds
            )

        # First determine current traffic using
        # recent history before adding current state.
        intelligence = determine_traffic_state(
            active_count,
            average_speed,
            recent_states
        )

        traffic_state = intelligence["state"]

        recent_states.append(
            traffic_state
        )

        traffic_state_counts[
            traffic_state
        ] += 1

        traffic_history.append(
            {
                "frame": frame_index,
                "active_vehicles": active_count,
                "average_speed_kmh": (
                    round(
                        average_speed,
                        2
                    )
                    if average_speed is not None
                    else None
                ),
                "traffic_state": traffic_state,
                "traffic_score": intelligence[
                    "score"
                ],
            }
        )

        frame_records.append(
            {
                "frame": frame_index,
                "active_vehicles": active_count,
                "average_speed_kmh": (
                    round(
                        average_speed,
                        2
                    )
                    if average_speed is not None
                    else None
                ),
                "traffic": intelligence,
            }
        )

        # ----------------------------------------------------
        # Video overlay
        # ----------------------------------------------------

        cv2.rectangle(
            frame,
            (15, 15),
            (430, 150),
            (0, 0, 0),
            -1
        )

        cv2.putText(
            frame,
            "ROADLINK",
            (30, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"Frame: {frame_index}/{total_frames}",
            (30, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"Vehicles: {active_count}",
            (30, 98),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        speed_text = (
            f"{average_speed:.1f} km/h"
            if average_speed is not None
            else "N/A"
        )

        cv2.putText(
            frame,
            f"Avg Speed: {speed_text}",
            (30, 124),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            f"Traffic: {traffic_state}",
            (250, 124),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        writer.write(frame)

        if frame_index % 100 == 0:

            print(
                f"Processed "
                f"{frame_index}/{total_frames} "
                f"| vehicles={active_count} "
                f"| speed="
                f"{speed_text} "
                f"| traffic="
                f"{traffic_state}"
            )

    cap.release()
    writer.release()

    end_time = datetime.now()

    processing_seconds = (
        end_time - start_time
    ).total_seconds()

    # --------------------------------------------------------
    # Final statistics
    # --------------------------------------------------------

    active_counts = [
        record["active_vehicles"]
        for record in frame_records
    ]

    avg_active = (
        sum(active_counts) /
        len(active_counts)
        if active_counts
        else 0
    )

    peak_active = (
        max(active_counts)
        if active_counts
        else 0
    )

    avg_speed = (
        sum(speed_values) /
        len(speed_values)
        if speed_values
        else None
    )

    peak_speed = (
        max(speed_values)
        if speed_values
        else None
    )

    report = {

        "analysis_id": analysis_id,

        "source_video": os.path.basename(
            VIDEO_PATH
        ),

        "calibration": {
            "reference_distance_meters":
                REFERENCE_DISTANCE_METERS,

            "reference_pixel_distance":
                REFERENCE_PIXEL_DISTANCE,

            "meters_per_pixel":
                METERS_PER_PIXEL,

            "note":
                "Prototype calibration. "
                "Replace with measured camera "
                "calibration before using real-world "
                "speed values."
        },

        "traffic_model": {
            "density_weight": 0.45,
            "speed_weight": 0.40,
            "persistence_weight": 0.15,
            "persistence_frames":
                PERSISTENCE_FRAMES,
        },

        "video": {
            "fps": fps,
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "duration_seconds": duration,
        },

        "unique_vehicle_ids": len(
            unique_vehicle_ids
        ),

        "average_active_vehicles": round(
            avg_active,
            2
        ),

        "peak_active_vehicles": peak_active,

        "average_valid_estimated_speed_kmh": (
            round(avg_speed, 2)
            if avg_speed is not None
            else None
        ),

        "peak_valid_estimated_speed_kmh": (
            round(peak_speed, 2)
            if peak_speed is not None
            else None
        ),

        "traffic_states": dict(
            traffic_state_counts
        ),

        "frame_records": frame_records,

        "processing_seconds":
            processing_seconds,
    }

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2
        )

    print()
    print("=" * 65)
    print("PHASE 2.2 COMPLETE")
    print("=" * 65)
    print()
    print(
        f"Analysis ID: "
        f"{analysis_id}"
    )
    print(
        f"Unique vehicles: "
        f"{len(unique_vehicle_ids)}"
    )
    print(
        f"Average active vehicles: "
        f"{avg_active:.2f}"
    )
    print(
        f"Peak active vehicles: "
        f"{peak_active}"
    )

    if avg_speed is not None:
        print(
            f"Average estimated speed: "
            f"{avg_speed:.2f} km/h"
        )

    if peak_speed is not None:
        print(
            f"Peak estimated speed: "
            f"{peak_speed:.2f} km/h"
        )

    print(
        f"Traffic states: "
        f"{dict(traffic_state_counts)}"
    )

    print(
        f"Processing time: "
        f"{processing_seconds:.1f}s"
    )

    print()
    print(
        f"Output video: "
        f"{output_video}"
    )

    print(
        f"Report: "
        f"{report_path}"
    )

    print()

    return report


if __name__ == "__main__":
    analyze_video()

