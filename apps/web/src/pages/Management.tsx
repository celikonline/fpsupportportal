import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  Settings,
  Download,
  LockKeyhole,
  Users,
  Plus,
  CheckCircle2,
} from "lucide-react";
import { api, date, roles, type Project, type User } from "../shared/api";
import { PageHeading } from "./Tickets";
import { InvitationsPanel } from "./Invitations";

function Feedback({ error, success }: { error: string; success: string }) {
  return (
    <>
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      {success && (
        <p className="success-banner" role="status">
          {success}
        </p>
      )}
    </>
  );
}
export function SettingsPage({
  scope,
  project,
  session,
  accountOnly = false,
}: {
  scope: string;
  project: Project;
  session: { mfaEnabled: boolean };
  accountOnly?: boolean;
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [secret, setSecret] = useState("");
  const run = async (action: () => Promise<unknown>, message: string) => {
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const setup = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    await run(async () => {
      const result = await api<{ secret: string }>("auth/mfa/setup", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSecret(result.secret);
    }, "Anahtar oluşturuldu. Doğrulayıcı uygulamanıza ekleyin.");
  };
  const verify = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    await run(async () => {
      await api("auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSecret("");
      void client.invalidateQueries({ queryKey: ["session"] });
    }, "MFA doğrulandı. Hassas yönetim işlemleri için 10 dakikalık doğrulama açıldı.");
  };
  const settings = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    await run(async () => {
      await api(scope + "/settings", {
        method: "PATCH",
        body: JSON.stringify({
          ...data,
          firstResponseMinutes: Number(data.firstResponseMinutes),
          resolutionMinutes: Number(data.resolutionMinutes),
          businessStart: Number(data.businessStart),
          businessEnd: Number(data.businessEnd),
          holidays: String(data.holidays || "")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          categories: String(data.categories || "")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          archived: data.archived === "on",
        }),
      });
      void client.invalidateQueries({ queryKey: ["projects"] });
    }, "Proje ayarları kaydedildi. Mevcut taleplerin SLA politikası korunur.");
  };
  return (
    <>
      <PageHeading
        title="Ayarlar"
        subtitle="Hesabınızın güvenliğini ve projenizin çalışma biçimini yönetin."
      />
      <Feedback error={error} success={success} />
      <div className={accountOnly ? "account-security" : "management-grid"}>
        <section className="card">
          <h2 className="inline">
            <ShieldCheck size={22} />
            Hesap güvenliği
          </h2>
          <p className="muted">
            İki aşamalı doğrulama hassas yönetim işlemleri için gereklidir.
          </p>
          <span
            className={"status " + (session.mfaEnabled ? "resolved" : "new")}
          >
            {session.mfaEnabled ? "MFA etkin" : "MFA henüz kurulmadı"}
          </span>
          {!session.mfaEnabled && !secret && (
            <form onSubmit={setup}>
              <label>
                Mevcut parola
                <input
                  name="password"
                  type="password"
                  required
                  autoComplete="current-password"
                />
              </label>
              <button className="button primary">MFA kurulumunu başlat</button>
            </form>
          )}
          {secret && (
            <div className="mfa-secret">
              <p>
                Google Authenticator, Microsoft Authenticator veya uyumlu
                uygulamada manuel anahtar olarak ekleyin.
              </p>
              <code>{secret}</code>
              <small>Bu anahtarı güvenli saklayın ve paylaşmayın.</small>
            </div>
          )}
          {(secret || session.mfaEnabled) && (
            <form onSubmit={verify}>
              <label>
                Doğrulayıcı uygulama kodu
                <input
                  name="code"
                  inputMode="numeric"
                  required
                  maxLength={6}
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                />
              </label>
              <button className="button primary">
                {secret ? "MFA etkinleştir" : "Yönetim işlemleri için doğrula"}
              </button>
            </form>
          )}
          <div className="divider" />
          <h3>Parola değiştir</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const body = Object.fromEntries(new FormData(e.currentTarget));
              void run(async () => {
                await api("auth/password", {
                  method: "POST",
                  body: JSON.stringify(body),
                });
                window.location.assign("/");
              }, "Parola değiştirildi.");
            }}
          >
            <label>
              Mevcut parola
              <input
                type="password"
                name="currentPassword"
                required
                autoComplete="current-password"
              />
            </label>
            <label>
              Yeni parola
              <input
                type="password"
                name="newPassword"
                minLength={12}
                required
                autoComplete="new-password"
              />
            </label>
            <button className="button">Parolayı değiştir ve çıkış yap</button>
          </form>
        </section>
        {!accountOnly && (
          <section className="card">
            <h2 className="inline">
              <Settings size={22} />
              Proje ayarları
            </h2>
            <p className="muted">
              {project.name} · {roles[project.role]}
            </p>
            {project.role === "manager" ? (
              <form onSubmit={settings}>
                <label>
                  Proje adı
                  <input
                    name="name"
                    required
                    defaultValue={project.name}
                    maxLength={120}
                  />
                </label>
                <label>
                  Saat dilimi
                  <input
                    name="timezone"
                    defaultValue={project.timezone}
                    required
                  />
                </label>
                <label>
                  Tatil tarihleri
                  <input
                    name="holidays"
                    defaultValue={project.holidays?.join(", ")}
                    placeholder="2026-10-29, 2027-01-01"
                  />
                </label>
                <label>
                  Proje kategorileri
                  <input
                    name="categories"
                    defaultValue={project.categories?.join(", ")}
                    placeholder="Genel, Entegrasyon, Raporlama"
                  />
                </label>
                <div className="form-two">
                  <label>
                    İlk yanıt hedefi (dakika)
                    <input
                      type="number"
                      min={1}
                      max={525600}
                      name="firstResponseMinutes"
                      defaultValue={project.firstResponseMinutes}
                      required
                    />
                  </label>
                  <label>
                    Çözüm hedefi (dakika)
                    <input
                      type="number"
                      min={1}
                      max={525600}
                      name="resolutionMinutes"
                      defaultValue={project.resolutionMinutes}
                      required
                    />
                  </label>
                </div>
                <div className="form-two">
                  <label>
                    Mesai başlangıcı
                    <input
                      type="number"
                      min={0}
                      max={23}
                      name="businessStart"
                      defaultValue={project.businessStart}
                      required
                    />
                  </label>
                  <label>
                    Mesai bitişi
                    <input
                      type="number"
                      min={1}
                      max={24}
                      name="businessEnd"
                      defaultValue={project.businessEnd}
                      required
                    />
                  </label>
                </div>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="archived"
                    defaultChecked={project.archived}
                  />
                  Projeyi arşivle (salt okunur)
                </label>
                <button className="button primary">Ayarları kaydet</button>
              </form>
            ) : (
              <p>Proje ayarlarını yalnız proje yöneticisi değiştirebilir.</p>
            )}
          </section>
        )}
      </div>
    </>
  );
}
type PrivacyItem = {
  id: string;
  username: string;
  kind: string;
  status: string;
  note: string;
  createdAt: string;
};
export function PrivacyPage({
  tenantId,
  admin,
}: {
  tenantId: string;
  admin: boolean;
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const path = `tenants/${tenantId}/privacy`;
  const [reviewReason, setReviewReason] = useState("");
  const [verified, setVerified] = useState(false);
  const query = useQuery({
    queryKey: ["privacy", tenantId],
    queryFn: () => api<PrivacyItem[]>(path),
  });
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      form.reset();
      setSuccess("Başvurunuz kaydedildi.");
      setError("");
      void client.invalidateQueries({ queryKey: ["privacy", tenantId] });
    } catch (x) {
      setError((x as Error).message);
    }
  };
  const action = async (item: PrivacyItem, action: string) => {
    try {
      const result = await api(path + "/" + item.id, {
        method: "POST",
        body: JSON.stringify({
          action,
          reason: reviewReason,
          identityVerified: verified,
        }),
      });
      if (action === "export") {
        const url = URL.createObjectURL(
          new Blob([JSON.stringify(result, null, 2)], {
            type: "application/json",
          }),
        );
        const a = document.createElement("a");
        a.href = url;
        a.download = "kisisel-veri-basvurusu.json";
        a.click();
        URL.revokeObjectURL(url);
      }
      void client.invalidateQueries({ queryKey: ["privacy", tenantId] });
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const kinds: Record<string, string> = {
    access: "Verilerime erişim",
    erasure: "Silme talebi",
    correction: "Düzeltme talebi",
  };
  return (
    <>
      <PageHeading
        title="Gizlilik merkezi"
        subtitle="Kişisel verilerinize ilişkin başvurularınızı oluşturun ve takip edin."
      />
      <Feedback error={error || query.error?.message || ""} success={success} />
      <div className="management-grid">
        <section className="card">
          <h2>Yeni başvuru</h2>
          <p className="muted">
            Başvurunuz kuruluşunuzun yetkili sorumlusuna iletilir. Silme
            talepleri saklama yükümlülükleriyle birlikte değerlendirilir.
          </p>
          <form onSubmit={submit}>
            <label>
              Başvuru türü
              <select name="kind">
                {Object.entries(kinds).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Açıklama
              <textarea
                name="note"
                maxLength={500}
                rows={5}
                placeholder="Başvurunuzun kapsamını belirtin. Gereksiz kişisel veri paylaşmayın."
              />
            </label>
            <button className="button primary">Başvuru oluştur</button>
          </form>
        </section>
        <section className="card">
          <h2 className="inline">
            <ShieldCheck size={22} />
            Verileriniz nasıl korunur?
          </h2>
          <p>
            Talep ve eklerinize erişim, kuruluş ve proje üyeliğinizle
            sınırlandırılır.
          </p>
          <p>
            Destek ekibinin iç notları müşteri görünümünde yer almaz. Ekler
            güvenlik taramasından geçmeden açılmaz.
          </p>
          <p>
            Dosya ve kayıtlar kuruluşunuzun onayladığı saklama politikası
            kapsamında yönetilir. Gizlilik başvurularınız yetkili sorumlu
            tarafından değerlendirilir.
          </p>
          <small className="muted">
            Bu metin ürün açıklamasıdır. Kuruluşunuza ait hukuki aydınlatma
            metni ve veri işleme şartları pilot öncesinde ayrıca
            yayımlanmalıdır.
          </small>
        </section>
      </div>
      <section className="card">
        {admin && (
          <div className="review-controls">
            <label>
              İnceleme ve hukuki değerlendirme gerekçesi
              <input
                value={reviewReason}
                maxLength={500}
                onChange={(e) => setReviewReason(e.target.value)}
              />
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={verified}
                onChange={(e) => setVerified(e.target.checked)}
              />
              İlgili kişinin kimliği kurum prosedürüne göre doğrulandı
            </label>
            <p className="muted">
              İmha iki farklı yöneticinin onayını gerektirir. Hesap ayarlarında
              yakın tarihli MFA doğrulaması yapın.
            </p>
          </div>
        )}
        <h2>{admin ? "Kuruluş başvuruları" : "Başvurularım"}</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>BAŞVURU</th>
                <th>KULLANICI</th>
                <th>DURUM</th>
                <th>TARİH</th>
                <th>İŞLEM</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((x) => (
                <tr key={x.id}>
                  <td>
                    {kinds[x.kind]}
                    <small className="muted block">{x.note}</small>
                  </td>
                  <td>{x.username}</td>
                  <td>{x.status}</td>
                  <td>{date(x.createdAt)}</td>
                  <td>
                    {admin && (
                      <div className="inline">
                        <button
                          className="button small"
                          onClick={() => void action(x, "review")}
                        >
                          İncele
                        </button>
                        {x.kind === "access" && (
                          <button
                            className="button small"
                            onClick={() => void action(x, "export")}
                          >
                            <Download size={14} />
                            Dışa aktar
                          </button>
                        )}
                        <button
                          className="button small"
                          onClick={() => void action(x, "reject")}
                        >
                          Reddet
                        </button>
                        {x.kind === "erasure" && (
                          <button
                            className="button small"
                            onClick={() =>
                              void action(
                                x,
                                x.status === "approved"
                                  ? "execute_erasure"
                                  : "approve_erasure",
                              )
                            }
                          >
                            {x.status === "approved"
                              ? "İkinci onay ve imha"
                              : "İmhayı onayla"}
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!query.data?.length && (
          <p className="empty-state">Henüz başvuru yok.</p>
        )}
      </section>
    </>
  );
}
export function AuditPage({ tenantId }: { tenantId: string }) {
  const query = useQuery({
    queryKey: ["audit", tenantId],
    queryFn: () =>
      api<
        {
          id: string;
          action: string;
          actorId: string;
          targetId: string;
          result: string;
          createdAt: string;
        }[]
      >(`tenants/${tenantId}/audit-events`),
  });
  return (
    <>
      <PageHeading
        title="Denetim kayıtları"
        subtitle="Erişim, yönetim ve veri işlemlerini izlenebilir kayıtlarla takip edin."
      />
      <section className="card">
        {query.error && (
          <p className="error" role="alert">
            {query.error.message}
          </p>
        )}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>İŞLEM</th>
                <th>AKTÖR</th>
                <th>HEDEF</th>
                <th>SONUÇ</th>
                <th>TARİH</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((a) => (
                <tr key={a.id}>
                  <td>{a.action}</td>
                  <td>{a.actorId}</td>
                  <td>
                    <code>{a.targetId.slice(0, 12)}</code>
                  </td>
                  <td>{a.result}</td>
                  <td>{date(a.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          Son 100 olay · İçerik ve dosya gövdeleri denetim kayıtlarında
          tutulmaz.
        </p>
      </section>
    </>
  );
}
type AdminData = {
  members: (User & { role: string; active: boolean })[];
  projects: { id: string; name: string; code: string }[];
  retentionDays: number;
  retentionApproved: boolean;
};
function TenantAdminCore({ tenantId }: { tenantId: string }) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const path = `tenants/${tenantId}/admin`;
  const query = useQuery({
    queryKey: ["admin", tenantId],
    queryFn: () => api<AdminData>(path),
  });
  const send = async (body: unknown, method = "POST", endpoint = path) => {
    try {
      await api(endpoint, { method, body: JSON.stringify(body) });
      setError("");
      setSuccess("İşlem kaydedildi.");
      void client.invalidateQueries({ queryKey: ["admin", tenantId] });
      void client.invalidateQueries({ queryKey: ["projects", tenantId] });
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <PageHeading
        title="Kuruluş yönetimi"
        subtitle="Proje erişimlerini ve veri saklama politikasını yönetin."
      />
      <Feedback error={error || query.error?.message || ""} success={success} />
      <div className="management-grid">
        <section className="card">
          <h2 className="inline">
            <Users size={22} />
            Proje rolü ata
          </h2>
          <p className="muted">
            Önce hesap ayarlarında MFA doğrulaması yapın. Tenant yöneticiliği
            tek başına proje içeriğini görme hakkı vermez.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(Object.fromEntries(new FormData(e.currentTarget)));
            }}
          >
            <label>
              Kullanıcı
              <select name="username">
                {query.data?.members
                  .filter((m) => m.active)
                  .map((m) => (
                    <option key={m.id} value={m.username}>
                      {m.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Proje
              <select name="projectId">
                {query.data?.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
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
            <button className="button primary">Rolü ata</button>
          </form>
        </section>
        <section className="card">
          <h2>Yeni proje</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(
                Object.fromEntries(new FormData(e.currentTarget)),
                "POST",
                `tenants/${tenantId}/projects`,
              );
            }}
          >
            <label>
              Proje adı
              <input name="name" required maxLength={120} />
            </label>
            <label>
              Proje kodu
              <input
                name="code"
                required
                maxLength={16}
                pattern="[a-z0-9-]+"
                placeholder="ornek-proje"
              />
            </label>
            <button className="button">
              <Plus size={16} />
              Proje oluştur
            </button>
          </form>
          <div className="divider" />
          <h3>Saklama politikası</h3>
          <p className="muted">
            Süre hukuki gerekçeyle belirlenmelidir. Kaydetmek kurum
            politikasının onaylandığını kaydeder; tek başına otomatik imha
            başlatmaz.
          </p>
          <form
            key={query.data?.retentionDays}
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void send(
                { retentionDays: Number(data.get("retentionDays")) },
                "PATCH",
              );
            }}
          >
            <label>
              Saklama süresi (gün)
              <input
                type="number"
                name="retentionDays"
                min={1}
                max={3650}
                defaultValue={query.data?.retentionDays || 365}
                required
              />
            </label>
            <button className="button">Politikayı onayla ve kaydet</button>
          </form>
        </section>
      </div>
      <section className="card">
        <h2>Kuruluş üyeleri</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>KULLANICI</th>
                <th>TENANT ROLÜ</th>
                <th>DURUM</th>
                <th>İŞLEM</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.members.map((m) => (
                <tr key={m.id}>
                  <td>
                    {m.name}
                    <small className="muted block">{m.username}</small>
                  </td>
                  <td>{m.role}</td>
                  <td>{m.active ? "Aktif" : "İptal"}</td>
                  <td>
                    {m.active && (
                      <button
                        className="button small"
                        onClick={() =>
                          void send({ action: "revoke", username: m.username })
                        }
                      >
                        Üyeliği iptal et
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

export function TenantAdminPage({ tenantId }: { tenantId: string }) {
  return (
    <>
      <TenantAdminCore tenantId={tenantId} />
      <InvitationsPanel tenantId={tenantId} />
    </>
  );
}
