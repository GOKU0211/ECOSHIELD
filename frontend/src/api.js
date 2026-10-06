// Thin client for the backend. Paths match the backend routes: GET /status, GET /history, GET /alerts.
// In dev these go through the Vite proxy (/api -> backend). For a deployed build,
// set VITE_API_BASE to the backend's full URL (and enable CORS on the backend).
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function getJson(path) {
  const res = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} returned HTTP ${res.status}`);
  return res.json();
}

export const fetchStatus = () => getJson("/status");

export async function fetchHistory() {
  const data = await getJson("/history");
  // Sort defensively by time so the chart is correct whichever order the backend returns.
  const readings = [...(data.readings || [])].sort((a, b) => a.timestamp - b.timestamp);
  const tierEvents = [...(data.tier_events || [])].sort((a, b) => a.timestamp - b.timestamp);
  return { readings, tierEvents };
}
export async function fetchAlerts(limit = 50) {
  const data = await getJson(`/alerts?limit=${limit}`);
  return { alerts: data.alerts || [], summary: data.summary || null };
}