from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AlertEngine:
    """
    RoadLink traffic alert engine.

    Alert rules:
        CRITICAL traffic -> CRITICAL_TRAFFIC
        HIGH traffic     -> HIGH_TRAFFIC
        MODERATE traffic + speed < 15 km/h -> SLOW_TRAFFIC

    Alerts require condition persistence and are deduplicated
    while the same condition remains active.

    Speed-anomaly alerts are intentionally not implemented here
    because the current speed calibration is still prototype-level.
    """

    def __init__(
        self,
        persistence_required: int = 3,
    ):
        self.persistence_required = (
            persistence_required
        )

        self.condition_counts: dict[
            str, int
        ] = {}

        self.active_alerts: dict[
            str, dict[str, Any]
        ] = {}

        self.alert_history: list[
            dict[str, Any]
        ] = []

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _condition_key(
        self,
        alert_type: str,
    ) -> str:
        return alert_type

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        traffic_snapshot: dict[str, Any],
    ) -> dict[str, Any]:

        alert = {
            "alert_id": (
                f"ALERT-"
                f"{len(self.alert_history) + 1:05d}"
            ),
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "traffic_state": traffic_snapshot.get(
                "traffic_state"
            ),
            "average_speed_kmh": traffic_snapshot.get(
                "average_speed_kmh"
            ),
            "active_vehicle_count": traffic_snapshot.get(
                "active_vehicle_count"
            ),
            "traffic_score": traffic_snapshot.get(
                "traffic_score"
            ),
            "created_at": self._utc_timestamp(),
            "status": "ACTIVE",
        }

        self.active_alerts[
            alert_type
        ] = alert

        self.alert_history.append(
            alert
        )

        return alert

    def evaluate(
        self,
        traffic_snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:

        traffic_state = traffic_snapshot.get(
            "traffic_state",
            "LOW",
        )

        average_speed = traffic_snapshot.get(
            "average_speed_kmh"
        )

        conditions: dict[
            str, tuple[str, str]
        ] = {}

        if traffic_state == "CRITICAL":
            conditions[
                "CRITICAL_TRAFFIC"
            ] = (
                "CRITICAL",
                "Critical traffic congestion detected.",
            )

        elif traffic_state == "HIGH":
            conditions[
                "HIGH_TRAFFIC"
            ] = (
                "HIGH",
                "High traffic congestion detected.",
            )

        elif (
            traffic_state == "MODERATE"
            and average_speed is not None
            and average_speed < 15.0
        ):
            conditions[
                "SLOW_TRAFFIC"
            ] = (
                "MEDIUM",
                "Moderate traffic with very low average speed detected.",
            )

        generated_alerts: list[
            dict[str, Any]
        ] = []

        # Process currently active conditions.
        for alert_type, (
            severity,
            message,
        ) in conditions.items():

            self.condition_counts[
                alert_type
            ] = (
                self.condition_counts.get(
                    alert_type,
                    0,
                )
                + 1
            )

            # Already active -> don't duplicate.
            if alert_type in self.active_alerts:
                continue

            if (
                self.condition_counts[
                    alert_type
                ]
                >= self.persistence_required
            ):
                generated_alerts.append(
                    self._create_alert(
                        alert_type=alert_type,
                        severity=severity,
                        message=message,
                        traffic_snapshot=traffic_snapshot,
                    )
                )

        # Reset conditions that are no longer active.
        for alert_type in list(
            self.condition_counts.keys()
        ):
            if alert_type not in conditions:
                self.condition_counts[
                    alert_type
                ] = 0

                self.active_alerts.pop(
                    alert_type,
                    None,
                )

        return generated_alerts

    def evaluate_sequence(
        self,
        traffic_snapshots: list[
            dict[str, Any]
        ],
    ) -> list[dict[str, Any]]:

        alerts: list[
            dict[str, Any]
        ] = []

        for snapshot in traffic_snapshots:
            alerts.extend(
                self.evaluate(snapshot)
            )

        return alerts

    def reset(self) -> None:
        self.condition_counts.clear()
        self.active_alerts.clear()
        self.alert_history.clear()


alert_engine = AlertEngine()
