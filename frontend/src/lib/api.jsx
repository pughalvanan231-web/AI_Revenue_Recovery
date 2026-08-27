/**
 * api.jsx
 *
 * Trust Boundary: The typed client contract between the React frontend and the FastAPI backend.
 * Responsibility: Maps UI actions to strict API endpoints.
 * Invariant: The frontend must NEVER propose an action to the backend. It only passes raw events
 * for diagnosis, and the backend handles all deterministic decisions.
 */
import axios from "axios";

const BACKEND_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API, timeout: 20000 });

export const api = {
  listEvents: () => client.get(`/events?limit=60`).then((r) => r.data.events),
  newEvent: () => client.post(`/events/new`).then((r) => r.data),
  runPipeline: (event) =>
    client.post(`/pipeline/run`, { event }).then((r) => r.data),
  reservations: () =>
    client.get(`/state/reservations`).then((r) => r.data.rows),
  executors: () => client.get(`/state/executors`).then((r) => r.data.rows),
  metrics: () => client.get(`/metrics`).then((r) => r.data),
  reset: () => client.post(`/state/reset`).then((r) => r.data),
  failure: {
    concurrent: () =>
      client.post(`/failure/concurrent-webhooks`).then((r) => r.data),
    stale: () => client.post(`/failure/stale-reservation`).then((r) => r.data),
    duplicate: () =>
      client.post(`/failure/duplicate-executor`).then((r) => r.data),
  },
};

export const fmtINR = (paise) => {
  const rupees = (paise || 0) / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(rupees);
};

export const shortId = (s, n = 10) =>
  s ? s.slice(0, n) + (s.length > n ? "…" : "") : "—";

export const timeAgo = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  const sec = Math.max(1, Math.floor((Date.now() - d.getTime()) / 1000));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return d.toLocaleString();
};
