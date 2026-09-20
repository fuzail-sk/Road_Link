import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Ambulance,
  Car,
  CheckCircle2,
  Clock3,
  Gauge,
  MapPinned,
  Play,
  Route,
  ShieldCheck,
  Video,
} from "lucide-react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text || response.statusText}`);
  }

  return response.json();
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function getTrafficState(report) {
  if (report?.traffic_state) return report.traffic_state;
  if (report?.trafficState) return report.trafficState;

  const states = report?.traffic_states;

  if (states && typeof states === "object") {
    const entries = Object.entries(states);

    if (entries.length) {
      entries.sort((a, b) => Number(b[1]) - Number(a[1]));
      return entries[0][0];
    }
  }

  return "UNKNOWN";
}

function getTrafficScore(report) {
  if (report?.average_traffic_score !== undefined) {
    return report.average_traffic_score;
  }

  if (report?.averageTrafficScore !== undefined) {
    return report.averageTrafficScore;
  }

  const records = report?.frame_records;

  if (Array.isArray(records) && records.length) {
    const scores = records
      .map((record) => Number(record.traffic_score))
      .filter((value) => Number.isFinite(value));

    if (scores.length) {
      return scores.reduce((sum, value) => sum + value, 0) / scores.length;
    }
  }

  return null;
}

function normalizeTrafficReport(payload) {
  /*
   * RoadLink video API returns:
   *
   * {
   *   status,
   *   message,
   *   analysis: {
   *     analysis_id,
   *     source_video,
   *     processing,
   *     vehicles,
   *     speed,
   *     traffic,
   *     calibration,
   *     report: "/outputs/...json"
   *   }
   * }
   */

  const report = payload?.analysis || payload || {};

  const traffic = report?.traffic || {};
  const vehicles = report?.vehicles || {};
  const speed = report?.speed || {};
  const processing = report?.processing || {};

  let videoUrl = null;

  /*
   * The backend explicitly returns the generated MP4 path.
   * Use that path directly instead of deriving it from the JSON report.
   */
  if (report?.output_video) {
    videoUrl = `${API_BASE}${report.output_video}`;
  } else if (report?.report) {
    const reportPath = String(report.report);

    if (reportPath.endsWith(".json")) {
      const videoPath = reportPath.replace(/\.json$/, ".mp4");
      videoUrl = `${API_BASE}${videoPath}`;
    }
  }

  return {
    analysisId:
      report?.analysis_id ||
      report?.analysisId ||
      "—",

    sourceVideo:
      report?.source_video ||
      report?.sourceVideo ||
      "Sample video",

    videoUrl,

    trafficState:
      getTrafficState(traffic) !== "UNKNOWN"
        ? getTrafficState(traffic)
        : getTrafficState(report),

    activeVehicles:
      vehicles?.average_active_vehicles ??
      report?.average_active_vehicles ??
      null,

    peakVehicles:
      vehicles?.peak_active_vehicles ??
      report?.peak_active_vehicles ??
      null,

    averageSpeed:
      speed?.average_estimated_speed_kmh ??
      report?.average_estimated_speed_kmh ??
      null,

    peakSpeed:
      speed?.peak_estimated_speed_kmh ??
      report?.peak_estimated_speed_kmh ??
      null,

    trafficScore:
      traffic?.average_traffic_score ??
      report?.average_traffic_score ??
      null,

    uniqueVehicles:
      vehicles?.unique_vehicle_ids ??
      report?.unique_vehicle_ids ??
      null,

    processingSeconds:
      processing?.processing_seconds ??
      report?.processing_seconds ??
      null,

    calibration:
      report?.calibration ||
      null,

    alerts:
      report?.alerts ||
      {
        total_generated: 0,
        by_type: {},
        items: [],
      },
  };
}

function normalizeJourney(payload) {
  /*
   * RoadLink journey API:
   *
   * {
   *   success: true,
   *   controlled_test: true,
   *   data: {
   *     vehicle_id,
   *     plate,
   *     plate_status,
   *     journey: {
   *       distance_km,
   *       duration_minutes,
   *       camera_count,
   *       ...
   *     }
   *   }
   * }
   */

  const data = payload?.data || payload || {};
  const journey = data?.journey || {};

  return {
    vehicleId:
      data?.vehicle_id ||
      journey?.vehicle_id ||
      "—",

    plate:
      data?.plate ||
      "—",

    plateStatus:
      data?.plate_status ||
      "—",

    distance:
      journey?.distance_km ??
      null,

    duration:
      journey?.duration_minutes ??
      null,

    cameras:
      journey?.camera_count ??
      journey?.cameras_observed?.length ??
      null,
  };
}

function normalizeEmergency(payload) {
  /*
   * RoadLink emergency API:
   *
   * {
   *   success: true,
   *   controlled_test: true,
   *   data: {
   *     recommendation: {
   *       corridor_id,
   *       name,
   *       total_distance_km,
   *       estimated_travel_time_minutes,
   *       ...
   *     },
   *     alternatives: [],
   *     decision_support_only,
   *     live_navigation,
   *     signal_control
   *   }
   * }
   */

  const data = payload?.data || payload || {};
  const recommendation = data?.recommendation || {};

  return {
    corridor:
      recommendation?.corridor_id ||
      "—",

    name:
      recommendation?.name ||
      "—",

    distance:
      recommendation?.total_distance_km ??
      null,

    travelTime:
      recommendation?.estimated_travel_time_minutes ??
      null,

    decisionSupportOnly:
      data?.decision_support_only ?? true,
  };
}

function MetricCard({ icon: Icon, label, value, suffix }) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <div className="metric-icon">
          <Icon size={18} strokeWidth={1.8} />
        </div>

        <span>{label}</span>
      </div>

      <div className="metric-number">
        {value}
        {value !== "—" && suffix && (
          <small>{suffix}</small>
        )}
      </div>
    </div>
  );
}

function PanelHeader({ eyebrow, title, icon: Icon }) {
  return (
    <div className="panel-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
      </div>

      <div className="panel-header-icon">
        <Icon size={19} strokeWidth={1.8} />
      </div>
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [traffic, setTraffic] = useState(null);
  const [journey, setJourney] = useState(null);
  const [emergency, setEmergency] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadControlRoom() {
      try {
        const [health, journeyResult, emergencyResult] =
          await Promise.all([
            request("/api/health"),
            request("/api/journeys/test", { method: "POST" }),
            request("/api/emergency/test", { method: "POST" }),
          ]);

        setApiOnline(health?.status === "online");
        setJourney(normalizeJourney(journeyResult));
        setEmergency(normalizeEmergency(emergencyResult));
      } catch (err) {
        setApiOnline(false);
        setError(err.message);
      }
    }

    loadControlRoom();
  }, []);

  async function analyzeSampleVideo() {
    setAnalyzing(true);
    setError("");

    try {
      const result = await request("/api/video/analyze-sample", {
        method: "POST",
      });

      setTraffic(normalizeTrafficReport(result));
      setApiOnline(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  const trafficState = traffic?.trafficState || "NOT ANALYZED";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-block">
            <div className="brand-mark">RL</div>

            <div>
              <div className="brand-name">ROADLINK</div>
              <div className="brand-subtitle">
                Traffic Intelligence & Response Control Room
              </div>
            </div>
          </div>

          <div className="connection-status">
            <span
              className={`connection-dot ${
                apiOnline ? "online" : ""
              }`}
            />

            <span>
              API {apiOnline ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
        </div>
      </header>

      <main className="main-content">
        {error && (
          <div className="error-banner">
            <AlertTriangle size={17} />
            <span>{error}</span>
          </div>
        )}

        <section className="hero-section">
          <div>
            <div className="eyebrow">CURRENT ANALYSIS</div>
            <h1>Traffic Overview</h1>

            <p className="hero-description">
              Road traffic intelligence derived from the selected recorded
              video source.
            </p>

            <div className="hero-context">
              <span>RECORDED VIDEO ANALYSIS</span>
              <span className="hero-divider">/</span>
              <span>DECISION SUPPORT</span>
              <span className="hero-divider">/</span>
              <span>NO LIVE SIGNAL CONTROL</span>
            </div>
          </div>

          <div className="state-box">
            <span>TRAFFIC STATE</span>

            <div className="state-value">
              <span className="state-indicator" />
              {trafficState}
            </div>
          </div>
        </section>

        <section className="metrics-grid">
          <MetricCard
            icon={Car}
            label="AVERAGE ACTIVE VEHICLES"
            value={formatNumber(traffic?.activeVehicles, 2)}
          />

          <MetricCard
            icon={Gauge}
            label="AVERAGE SPEED"
            value={formatNumber(traffic?.averageSpeed, 1)}
            suffix="km/h"
          />

          <MetricCard
            icon={Activity}
            label="TRAFFIC SCORE"
            value={formatNumber(traffic?.trafficScore, 1)}
          />

          <MetricCard
            icon={Route}
            label="UNIQUE VEHICLES"
            value={formatNumber(traffic?.uniqueVehicles, 0)}
          />
        </section>

        <section className="dashboard-grid">
          <div className="panel video-panel">
            <PanelHeader
              eyebrow="VIDEO INTELLIGENCE"
              title="Sample Road Analysis"
              icon={Video}
            />

            <div className="video-area">
              <div className="video-control-strip">
                <div className="video-control-left">
                  <span className="recorded-badge">
                    <span className="status-dot"></span>
                    RECORDED INPUT
                  </span>

                  <span className="video-mode-label">
                    PROCESSED ANALYSIS
                  </span>
                </div>

                <span className="not-live-label">
                  NOT LIVE CCTV
                </span>
              </div>

              {traffic?.videoUrl ? (
                <div className="processed-video-container">
                  <video
                    className="processed-video"
                    controls
                    playsInline
                    preload="metadata"
                    key={traffic.videoUrl}
                  >
                    <source src={traffic.videoUrl} type="video/mp4" />
                    Your browser does not support HTML5 video.
                  </video>

                  <div className="video-info-row">
                    <div>
                      <span className="video-info-label">SOURCE</span>
                      <strong>
                        {traffic?.sourceVideo || "ParkingVideo.mp4"}
                      </strong>
                    </div>

                    <div>
                      <span className="video-info-label">ANALYSIS ID</span>
                      <strong>{traffic?.analysisId || "—"}</strong>
                    </div>

                    <div>
                      <span className="video-info-label">OUTPUT</span>
                      <strong>H.264 / MP4</strong>
                    </div>
                  </div>

                  <div className="video-description">
                    Vehicle detection, persistent tracking, speed estimation
                    and traffic-state analysis generated from the recorded
                    video.
                  </div>
                </div>
              ) : (
                <div className="video-empty-state">
                  <div className="video-placeholder-icon">
                    <Video size={34} strokeWidth={1.5} />
                  </div>

                  <div className="video-source">
                    {traffic?.sourceVideo || "ParkingVideo.mp4"}
                  </div>

                  <div className="video-description">
                    Recorded road video used as the prototype input.
                  </div>
                </div>
              )}

              <button
                className="primary-button"
                onClick={analyzeSampleVideo}
                disabled={analyzing}
              >
                <Play size={16} fill="currentColor" />

                {analyzing
                  ? "ANALYZING VIDEO..."
                  : traffic?.videoUrl
                    ? "REANALYZE SAMPLE VIDEO"
                    : "ANALYZE SAMPLE VIDEO"}
              </button>

              {traffic && (
                <div className="analysis-meta">
                  <div>
                    <span>Processing</span>
                    <strong>
                      {formatNumber(traffic.processingSeconds, 1)} s
                    </strong>
                  </div>

                  <div>
                    <span>Peak vehicles</span>
                    <strong>
                      {formatNumber(traffic.peakVehicles, 0)}
                    </strong>
                  </div>

                  <div>
                    <span>Peak speed</span>
                    <strong>
                      {formatNumber(traffic.peakSpeed, 1)} km/h
                    </strong>
                  </div>
                </div>
              )}

              {traffic?.calibration?.real_world_calibration_required && (
                <div className="calibration-note">
                  <AlertTriangle size={15} />

                  <span>
                    Prototype speed calibration. Real-world deployment
                    requires camera and road-distance calibration.
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="panel">
            <PanelHeader
              eyebrow="VEHICLE JOURNEY"
              title="Cross-Camera Reconstruction"
              icon={MapPinned}
            />

            {journey ? (
              <div className="detail-list">
                <DetailRow
                  label="Vehicle ID"
                  value={journey.vehicleId}
                />

                <DetailRow
                  label="Number plate"
                  value={journey.plate}
                />

                <DetailRow
                  label="Plate status"
                  value={journey.plateStatus}
                />

                <DetailRow
                  label="Distance"
                  value={`${formatNumber(
                    journey.distance,
                    1
                  )} km`}
                />

                <DetailRow
                  label="Journey duration"
                  value={`${formatNumber(
                    journey.duration,
                    1
                  )} min`}
                />

                <DetailRow
                  label="Cameras observed"
                  value={formatNumber(journey.cameras, 0)}
                />

                {journey.averageSpeed !== undefined &&
                  journey.averageSpeed !== null && (
                    <DetailRow
                      label="Average journey speed"
                      value={`${formatNumber(
                        journey.averageSpeed,
                        1
                      )} km/h`}
                    />
                  )}

                {journey.status && (
                  <DetailRow
                    label="Journey status"
                    value={journey.status}
                  />
                )}
              </div>
            ) : (
              <div className="empty-state">
                <Clock3 size={18} />
                <span>Journey data unavailable.</span>
              </div>
            )}
          </div>

          <div className="panel">
            <PanelHeader
              eyebrow="EMERGENCY RESPONSE"
              title="Corridor Recommendation"
              icon={Ambulance}
            />

            {emergency ? (
              <>
                <div className="recommendation-box">
                  <div className="recommendation-label">
                    RECOMMENDED CORRIDOR
                  </div>

                  <div className="recommendation-name">
                    {emergency.corridor}
                  </div>

                  <div className="recommendation-road">
                    {emergency.name}
                  </div>
                </div>

                <div className="detail-list compact">
                  <DetailRow
                    label="Distance"
                    value={`${formatNumber(
                      emergency.distance,
                      1
                    )} km`}
                  />

                  <DetailRow
                    label="Estimated travel time"
                    value={`${formatNumber(
                      emergency.travelTime,
                      2
                    )} min`}
                  />
                </div>

                {Array.isArray(emergency.alternatives) &&
                  emergency.alternatives.length > 0 && (
                    <div className="alternative-routes">
                      <div className="section-mini-title">
                        ALTERNATIVE CORRIDORS
                      </div>

                      {emergency.alternatives.map((route, index) => (
                        <div
                          className="alternative-route"
                          key={route.corridor_id || route.id || index}
                        >
                          <div>
                            <strong>
                              {route.name ||
                                route.corridor_id ||
                                `Alternative ${index + 1}`}
                            </strong>

                            <span>
                              {route.total_distance_km !== undefined
                                ? `${formatNumber(
                                    route.total_distance_km,
                                    1
                                  )} km`
                                : "Distance unavailable"}
                            </span>
                          </div>

                          <strong>
                            {route.estimated_travel_time_minutes !==
                              undefined
                              ? `${formatNumber(
                                  route.estimated_travel_time_minutes,
                                  2
                                )} min`
                              : "—"}
                          </strong>
                        </div>
                      ))}
                    </div>
                  )}

                <div className="notice">
                  <ShieldCheck size={15} />

                  <span>
                    Decision support only. RoadLink does not currently
                    control traffic signals.
                  </span>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <Ambulance size={18} />
                <span>Emergency recommendation unavailable.</span>
              </div>
            )}
          </div>

          <div className="panel">
            <PanelHeader
              eyebrow="TRAFFIC ALERTS"
              title="Alert Monitor"
              icon={AlertTriangle}
            />

            {traffic ? (
              <div className="alert-monitor">
                <div className="alert-summary">
                  <div>
                    <span>Total generated</span>
                    <strong>
                      {formatNumber(
                        traffic.alerts?.total_generated ?? 0,
                        0
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Current state</span>
                    <strong>
                      {(traffic.alerts?.total_generated ?? 0) > 0
                        ? "REVIEW"
                        : "NO ACTIVE ALERTS"}
                    </strong>
                  </div>
                </div>

                {(traffic.alerts?.total_generated ?? 0) === 0 ? (
                  <div className="alert-clear">
                    <CheckCircle2 size={16} />
                    <span>
                      No traffic alerts were generated during this
                      recorded-video analysis.
                    </span>
                  </div>
                ) : (
                  <div className="alert-items">
                    {Array.isArray(traffic.alerts?.items) &&
                    traffic.alerts.items.length > 0 ? (
                      traffic.alerts.items.slice(0, 5).map((alert, index) => (
                        <div
                          className="alert-item"
                          key={alert.id || index}
                        >
                          <AlertTriangle size={15} />
                          <div>
                            <strong>
                              {alert.type || "TRAFFIC ALERT"}
                            </strong>
                            <span>
                              {alert.message ||
                                alert.description ||
                                "Alert generated by traffic intelligence."}
                            </span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="alert-clear">
                        <AlertTriangle size={16} />
                        <span>
                          Alert events were generated, but detailed event
                          records are not available in this response.
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state">
                <AlertTriangle size={18} />
                <span>Alert analysis not run.</span>
              </div>
            )}
          </div>
          <div className="panel">
            <PanelHeader
              eyebrow="VEHICLE INTELLIGENCE"
              title="Detection Summary"
              icon={Video}
            />

            {traffic ? (
              <div className="vehicle-summary">
                <div className="vehicle-summary-grid">
                  <div className="vehicle-summary-item">
                    <span>Unique vehicles</span>
                    <strong>
                      {formatNumber(traffic.uniqueVehicles, 0)}
                    </strong>
                  </div>

                  <div className="vehicle-summary-item">
                    <span>Average active</span>
                    <strong>
                      {formatNumber(traffic.activeVehicles, 2)}
                    </strong>
                  </div>

                  <div className="vehicle-summary-item">
                    <span>Peak active</span>
                    <strong>
                      {formatNumber(traffic.peakVehicles, 0)}
                    </strong>
                  </div>

                  <div className="vehicle-summary-item">
                    <span>Average speed</span>
                    <strong>
                      {formatNumber(traffic.averageSpeed, 1)} km/h
                    </strong>
                  </div>

                  <div className="vehicle-summary-item">
                    <span>Peak speed</span>
                    <strong>
                      {formatNumber(traffic.peakSpeed, 1)} km/h
                    </strong>
                  </div>

                  <div className="vehicle-summary-item">
                    <span>Traffic score</span>
                    <strong>
                      {formatNumber(traffic.trafficScore, 1)}
                    </strong>
                  </div>
                </div>

                <div className="vehicle-summary-note">
                  Aggregate results from the analyzed recorded video.
                  Individual vehicle history is reconstructed by the
                  tracking pipeline and is not exposed as a live city-wide
                  vehicle database in this prototype.
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <Video size={18} />
                <span>Vehicle analysis not run.</span>
              </div>
            )}
          </div>
          <div className="panel">
            <PanelHeader
              eyebrow="SYSTEM"
              title="Analysis Status"
              icon={CheckCircle2}
            />

            <div className="status-list">
              <div className="status-row">
                <span>Backend API</span>
                <strong className={apiOnline ? "success" : "danger"}>
                  {apiOnline ? "ONLINE" : "OFFLINE"}
                </strong>
              </div>

              <div className="status-row">
                <span>Traffic analysis</span>
                <strong className={traffic ? "success" : ""}>
                  {traffic ? "AVAILABLE" : "NOT RUN"}
                </strong>
              </div>

              <div className="status-row">
                <span>Journey service</span>
                <strong className={journey ? "success" : ""}>
                  {journey ? "AVAILABLE" : "NOT RUN"}
                </strong>
              </div>

              <div className="status-row">
                <span>Emergency service</span>
                <strong className={emergency ? "success" : ""}>
                  {emergency ? "AVAILABLE" : "NOT RUN"}
                </strong>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div>
          ROADLINK <span>·</span> Traffic Intelligence Prototype
        </div>

        <div>
          Recorded video analysis <span>·</span> Decision support
        </div>
      </footer>
    </div>
  );
}

export default App;







