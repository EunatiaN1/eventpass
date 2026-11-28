const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

export function apiUrl(path) {
  if (!API_BASE_URL) {
    throw new Error(
      "EventPass API is not configured. Set VITE_API_BASE_URL to your deployed FastAPI HTTPS URL in Vercel, then redeploy.",
    );
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
