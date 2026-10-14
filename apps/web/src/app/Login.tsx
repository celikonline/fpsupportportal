import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LifeBuoy,
  LockKeyhole,
  MessagesSquare,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import "@fontsource-variable/onest";
import "@fontsource-variable/bricolage-grotesque";
import { api, setCsrf } from "../shared/api";
import "./Login.css";

function LoginBrand({ onDark = false }: { onDark?: boolean }) {
  return (
    <div className="support-login-brand">
      <svg
        width="40"
        height="40"
        viewBox="0 0 40 40"
        fill="none"
        aria-hidden="true"
      >
        <rect
          x="12"
          y="4"
          width="24"
          height="24"
          rx="6"
          fill={onDark ? "white" : "#280087"}
        />
        <rect x="4" y="12" width="24" height="24" rx="6" fill="#008cf0" />
        <path
          d="M12.5 27.5L21 19M21 19H14.5M21 19V25.5"
          stroke="white"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div>
        <strong>FaturaPort Destek</strong>
        <span>FaturaPort ekosisteminin bir parçası</span>
      </div>
    </div>
  );
}

export function Login({ onLogin }: { onLogin: () => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("fp-theme");
    return saved
      ? saved === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("fp-theme", dark ? "dark" : "light");
  }, [dark]);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      const result = await api<{ csrfToken: string }>("auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(data)),
      });
      setCsrf(result.csrfToken);
      onLogin();
    } catch (x) {
      setError((x as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="support-login" data-theme={dark ? "dark" : "light"}>
      <button
        className="support-login-theme"
        type="button"
        onClick={() => setDark(!dark)}
        aria-label={dark ? "Açık temaya geç" : "Koyu temaya geç"}
        title={dark ? "Açık temaya geç" : "Koyu temaya geç"}
      >
        {dark ? <Moon size={17} /> : <Sun size={17} />}
      </button>

      <aside
        className="support-login-story"
        aria-label="FaturaPort Destek hakkında"
      >
        <div
          className="support-login-shape support-login-shape-back"
          aria-hidden="true"
        />
        <div
          className="support-login-shape support-login-shape-front"
          aria-hidden="true"
        />
        <LoginBrand onDark />
        <div className="support-login-story-content">
          <span className="support-login-eyebrow">
            <span />
            Her adımda yanınızdayız
          </span>
          <h1>
            Birlikte, daha hızlı
            <br />
            çözüme ulaşın.
          </h1>
          <p>
            Taleplerinizi tek yerden yönetin, ekibinizle iletişimde kalın. Her
            adımda açık iletişim, her talepte doğru çözüm.
          </p>
          <div className="support-login-features">
            <div>
              <span className="support-login-feature-icon">
                <LifeBuoy size={20} />
              </span>
              <span>Tüm destek talepleriniz tek yerde</span>
            </div>
            <div>
              <span className="support-login-feature-icon orange">
                <MessagesSquare size={20} />
              </span>
              <span>Ekibinizle kesintisiz iletişim</span>
            </div>
            <div>
              <span className="support-login-feature-icon teal">
                <ShieldCheck size={20} />
              </span>
              <span>Güvenli ve size özel çalışma alanı</span>
            </div>
          </div>
        </div>
        <small>
          © {new Date().getFullYear()} FaturaPort. Tüm hakları saklıdır.
        </small>
      </aside>

      <main className="support-login-form-panel">
        <form
          className="support-login-form"
          onSubmit={submit}
          aria-label="Destek portalına giriş"
          aria-busy={busy}
        >
          <div className="support-login-mobile-brand">
            <LoginBrand />
          </div>
          <div className="support-login-accent" aria-hidden="true" />
          <h2>Tekrar hoş geldiniz</h2>
          <p className="support-login-subtitle">
            Destek portalına devam etmek için giriş yapın.
          </p>
          {error && (
            <p className="support-login-error" role="alert">
              {error}
            </p>
          )}
          <div className="support-login-fields">
            <label className="support-login-field" htmlFor="login-username">
              Kullanıcı adı
              <input
                id="login-username"
                name="username"
                required
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="Kullanıcı adınız"
                disabled={busy}
              />
            </label>
            <div className="support-login-field">
              <label htmlFor="login-password">Parola</label>
              <div className="support-login-password">
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  placeholder="Parolanız"
                  disabled={busy}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={
                    showPassword ? "Parolayı gizle" : "Parolayı göster"
                  }
                  aria-pressed={showPassword}
                  disabled={busy}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>
            <label className="support-login-field" htmlFor="login-code">
              <span>
                Doğrulama kodu <small>MFA etkinse</small>
              </span>
              <input
                id="login-code"
                name="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="6 haneli kod"
                disabled={busy}
              />
            </label>
          </div>
          <button
            className="support-login-submit"
            type="submit"
            disabled={busy}
          >
            {busy ? "Giriş yapılıyor…" : "Giriş yap"}
            <ArrowRight size={18} aria-hidden="true" />
          </button>
          <p className="support-login-contact">
            Hesabınız için şirket yöneticinizle iletişime geçin.
          </p>
          <p className="support-login-security">
            <LockKeyhole size={14} aria-hidden="true" />
            İki aşamalı doğrulama ile güvenli erişim
          </p>
        </form>
      </main>
    </div>
  );
}
