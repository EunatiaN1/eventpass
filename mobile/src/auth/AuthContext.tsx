import * as SecureStore from "expo-secure-store";
import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Platform } from "react-native";

const API_BASE = (process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "eventpass.session.jwt";

export type EventPassUser = {
  id: string;
  email: string;
  wallet: string;
  role: string;
};

type RequestOptions = RequestInit & { token?: string | null };

type AuthContextValue = {
  user: EventPassUser | null;
  isLoading: boolean;
  api: <T>(path: string, options?: RequestOptions) => Promise<T>;
  requestCode: (email: string) => Promise<{ dev_sandbox_otp?: string }>;
  verifyCode: (email: string, code: string) => Promise<EventPassUser>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function errorMessage(status: number, detail?: unknown) {
  if (typeof detail === "string" && detail) return detail;
  if (status === 410) return "Code expired. Request a new one.";
  if (status === 429) return "Too many attempts. Wait a moment and try again.";
  if (status === 401) return "Invalid code. Check the 6 digits and try again.";
  if (status === 503) return "Email delivery is unavailable. Please try again shortly.";
  return "We couldn't complete that request. Please try again.";
}

async function fetchApi<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, headers, ...requestOptions } = options;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...requestOptions,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(Platform.OS !== "web" && token ? { Authorization: `Bearer ${token}` } : {}),
        ...(headers as Record<string, string> | undefined),
      },
    });
  } catch {
    throw new Error("Network error. Check your connection and try again.");
  }

  const body = await response.text();
  let data: any = null;
  try {
    data = body ? JSON.parse(body) : null;
  } catch {
    data = body;
  }
  if (!response.ok) {
    const detail = Array.isArray(data?.detail) ? undefined : data?.detail;
    throw new Error(errorMessage(response.status, detail));
  }
  return data as T;
}

function mapUser(data: any): EventPassUser {
  return {
    id: data.user_id || data.id,
    email: data.email || "",
    wallet: data.wallet,
    role: data.role || "buyer",
  };
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<EventPassUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const api = useCallback(<T,>(path: string, options: RequestOptions = {}) =>
    fetchApi<T>(path, { ...options, token: options.token ?? token }), [token]);

  useEffect(() => {
    let mounted = true;
    const loadSession = async () => {
      try {
        const storedToken = Platform.OS === "web" ? null : await SecureStore.getItemAsync(TOKEN_KEY);
        if (storedToken) setToken(storedToken);
        const session = await fetchApi<any>("/api/auth/me", { token: storedToken });
        if (mounted) setUser(mapUser(session));
      } catch {
        if (mounted) {
          setUser(null);
          setToken(null);
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    };
    loadSession();
    return () => { mounted = false; };
  }, []);

  const requestCode = useCallback((email: string) =>
    fetchApi<{ dev_sandbox_otp?: string }>("/api/auth/otp", {
      method: "POST",
      body: JSON.stringify({ email: email.trim() }),
    }), []);

  const verifyCode = useCallback(async (email: string, code: string) => {
    const session = await fetchApi<any>("/api/auth/verify-otp", {
      method: "POST",
      headers: Platform.OS === "web" ? {} : { "X-Auth-Client": "native" },
      body: JSON.stringify({ email: email.trim(), otp_code: code }),
    });
    if (Platform.OS !== "web" && session.access_token) {
      await SecureStore.setItemAsync(TOKEN_KEY, session.access_token);
      setToken(session.access_token);
    }
    const nextUser = mapUser(session);
    setUser(nextUser);
    return nextUser;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api("/api/auth/sign-out", { method: "POST" });
    } finally {
      if (Platform.OS !== "web") await SecureStore.deleteItemAsync(TOKEN_KEY);
      setToken(null);
      setUser(null);
    }
  }, [api]);

  const value = useMemo(() => ({ user, isLoading, api, requestCode, verifyCode, signOut }), [
    user, isLoading, api, requestCode, verifyCode, signOut,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
