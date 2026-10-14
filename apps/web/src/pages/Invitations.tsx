import { useState, type FormEvent } from "react";
import { api, roles } from "../shared/api";
import { useQuery } from "@tanstack/react-query";

export function InvitationsPanel({ tenantId }: { tenantId: string }) {
  const [error, setError] = useState("");
  const [link, setLink] = useState("");
  const query = useQuery({
    queryKey: ["admin", tenantId],
    queryFn: () =>
      api<{ projects: { id: string; name: string }[] }>(
        `tenants/${tenantId}/admin`,
      ),
  });
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLink("");
    try {
      const data = Object.fromEntries(new FormData(e.currentTarget));
      const result = await api<{ token: string }>(
        `tenants/${tenantId}/invitations`,
        { method: "POST", body: JSON.stringify(data) },
      );
      setLink(window.location.origin + "/invite#" + result.token);
    } catch (x) {
      setError((x as Error).message);
    }
  };
  return (
    <section className="card">
      <h2>Kullanıcı davet et</h2>
      <p className="muted">
        Davet 3 gün geçerlidir ve tek kullanımlıktır. MFA doğrulamasından sonra
        bağlantıyı oluşturup davet ettiğiniz kişiyle güvenli kanaldan paylaşın.
      </p>
      <form onSubmit={submit}>
        <div className="form-two">
          <label>
            E-posta
            <input name="email" type="email" required />
          </label>
          <label>
            Proje
            <select name="projectId" required>
              {query.data?.projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Rol
          <select name="role">
            {Object.entries(roles).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <button className="button primary">Davet bağlantısı oluştur</button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {link && (
        <label>
          Tek sefer gösterilen davet bağlantısı
          <input readOnly value={link} onFocus={(e) => e.target.select()} />
        </label>
      )}
    </section>
  );
}
export function InvitationPage() {
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [token] = useState(() => window.location.hash.slice(1));
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = Object.fromEntries(new FormData(e.currentTarget));
      await api("invitations/accept", {
        method: "POST",
        body: JSON.stringify({ ...data, token }),
      });
      history.replaceState(null, "", "/invite");
      setSuccess(true);
    } catch (x) {
      setError((x as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="context-page">
      <section className="card">
        <span className="eyebrow">FATURAPORT DESTEK</span>
        <h1>Çalışma alanına katılın</h1>
        {success ? (
          <>
            <p>Davet kabul edildi. Hesabınızla giriş yapabilirsiniz.</p>
            <a className="button primary" href="/">
              Girişe dön
            </a>
          </>
        ) : (
          <>
            <p className="muted">
              Yeni hesap oluşturmak için bilgileri doldurun. Mevcut hesabınız
              varsa önce giriş yapın ve bu davet bağlantısını tekrar açın.
            </p>
            <form onSubmit={submit}>
              <label>
                Ad soyad
                <input name="name" autoComplete="name" />
              </label>
              <label>
                Kullanıcı adı
                <input name="username" autoComplete="username" />
              </label>
              <label>
                Parola
                <input
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={12}
                />
              </label>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <button className="button primary" disabled={busy || !token}>
                {busy ? "Kaydediliyor…" : "Daveti kabul et"}
              </button>
              <a className="button" href="/">
                Girişe dön
              </a>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
