const API_BASE = "http://localhost:8000";

function authHeaders(token) {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Login failed");
  }
  return res.json();
}

export async function signupUser(email, password) {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Signup failed");
  }
  return res.json();
}

export async function generateInitialReport(files, token) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  const res = await fetch(`${API_BASE}/api/generate-initial-report`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to generate initial report");
  }
  return res.json();
}

export async function generateFinalReport(initialReport, userInput, reportId, token) {
  const formData = new FormData();
  formData.append("initial_report", initialReport);
  formData.append("user_input", userInput);
  if (reportId) formData.append("report_id", reportId);

  const res = await fetch(`${API_BASE}/api/generate-final-report`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to generate final report");
  }
  return res.json();
}

export async function fetchReports(token) {
  const res = await fetch(`${API_BASE}/api/reports`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to fetch reports");
  }
  return res.json();
}

export async function fetchReportById(reportId, token) {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to fetch report");
  }
  return res.json();
}

export async function downloadPdf(markdownContent, filename = "compliance_report") {
  const formData = new FormData();
  formData.append("markdown_content", markdownContent);
  formData.append("filename", filename);

  const res = await fetch(`${API_BASE}/api/download-pdf`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "PDF download failed");
  }

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
