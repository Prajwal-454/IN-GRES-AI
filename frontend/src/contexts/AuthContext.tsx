import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { fetchMe, login as loginApi, refresh, register as registerApi, type User } from "@/services/auth";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    fullName: string,
    email: string,
    password: string,
    captcha?: { captcha_id: string | null; captcha_answer: string | null }
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function persistTokens(data: { access_token: string; refresh_token: string }) {
  localStorage.setItem("ingres_access_token", data.access_token);
  localStorage.setItem("ingres_refresh_token", data.refresh_token);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("ingres_access_token");
    const refreshToken = localStorage.getItem("ingres_refresh_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => {
        if (refreshToken) {
          refresh(refreshToken)
            .then((data) => {
              persistTokens(data);
              setUser(data.user);
            })
            .catch(() => {
              localStorage.removeItem("ingres_access_token");
              localStorage.removeItem("ingres_refresh_token");
            });
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await loginApi({ email, password });
    persistTokens(data);
    setUser(data.user);
  }, []);

  const register = useCallback(
    async (
      fullName: string,
      email: string,
      password: string,
      captcha?: { captcha_id: string | null; captcha_answer: string | null }
    ) => {
      const data = await registerApi({
        full_name: fullName,
        email,
        password,
        captcha_id: captcha?.captcha_id ?? null,
        captcha_answer: captcha?.captcha_answer ?? null,
      });
      persistTokens(data);
      setUser(data.user);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem("ingres_access_token");
    localStorage.removeItem("ingres_refresh_token");
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: user !== null, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}