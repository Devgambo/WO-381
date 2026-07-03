const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function authHeaders(token) {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function readErr(res, fallback) {
  if (res.status === 429) {
    const retry = res.headers.get("Retry-After");
    return retry
      ? `Rate limit reached — try again in ${retry}s.`
      : "Rate limit reached — please slow down and retry shortly.";
  }
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  return err.detail || fallback;
}

async function jsonFetch(url, opts = {}, fallback = "Request failed") {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await readErr(res, fallback));
  return res.json();
}

export async function refreshSession(refreshToken) {
  // Use the raw, unwrapped fetch so the auth wrapper can call this during a
  // 401 retry without recursing.
  const raw = window.fetch.__original || window.fetch;
  const res = await raw(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) throw new Error(await readErr(res, "Session refresh failed"));
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

// Both generate endpoints are now async jobs: they return { job_id, status }.
// Poll getJobStatus / pollJob to retrieve the result.
export async function generateInitialReport(files, token) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return jsonFetch(`${API_BASE}/api/generate-initial-report`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  }, "Failed to start initial report");
}

export async function getJobStatus(jobId, token) {
  return jsonFetch(`${API_BASE}/api/jobs/${jobId}`, {
    headers: authHeaders(token),
  }, "Failed to fetch job status");
}

/**
 * Poll a background job until it finishes or fails.
 * @param {string} jobId
 * @param {string} token
 * @param {(job: object) => void} [onTick] called with each job snapshot
 * @param {{ intervalMs?: number, timeoutMs?: number, signal?: AbortSignal }} [opts]
 * @returns {Promise<object>} the job's `result` payload
 */
export async function pollJob(jobId, token, onTick, opts = {}) {
  const intervalMs = opts.intervalMs ?? 2000;
  const timeoutMs = opts.timeoutMs ?? 5 * 60 * 1000;
  const started = Date.now();

  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (opts.signal?.aborted) throw new Error("Cancelled");
    const { job } = await getJobStatus(jobId, token);
    if (onTick) onTick(job);
    if (job.status === "finished") return job.result;
    if (job.status === "failed") throw new Error(job.error || "Job failed");
    if (Date.now() - started > timeoutMs) throw new Error("Job timed out — please retry");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
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
  }, "Failed to start final report");
}

export async function validateInput(missingFields, userAnswers, token) {
  return jsonFetch(`${API_BASE}/api/validate-input`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ missing_fields: missingFields, user_answers: userAnswers }),
  }, "Validation failed");
}

export async function queryRag(q, token, k = 5, contentType = null, elementType = null) {
  const params = new URLSearchParams({ q, k: String(k) });
  if (contentType) params.append("content_type", contentType);
  if (elementType) params.append("element_type", elementType);

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
  // F11: Safari cancels the download if the URL is revoked before the
  // click event has fully propagated. Defer.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
