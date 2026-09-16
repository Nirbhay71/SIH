const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function startVerification({ travel_direction, latitude, longitude }) {
  const res = await fetch(`${BASE}/verification/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ travel_direction, latitude, longitude }),
  });
  return handle(res);
}

export async function uploadDocument(sessionId, file, documentTypeHint) {
  const form = new FormData();
  form.append("file", file);
  if (documentTypeHint) form.append("document_type_hint", documentTypeHint);
  const res = await fetch(`${BASE}/verification/${sessionId}/document`, { method: "POST", body: form });
  return handle(res);
}

export async function uploadFace(sessionId, file, simulateMismatch = false) {
  const form = new FormData();
  form.append("file", file);
  form.append("simulate_mismatch", simulateMismatch ? "true" : "false");
  const res = await fetch(`${BASE}/verification/${sessionId}/face`, { method: "POST", body: form });
  return handle(res);
}

export async function getResult(sessionId) {
  const res = await fetch(`${BASE}/verification/${sessionId}/result`);
  return handle(res);
}

export async function submitDecision(sessionId, decision) {
  const res = await fetch(`${BASE}/verification/${sessionId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  return handle(res);
}

export async function verifyChain() {
  const res = await fetch(`${BASE}/audit/verify-chain`);
  return handle(res);
}

function authHeader(username, password) {
  return { Authorization: "Basic " + btoa(`${username}:${password}`) };
}

export async function listWatchlist(creds) {
  const res = await fetch(`${BASE}/admin/watchlist`, { headers: authHeader(creds.username, creds.password) });
  return handle(res);
}

export async function addWatchlist(creds, referenceLabel, file) {
  const form = new FormData();
  form.append("reference_label", referenceLabel);
  form.append("file", file);
  const res = await fetch(`${BASE}/admin/watchlist`, {
    method: "POST",
    headers: authHeader(creds.username, creds.password),
    body: form,
  });
  return handle(res);
}

export async function deleteWatchlist(creds, id) {
  const res = await fetch(`${BASE}/admin/watchlist/${id}`, {
    method: "DELETE",
    headers: authHeader(creds.username, creds.password),
  });
  return handle(res);
}

export function openPipelineSocket(sessionId) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${window.location.host}/api/verification/${sessionId}/stream`);
}
