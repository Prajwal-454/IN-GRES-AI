import { api } from "./api";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  language_pref: string;
  is_active: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  captcha_id?: string | null;
  captcha_answer?: string | null;
}

export interface CaptchaChallenge {
  captcha_id: string;
  svg: string;
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/login", payload);
  return data;
}

export async function fetchCaptcha(): Promise<CaptchaChallenge> {
  const { data } = await api.get<CaptchaChallenge>("/auth/captcha");
  return data;
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/register", payload);
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

export async function refresh(refreshToken: string): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}