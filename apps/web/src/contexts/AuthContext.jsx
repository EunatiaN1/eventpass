import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const AuthContext = createContext(null);

async function authRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error("Network error. Check your connection and try again.");
  }

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (response.status === 422) throw new Error("Enter a valid email address and 6-digit code.");
    if (response.status === 410) throw new Error("Code expired. Request a new one.");
    if (response.status === 429) {
      throw new Error(data?.detail || "Too many attempts. Wait a moment and try again.");
    }
    if (response.status === 401) {
      throw new Error(data?.detail || "Invalid code. Check the 6 digits and try again.");
    }
    if (response.status === 503) {
      throw new Error(data?.detail || "Email delivery is unavailable. Try again shortly.");
    }
    throw new Error(data?.detail || "We couldn't complete that request. Please try again.");
  }
  return data;
}

function toAuthUser(data) {
  return {
    id: data.user_id || data.id,
    email: data.email || null,
    wallet: data.wallet,
    role: data.role || "buyer",
    label: data.email || data.wallet,
    isAuthenticated: true,
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const data = await authRequest("/api/auth/me");
      setUser(toAuthUser(data));
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const requestCode = useCallback(async (email) => {
    return authRequest("/api/auth/otp", {
      method: "POST",
      body: JSON.stringify({ email: email.trim() }),
    });
  }, []);

  const verifyCode = useCallback(async (email, otpCode) => {
    const data = await authRequest("/api/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email: email.trim(), otp_code: otpCode }),
    });
    // The JWT is held in an HttpOnly cookie. Keep only the user's public profile in React state.
    const nextUser = toAuthUser(data);
    setUser(nextUser);
    return nextUser;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authRequest("/api/auth/sign-out", { method: "POST" });
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      auth: user || { isAuthenticated: false, id: null, email: null, wallet: null, role: null, label: null },
      isLoading,
      requestCode,
      verifyCode,
      signOut,
    }),
    [user, isLoading, requestCode, verifyCode, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
