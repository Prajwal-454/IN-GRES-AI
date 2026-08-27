import axios from "axios";

// NOTE: no global Content-Type here — forcing application/json breaks
// multipart FormData uploads (voice mic -> /chat/voice). Axios sets the right
// header per request: JSON for object payloads, multipart boundary for FormData.
export const api = axios.create({
  baseURL: "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ingres_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** Exchange the stored refresh token for a fresh access token (once at a
 * time — concurrent 401s share the same promise). */
let refreshPromise: Promise<string | null> | null = null;

function tryRefresh(): Promise<string | null> {
  refreshPromise ??= (async () => {
    const refreshToken = localStorage.getItem("ingres_refresh_token");
    if (!refreshToken) return null;
    try {
      // Raw axios on purpose: no auth header, no recursion through interceptors.
      const { data } = await axios.post<{
        access_token: string;
        refresh_token?: string;
      }>("/api/auth/refresh", { refresh_token: refreshToken });
      localStorage.setItem("ingres_access_token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("ingres_refresh_token", data.refresh_token);
      }
      return data.access_token;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config ?? {};
    const url: string = typeof config.url === "string" ? config.url : "";
    const isAuthCall =
      url.includes("/auth/login") ||
      url.includes("/auth/refresh") ||
      url.includes("/auth/register");

    if (error.response?.status === 401 && !isAuthCall && !config._retry) {
      config._retry = true;
      const newToken = await tryRefresh();
      if (newToken) {
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${newToken}`,
        };
        return api(config);
      }
      localStorage.removeItem("ingres_access_token");
      localStorage.removeItem("ingres_refresh_token");
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register")
      ) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function getApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // Network / offline — no response from server (Render cold start, no internet, CORS)
    if (!error.response) {
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        return "You’re offline. Check your internet connection and try again.";
      }
      if (error.code === "ERR_NETWORK" || error.message === "Network Error") {
        return "Cannot reach IN-GRES AI servers. The backend may be waking up — please retry in a few seconds.";
      }
      return error.message || "Network error. Please check your connection and try again.";
    }
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
  }
  return "Something went wrong. Please try again.";
}

export function isNetworkError(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    if (!error.response) return true;
  }
  if (error instanceof TypeError && error.message === "Failed to fetch") return true;
  return false;
}