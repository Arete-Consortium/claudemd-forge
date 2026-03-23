/**
 * API client for anchormd backend.
 * All authenticated requests send the token via Authorization header.
 */

const TOKEN_KEY = "anchormd_token";
const USER_KEY = "anchormd_user";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function storeAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function authHeaders() {
  const token = getStoredToken();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiGet(path) {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getGitHubLoginUrl() {
  return apiGet("/api/auth/github");
}

export async function exchangeCode(code) {
  return apiGet(`/api/auth/callback?code=${encodeURIComponent(code)}`);
}

export async function getMe() {
  return apiGet("/api/auth/me");
}

export async function listRepos() {
  return apiGet("/api/repos");
}

export async function scanRepo(repoUrl) {
  return apiPost("/api/scan", { repo_url: repoUrl });
}

export async function getScan(scanId) {
  return apiGet(`/api/scan/${scanId}`);
}

export async function scanAll(username) {
  return apiPost("/api/scan-all", { username });
}

export async function getBatchStatus(batchId) {
  return apiGet(`/api/scan-batch/${batchId}`);
}

export async function getAdminMetrics() {
  return apiGet("/api/admin/metrics");
}

export async function createDeepScanCheckout(repoUrl, email) {
  return apiPost("/api/checkout/deep-scan", { repo_url: repoUrl, email });
}

export async function getDeepScanReport(scanId) {
  return apiGet(`/api/scan/${scanId}/report`);
}

export async function getFixReport(scanId) {
  return apiGet(`/api/scan/${scanId}/fix-report`);
}

export async function pushPR(scanId, options = {}) {
  return apiPost(`/api/scan/${scanId}/push-pr`, options);
}
