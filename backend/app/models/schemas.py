from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class VehicleDetection(BaseModel):
    vehicle_id: Optional[int] = None
    vehicle_class: str
    confidence: float
    bbox: List[float]


class TrafficSnapshot(BaseModel):
    frame: int
    active_vehicles: int
    estimated_speed_kmh: Optional[float] = None
    traffic_state: str


class TrafficSummary(BaseModel):
    average_active_vehicles: float
    peak_active_vehicles: int
    average_estimated_speed_kmh: Optional[float] = None
    peak_estimated_speed_kmh: Optional[float] = None
    traffic_states: Dict[str, int]


class Alert(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    frame: Optional[int] = None
    message: str
    status: str = "ACTIVE"


class JourneySegment(BaseModel):
    from_camera: str
    to_camera: str
    distance_km: float
    duration_seconds: float
    average_speed_kmh: float


class VehicleJourney(BaseModel):
    journey_id: str
    vehicle_id: str
    plate: Optional[str] = None
    first_seen: str
    last_seen: str
    duration_minutes: float
    distance_km: float
    average_speed_kmh: float
    cameras: List[str]
    status: str
    segments: List[JourneySegment] = Field(
        default_factory=list
    )


class EmergencyCorridor(BaseModel):
    corridor_id: str
    name: str
    distance_km: float
    estimated_travel_time_minutes: float
    route_cost: float
    congestion_states: List[str]


class EmergencyRecommendation(BaseModel):
    recommended_corridor: str
    estimated_travel_time_minutes: float
    route_cost: float
    alternatives: List[EmergencyCorridor] = Field(
        default_factory=list
    )


class AnalysisResponse(BaseModel):
    analysis_id: str
    source_video: str
    frames_processed: int
    unique_vehicle_ids: int
    processing_seconds: float
    output_video: Optional[str] = None
    report: Dict[str, Any]
