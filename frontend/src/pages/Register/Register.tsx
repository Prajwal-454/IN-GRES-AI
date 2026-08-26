import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, RefreshCw, Waves, XCircle } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { getApiError } from "@/services/api";
import { fetchCaptcha, type CaptchaChallenge } from "@/services/auth";

export default function Register() {
  const { register } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [captcha, setCaptcha] = useState<CaptchaChallenge | null>(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadCaptcha = useCallback(() => {
    setCaptchaAnswer("");
    fetchCaptcha()
      .then(setCaptcha)
      .catch(() => setCaptcha(null));
  }, []);

  useEffect(() => {
    loadCaptcha();
  }, [loadCaptcha]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError(t("Passwords do not match"));
      return;
    }
    if (password.length < 8) {
      setError(t("Password must be at least 8 characters"));
      return;
    }
    setSubmitting(true);
    try {
      await register(fullName, email, password, {
        captcha_id: captcha?.captcha_id ?? null,
        captcha_answer: captchaAnswer || null,
      });
      navigate("/assistant", { replace: true });
    } catch (err) {
      setError(getApiError(err));
      loadCaptcha(); // fresh challenge after every failed attempt
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-accent/50 to-background px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-6 flex items-center justify-center gap-2 text-xl font-semibold">
          <Waves className="h-7 w-7 text-primary" />
          IN-GRES AI
        </Link>
        <Card>
          <CardHeader className="text-center">
            <CardTitle>{t("Create your account")}</CardTitle>
            <CardDescription>{t("Start asking about groundwater resources")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fullName">{t("Full name")}</Label>
                <Input
                  id="fullName"
                  autoComplete="name"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">{t("Email")}</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{t("Password")}</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">{t("Confirm password")}</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                {confirmPassword.length > 0 &&
                  (password === confirmPassword ? (
                    <p className="flex items-center gap-1.5 rounded-md border border-green-500/40 bg-green-500/10 px-2.5 py-1.5 text-sm font-medium text-green-600 dark:text-green-400">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      {t("Passwords match")}
                    </p>
                  ) : (
                    <p className="flex items-center gap-1.5 text-sm text-destructive">
                      <XCircle className="h-4 w-4 shrink-0" />
                      {t("Passwords do not match")}
                    </p>
                  ))}
              </div>
              <div className="space-y-2">
                <Label htmlFor="captcha">{t("Security check")}</Label>
                <div className="flex items-center gap-2">
                  <div
                    className="shrink-0 overflow-hidden rounded-md border"
                    dangerouslySetInnerHTML={{ __html: captcha?.svg ?? "" }}
                    style={{ width: 140, height: 48 }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={loadCaptcha}
                    title={t("New question")}
                    className="h-9 w-9 shrink-0"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Input
                    id="captcha"
                    required
                    inputMode="numeric"
                    value={captchaAnswer}
                    onChange={(e) => setCaptchaAnswer(e.target.value)}
                    placeholder={t("Answer")}
                    className="flex-1"
                  />
                </div>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? t("Creating account…") : t("Create account")}
              </Button>
            </form>
            <p className="mt-4 text-center text-sm text-muted-foreground">
              {t("Already registered?")}{" "}
              <Link to="/login" className="font-medium text-primary hover:underline">
                {t("Sign in")}
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}