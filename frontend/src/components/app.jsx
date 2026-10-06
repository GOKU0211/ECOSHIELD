import { useCallback, useEffect, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchAlerts, fetchHistory, fetchStatus } from "../api.js";

const SEV_LABEL = { 1: "HIGH", 2: "MEDIUM", 3: "LOW" };
const SEV_COLOR = { 1: "#E2554B", 2: "#E3A83D", 3: "#8A9A9F" };

const TIER_COLORS = {
  BASELINE: "#49C98A",
  ELEVATED: "#E3A83D",
  INTENSIVE: "#E2554B",
};
const tierColor = (t) => TIER_COLORS[t] || "#8A9A9F";

// Band cutoffs from backend/risk_engine/hysteresis.py score_to_band():
// BASELINE <= 30, ELEVATED <= 70, INTENSIVE > 70. Hardcoded there (not sent
// via /status), so hardcoded here to match — update both if you retune them.
const BASELINE_MAX = 30;
const ELEVATED_MAX = 70;

const fmtTime = (ts) =>
  new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const num = (v, d = 1) => (typeof v === "number" ? v.toFixed(d) : "—");

// --- Carbon estimate -------------------------------------------------------
// There's no carbon figure from the backend, so this is derived client-side
// from the same resource_snapshot you already poll. It's an estimate, not a
// measurement, and the UI labels it as such.
const ASSUMED_HOST_TDP_WATTS = 65;
const GRID_CARBON_INTENSITY_G_PER_KWH = 475;

function useCarbonTracker(resourceSnapshot, pollSeconds) {
  const totalRef = useRef(0);
  const [totalG, setTotalG] = useState(0);
  const [rateGPerHr, setRateGPerHr] = useState(0);

  useEffect(() => {
    if (!resourceSnapshot || typeof resourceSnapshot.cpu_percent !== "number") return;
    const watts = (resourceSnapshot.cpu_percent / 100) * ASSUMED_HOST_TDP_WATTS;
    const kwhThisTick = (watts / 1000) * (pollSeconds / 3600);
    const gThisTick = kwhThisTick * GRID_CARBON_INTENSITY_G_PER_KWH;
    totalRef.current += gThisTick;
    setTotalG(totalRef.current);
    setRateGPerHr(watts * (GRID_CARBON_INTENSITY_G_PER_KWH / 1000));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resourceSnapshot?.cpu_percent]);

  return { totalG, rateGPerHr };
}

// --- small presentational pieces -------------------------------------------

function Pill({ children, bg }) {
  return (
    <span className="es-pill" style={{ background: bg }}>
      {children}
    </span>
  );
}

function Panel({ title, children, className = "", actions = null }) {
  return (
    <section className={`es-panel ${className}`}>
      <div className="es-panel-head">
        <h2 className="es-panel-title">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

function Meter({ label, value, unit = "%", max = 100 }) {
  const pct = typeof value === "number" ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="es-meter">
      <div className="es-meter-head">
        <span>{label}</span>
        <span className="es-mono">
          {num(value)}
          {unit}
        </span>
      </div>
      <div className="es-meter-track">
        <div className="es-meter-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatCard({ label, value, unit = "", hint }) {
  return (
    <div className="es-stat-card">
      <div className="es-stat-label">{label}</div>
      <div className="es-stat-value es-mono">
        {typeof value === "number" ? num(value) : value ?? "—"}
        {typeof value === "number" && unit ? <span className="es-stat-unit">{unit}</span> : null}
      </div>
      {hint && <div className="es-stat-hint">{hint}</div>}
    </div>
  );
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="es-tooltip es-mono">
      <div>{fmtTime(r.timestamp)}</div>
      <div>risk {num(r.risk_score, 2)}</div>
      <div style={{ color: tierColor(r.active_tier) }}>{r.active_tier}</div>
    </div>
  );
}

// Circular risk gauge — pure SVG, no chart library needed.
function RiskGauge({ score, tier }) {
  const pct = Math.max(0, Math.min(100, score ?? 0));
  const color = tierColor(tier);
  const r = 70;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct / 100);

  return (
    <div className="es-gauge-wrap">
      <svg viewBox="0 0 180 180" className="es-gauge-svg">
        <circle cx="90" cy="90" r={r} fill="none" stroke="#2A353A" strokeWidth="14" />
        <circle
          cx="90"
          cy="90"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 90 90)"
          style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.3s ease" }}
        />
        <text x="90" y="86" textAnchor="middle" className="es-gauge-num" fill={color}>
          {num(score, 1)}
        </text>
        <text x="90" y="108" textAnchor="middle" className="es-gauge-sub" fill="#6F8085">
          / 100
        </text>
      </svg>
      <div className="es-tier-badge" style={{ borderColor: color, color }}>
        {tier || "—"}
      </div>
    </div>
  );
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [readings, setReadings] = useState([]);
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [alertSummary, setAlertSummary] = useState(null);
  const [error, setError] = useState(null);
  const [lastOk, setLastOk] = useState(null);
  const [now, setNow] = useState(Date.now());
  const timer = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, al] = await Promise.all([fetchStatus(), fetchHistory(), fetchAlerts()]);
      setStatus(s);
      setAlerts(al.alerts);
      setAlertSummary(al.summary);
      setReadings(h.readings);
      setEvents(h.tierEvents);
      setError(null);
      setLastOk(Date.now());
    } catch (e) {
      setError(e.message || "Cannot reach backend");
    }
  }, []);

  const pollSeconds = Math.max(2, status?.tier_config?.poll_interval_seconds ?? 5);
  const pollMs = pollSeconds * 1000;
  useEffect(() => {
    refresh();
    timer.current = setInterval(refresh, pollMs);
    return () => clearInterval(timer.current);
  }, [refresh, pollMs]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const tier = status?.active_tier;
  const color = tierColor(tier);
  const cfg = status?.tier_config;
  const res = status?.resource_snapshot;
  const ageSec = status ? now / 1000 - status.updated_at : null;
  const stale = ageSec !== null && ageSec > (cfg?.poll_interval_seconds ?? 5) * 3;
  const online = status && !error && !stale;
  const chartData = readings.map((r) => ({ ...r }));
  const tMin = readings[0]?.timestamp;
  const visibleEvents = events.filter((e) => tMin !== undefined && e.timestamp >= tMin);
  const carbon = useCarbonTracker(res, pollSeconds);

  return (
    <div className="es-page">
      {/* Scoped styles so this drop-in doesn't require touching the project's CSS file. */}
      <style>{`
        .es-page { font-family: inherit; color: #E6EDEF; max-width: 1280px; margin: 0 auto; padding: 24px; }
        .es-mono { font-family: "IBM Plex Mono", ui-monospace, monospace; }
        .es-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
        .es-header h1 { margin: 0; font-size: 28px; }
        .es-sub { margin: 2px 0 0; color: #8A9A9F; font-size: 14px; }
        .es-header-right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .es-pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #fff; letter-spacing: 0.02em; }
        .es-banner { background: #3a1f1f; border: 1px solid #E2554B; color: #f3c9c6; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
        .es-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; margin-bottom: 16px; }
        .es-panel { background: #161F22; border: 1px solid #2A353A; border-radius: 12px; padding: 18px; grid-column: span 4; }
        .es-panel.es-wide { grid-column: span 8; }
        .es-panel.es-full { grid-column: span 12; }
        .es-panel.es-center { display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .es-panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .es-panel-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: #8A9A9F; margin: 0; font-weight: 600; }
        .es-stats-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
        .es-stat-card { background: #161F22; border: 1px solid #2A353A; border-radius: 10px; padding: 14px; }
        .es-stat-label { font-size: 11px; color: #8A9A9F; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
        .es-stat-value { font-size: 22px; font-weight: 600; }
        .es-stat-unit { font-size: 13px; color: #8A9A9F; margin-left: 2px; }
        .es-stat-hint { font-size: 11px; color: #6F8085; margin-top: 4px; }
        .es-gauge-wrap { display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .es-gauge-svg { width: 170px; height: 170px; }
        .es-gauge-num { font-size: 30px; font-weight: 700; font-family: "IBM Plex Mono", monospace; }
        .es-gauge-sub { font-size: 11px; font-family: "IBM Plex Mono", monospace; }
        .es-tier-badge { border: 1.5px solid; border-radius: 999px; padding: 4px 14px; font-size: 13px; font-weight: 600; letter-spacing: 0.04em; }
        .es-kv { display: grid; grid-template-columns: 1fr auto; gap: 6px 10px; margin: 0; }
        .es-kv dt { color: #8A9A9F; font-size: 13px; }
        .es-kv dd { margin: 0; font-size: 13px; text-align: right; }
        .es-meter { margin-bottom: 12px; }
        .es-meter-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
        .es-meter-track { height: 6px; background: #2A353A; border-radius: 999px; overflow: hidden; }
        .es-meter-fill { height: 100%; background: #49C98A; border-radius: 999px; transition: width 0.4s ease; }
        .es-chart { width: 100%; height: 220px; }
        .es-legend { font-size: 11px; color: #6F8085; margin: 8px 0 0; }
        .es-muted { color: #6F8085; font-size: 13px; }
        .es-tooltip { background: #0E1517; border: 1px solid #2A353A; border-radius: 6px; padding: 8px 10px; font-size: 12px; }
        .es-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .es-table th { text-align: left; font-size: 11px; text-transform: uppercase; color: #8A9A9F; font-weight: 600; padding: 6px 8px; border-bottom: 1px solid #2A353A; }
        .es-table td { padding: 7px 8px; border-bottom: 1px solid #1d282b; }
        .es-table-wrap { max-height: 280px; overflow-y: auto; }
        .es-sev-chip { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
        .es-event-row { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px solid #1d282b; font-size: 13px; }
        @media (max-width: 900px) {
          .es-panel, .es-panel.es-wide { grid-column: span 12; }
          .es-stats-row { grid-template-columns: repeat(2, 1fr); }
        }
      `}</style>

      <header className="es-header">
        <div>
          <h1>EcoShield</h1>
          <p className="es-sub">Adaptive risk-driven monitoring · live view</p>
        </div>
        <div className="es-header-right">
          <Pill bg="#7c3aed">LIVE</Pill>
          <Pill bg="#334155">manual attacks</Pill>
          <Pill bg={online ? "#16a34a" : "#dc2626"}>
            {online ? "backend online" : stale ? "data stale" : "backend offline"}
          </Pill>
        </div>
      </header>

      {error && (
        <div className="es-banner">
          Cannot reach the backend. {lastOk ? `Last good data ${Math.round((now - lastOk) / 1000)}s ago.` : ""}
        </div>
      )}

      <div className="es-stats-row">
        <StatCard label="System CPU" value={res?.cpu_percent} unit="%" />
        <StatCard label="System memory" value={res?.memory_percent} unit="%" />
        <StatCard label="Monitor CPU" value={res?.process_cpu_percent} unit="%" />
        <StatCard label="Process memory" value={res?.process_memory_mb} unit=" MB" />
        <StatCard label="Alerts (live)" value={alertSummary?.total ?? 0} />
      </div>

      <div className="es-grid">
        <Panel title="Risk score" className="es-center">
          <RiskGauge score={status?.risk_score} tier={tier} />
        </Panel>

        <Panel title="Active tier configuration">
          <dl className="es-kv">
            <dt>Poll interval</dt>
            <dd className="es-mono">{cfg ? `${cfg.poll_interval_seconds}s` : "—"}</dd>
            <dt>Inspection depth</dt>
            <dd className="es-mono">{cfg?.inspection_depth ?? "—"}</dd>
            <dt>Logging verbosity</dt>
            <dd className="es-mono">{cfg?.logging_verbosity ?? "—"}</dd>
            <dt>Suricata ruleset</dt>
            <dd className="es-mono">{cfg?.suricata_ruleset ?? "—"}</dd>
          </dl>
        </Panel>

        <Panel title="Carbon (estimated)">
          <div className="es-gauge-wrap" style={{ gap: 4 }}>
            <div className="es-mono" style={{ fontSize: 32, fontWeight: 700, color: "#49C98A" }}>
              {num(carbon.totalG, 2)} <span style={{ fontSize: 14 }}>g CO₂e</span>
            </div>
            <div className="es-muted es-mono">{num(carbon.rateGPerHr, 1)} g/hr now</div>
          </div>
          <p className="es-legend">
            Estimated client-side from live CPU usage ({ASSUMED_HOST_TDP_WATTS}W TDP,{" "}
            {GRID_CARBON_INTENSITY_G_PER_KWH} g/kWh grid). Resets on reload.
          </p>
        </Panel>

        <Panel title="Resource usage" className="es-wide">
          <Meter label="System CPU" value={res?.cpu_percent} />
          <Meter label="System memory" value={res?.memory_percent} />
          <Meter label="Monitor process CPU" value={res?.process_cpu_percent} />
        </Panel>

        <Panel title={`Risk history (last ${readings.length})`} className="es-full">
          <div className="es-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#49C98A" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#49C98A" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#2A353A" strokeDasharray="2 4" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={fmtTime}
                  stroke="#6F8085"
                  tick={{ fontSize: 11, fontFamily: "IBM Plex Mono" }}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, BASELINE_MAX, ELEVATED_MAX, 100]}
                  stroke="#6F8085"
                  tick={{ fontSize: 11, fontFamily: "IBM Plex Mono" }}
                  width={36}
                />
                <ReferenceArea y1={0} y2={BASELINE_MAX} fill="#49C98A" fillOpacity={0.05} />
                <ReferenceArea y1={BASELINE_MAX} y2={ELEVATED_MAX} fill="#E3A83D" fillOpacity={0.05} />
                <ReferenceArea y1={ELEVATED_MAX} y2={100} fill="#E2554B" fillOpacity={0.05} />
                <ReferenceLine y={BASELINE_MAX} stroke="#E3A83D" strokeDasharray="3 3" strokeOpacity={0.6} label={{ value: "30", position: "right", fill: "#E3A83D", fontSize: 10 }} />
                <ReferenceLine y={ELEVATED_MAX} stroke="#E2554B" strokeDasharray="3 3" strokeOpacity={0.6} label={{ value: "70", position: "right", fill: "#E2554B", fontSize: 10 }} />
                <Tooltip content={<ChartTooltip />} />
                {visibleEvents.map((e) => (
                  <ReferenceLine
                    key={e.id}
                    x={e.timestamp}
                    stroke={tierColor(e.to_tier)}
                    strokeDasharray="4 3"
                    label={{ value: e.to_tier[0], position: "top", fill: tierColor(e.to_tier), fontSize: 11 }}
                  />
                ))}
                <Area type="monotone" dataKey="risk_score" stroke="#49C98A" strokeWidth={1.8} fill="url(#riskFill)" isAnimationActive={false} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="es-legend">Dashed lines mark tier changes (B = BASELINE, E = ELEVATED, I = INTENSIVE).</p>
        </Panel>

        <Panel title={`Live IDS alerts (${alertSummary?.total ?? 0})`} className="es-wide">
          {alerts.length === 0 ? (
            <p className="es-muted">No alerts yet. Run an attack from the Mininet CLI.</p>
          ) : (
            <>
              <p className="es-legend" style={{ marginBottom: 10 }}>
                {Object.entries(alertSummary?.by_signature ?? {})
                  .map(([sig, n]) => `${sig}: ${n}`)
                  .join("  ·  ")}
              </p>
              <div className="es-table-wrap">
                <table className="es-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Severity</th>
                      <th>Signature</th>
                      <th>Source → Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.map((a) => (
                      <tr key={a.id}>
                        <td className="es-mono">{fmtTime(a.timestamp)}</td>
                        <td>
                          <span
                            className="es-sev-chip es-mono"
                            style={{ color: SEV_COLOR[a.severity] || "#8A9A9F", border: `1px solid ${SEV_COLOR[a.severity] || "#8A9A9F"}` }}
                          >
                            {SEV_LABEL[a.severity] || "?"}
                          </span>
                        </td>
                        <td>{a.signature}</td>
                        <td className="es-mono es-muted">
                          {a.src_ip} → {a.dest_ip}:{a.dest_port ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Panel>

        <Panel title="Tier transitions" className="es-full">
          {events.length === 0 ? (
            <p className="es-muted">No tier changes recorded yet.</p>
          ) : (
            [...events].reverse().map((e) => (
              <div key={e.id} className="es-event-row">
                <span className="es-muted es-mono">{fmtTime(e.timestamp)}</span>
                <Pill bg={tierColor(e.from_tier)}>{e.from_tier}</Pill>
                <span className="es-muted">→</span>
                <Pill bg={tierColor(e.to_tier)}>{e.to_tier}</Pill>
              </div>
            ))
          )}
        </Panel>
      </div>
    </div>
  );
}