const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function authHeaders(token) {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function readErr(res, fallback) {
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  return err.detail || fallback;
}

async function jsonFetch(url, opts = {}, fallback = "Request failed") {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await readErr(res, fallback));
  return res.json();
}

export async function loginUser(email, password) {
  return jsonFetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }, "Login failed");
}

export async function signupUser(email, password) {
  return jsonFetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }, "Signup failed");
}

export async function logoutUser(token) {
  if (!token) return null;
  return jsonFetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    headers: authHeaders(token),
  }, "Logout failed").catch(() => null);
}

export async function generateInitialReport(files, token) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return jsonFetch(`${API_BASE}/api/generate-initial-report`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  }, "Failed to generate initial report");
}

export async function generateFinalReport(initialReport, userInput, drawingType, reportId, token, assumedValues = {}) {
  const formData = new FormData();
  formData.append("initial_report", initialReport);
  formData.append("user_input", userInput);
  formData.append("drawing_type", drawingType || "foundation");
  if (reportId) formData.append("report_id", reportId);
  if (Object.keys(assumedValues).length > 0) {
    formData.append("assumed_values", JSON.stringify(assumedValues));
  }

  return jsonFetch(`${API_BASE}/api/generate-final-report`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  }, "Failed to generate final report");
}

export async function validateInput(missingFields, userAnswers, token) {
  return jsonFetch(`${API_BASE}/api/validate-input`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ missing_fields: missingFields, user_answers: userAnswers }),
  }, "Validation failed");
}

export async function queryRag(q, token, k = 5, contentType = null) {
  const params = new URLSearchParams({ q, k: String(k) });
  if (contentType) params.append("content_type", contentType);

  return jsonFetch(`${API_BASE}/api/rag/query?${params.toString()}`, {
    headers: authHeaders(token),
  }, "RAG query failed");
}

export async function fetchReports(token) {
  return jsonFetch(`${API_BASE}/api/reports`, {
    headers: authHeaders(token),
  }, "Failed to fetch reports");
}

export async function deleteReport(reportId, token) {
  return jsonFetch(`${API_BASE}/api/reports/${reportId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }, "Failed to delete report");
}

export async function fetchReportById(reportId, token) {
  return jsonFetch(`${API_BASE}/api/reports/${reportId}`, {
    headers: authHeaders(token),
  }, "Failed to fetch report");
}

export async function fetchReportMissingFields(reportId, token) {
  return jsonFetch(`${API_BASE}/api/reports/${reportId}/missing-fields`, {
    headers: authHeaders(token),
  }, "Failed to derive missing fields");
}

export async function downloadPdf(markdownContent, filename = "compliance_report", token) {
  const formData = new FormData();
  formData.append("markdown_content", markdownContent);
  formData.append("filename", filename);

  const res = await fetch(`${API_BASE}/api/download-pdf`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });

  if (!res.ok) throw new Error(await readErr(res, "PDF download failed"));

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
