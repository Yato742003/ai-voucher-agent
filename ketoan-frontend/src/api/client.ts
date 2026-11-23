const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("access_token", token);
  else localStorage.removeItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (resp.status === 401) {
    setToken(null);
    window.location.href = "/login";
    throw new ApiError(401, "Phiên đăng nhập đã hết — vui lòng đăng nhập lại");
  }

  if (!resp.ok) {
    let detail = `Lỗi ${resp.status}`;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore parse error, giữ detail mặc định */
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await resp.json()) as T;
  return (await resp.blob()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export async function login(username: string, password: string): Promise<string> {
  const resp = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: "Đăng nhập thất bại" }));
    throw new ApiError(resp.status, body.detail || "Đăng nhập thất bại");
  }
  const data = await resp.json();
  return data.access_token as string;
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = getToken();
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: "Không xuất được file" }));
    throw new ApiError(resp.status, body.detail || "Không xuất được file");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
