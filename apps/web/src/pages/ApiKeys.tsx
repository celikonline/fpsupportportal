import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { Check, Copy, KeyRound, LockKeyhole, Plus, Trash2 } from "lucide-react";
import { api, date } from "../shared/api";
import { PageHeading } from "./Tickets";

type KeyItem = {
  id: string;
  name: string;
  prefix: string;
  mode: "read" | "read_write" | "customer_bridge";
  createdAt: string;
  expiresAt: string;
  lastUsedAt: string | null;
  revokedAt: string | null;
};
type CreatedKey = KeyItem & { key: string };

export function ApiKeysPage({
  scope,
  base,
  projectName,
  canWrite,
  mfaEnabled,
  canBridge = false,
}: {
  scope: string;
  base: string;
  projectName: string;
  canWrite: boolean;
  mfaEnabled: boolean;
  canBridge?: boolean;
}) {
  const client = useQueryClient();
  const path = scope + "/api-keys";
  const query = useQuery({
    queryKey: ["api-keys", scope],
    queryFn: ({ signal }) =>
      api<{ items: KeyItem[]; activeCount: number }>(path, { signal }),
  });
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [revokeId, setRevokeId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const items = query.data?.items || [];
  const activeCount = query.data?.activeCount ?? 0;

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await api<CreatedKey>(path, {
        method: "POST",
        body: JSON.stringify({
          name: values.name,
          mode: values.mode,
          expiresInDays: Number(values.expiresInDays),
        }),
      });
      setCreated(result);
      setCopied(false);
      setShowForm(false);
      form.reset();
      void client.invalidateQueries({ queryKey: ["api-keys", scope] });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    if (!revokeId) return;
    setBusy(true);
    setError("");
    try {
      await api(path + "/" + revokeId, { method: "DELETE" });
      setRevokeId(null);
      setSuccess("Anahtar iptal edildi. Yeni isteklerde kullanılamaz.");
      void client.invalidateQueries({ queryKey: ["api-keys", scope] });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.key);
      setCopied(true);
      setError("");
    } catch {
      setError(
        "Kopyalama yapılamadı. Anahtarı aşağıdaki alandan elle kopyalayın.",
      );
    }
  };

  return (
    <>
      <PageHeading
        title="API anahtarları"
        subtitle={`${projectName} için kişisel entegrasyon anahtarlarınızı yönetin.`}
        action={
          <button
            className="button primary"
            onClick={() => {
              setError("");
              setShowForm(true);
            }}
            disabled={
              !mfaEnabled ||
              query.isPending ||
              query.isError ||
              activeCount >= 10
            }
          >
            <Plus size={16} /> Yeni gizli anahtar
          </button>
        }
      />
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
      {!mfaEnabled && (
        <div className="warning-banner">
          Anahtar oluşturmak için önce{" "}
          <Link to={base + "/settings"}>Ayarlar</Link> bölümünde MFA kurun.
          Etkin MFA için işlem öncesinde güncel kodla doğrulama gerekir.
        </div>
      )}
      <div className="api-key-summary">
        <div className="card api-key-info">
          <span className="api-key-icon">
            <KeyRound size={25} />
          </span>
          <div>
            <strong>Proje kapsamlı erişim</strong>
            <p>
              Her anahtar yalnız bu projede ve hesabınızın güncel yetkileriyle
              çalışır. Üyelik kaldırıldığında erişim hemen kesilir.
            </p>
          </div>
        </div>
        <div className="card api-key-count">
          <strong>
            {activeCount}
            <small> / 10</small>
          </strong>
          <span>Etkin anahtar</span>
        </div>
      </div>

      {showForm && (
        <section className="card api-key-form" aria-labelledby="new-key-title">
          <div className="api-key-section-head">
            <div>
              <h2 id="new-key-title">Yeni gizli anahtar oluştur</h2>
              <p className="muted">
                Anahtarı tanınabilir bir adla kaydedin ve kullanım yetkisini
                seçin.
              </p>
            </div>
            <button
              className="button ghost"
              onClick={() => setShowForm(false)}
              disabled={busy}
            >
              Vazgeç
            </button>
          </div>
          <form onSubmit={create}>
            <label>
              Ad
              <input
                name="name"
                maxLength={80}
                placeholder="Örn. ERP entegrasyonu"
                required
                autoFocus
              />
            </label>
            <div className="form-two">
              <label>
                İzin
                <select name="mode" defaultValue="read">
                  <option value="read">Salt okunur</option>
                  {canWrite && (
                    <option value="read_write">Okuma ve yazma</option>
                  )}
                  {canBridge && canWrite && <option value="customer_bridge">Ürün müşteri destek köprüsü</option>}
                </select>
              </label>
              <label>
                Son kullanma
                <select name="expiresInDays" defaultValue="90">
                  <option value="30">30 gün</option>
                  <option value="90">90 gün</option>
                  <option value="180">180 gün</option>
                  <option value="365">365 gün</option>
                </select>
              </label>
            </div>
            <p className="api-key-hint">
              <LockKeyhole size={15} /> Oluşturma ve iptal işlemlerinde son 10
              dakika içinde MFA doğrulaması gerekir.
            </p>
            <button className="button primary" disabled={busy}>
              {busy ? "Oluşturuluyor…" : "Anahtarı oluştur"}
            </button>
          </form>
        </section>
      )}

      <section className="card api-key-list">
        <div className="api-key-section-head">
          <div>
            <h2>Anahtarlarım</h2>
            <p className="muted">Gizli değerler listede tekrar gösterilmez.</p>
          </div>
        </div>
        {query.isPending && <p className="muted">Anahtarlar yükleniyor…</p>}
        {query.isError && (
          <p className="error" role="alert">
            Anahtarlar yüklenemedi.{" "}
            <button
              className="button small"
              onClick={() => void query.refetch()}
            >
              Tekrar dene
            </button>
          </p>
        )}
        {query.isSuccess && !items.length && (
          <div className="api-key-empty">
            <KeyRound size={28} />
            <strong>Henüz API anahtarınız yok</strong>
            <p>
              İlk anahtarınızı oluşturup bu projenin API'sini entegrasyonunuzdan
              kullanabilirsiniz.
            </p>
          </div>
        )}
        {!!items.length && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>AD</th>
                  <th>ANAHTAR ÖNEKİ</th>
                  <th>İZİN</th>
                  <th>OLUŞTURULDU</th>
                  <th>SON KULLANIM</th>
                  <th>SON TARİH</th>
                  <th>DURUM</th>
                  <th>İŞLEM</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const expired =
                    new Date(item.expiresAt).getTime() <= Date.now();
                  return (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.name}</strong>
                      </td>
                      <td>
                        <code>{item.prefix}…</code>
                      </td>
                      <td>
                        {item.mode === "read" ? "Salt okunur" : item.mode === "customer_bridge" ? "Ürün müşteri köprüsü" : "Okuma / yazma"}
                      </td>
                      <td>{date(item.createdAt)}</td>
                      <td>
                        {item.lastUsedAt
                          ? date(item.lastUsedAt)
                          : "Henüz kullanılmadı"}
                      </td>
                      <td>{date(item.expiresAt)}</td>
                      <td>
                        <span
                          className={
                            "status " +
                            (item.revokedAt || expired ? "new" : "resolved")
                          }
                        >
                          {item.revokedAt
                            ? "İptal"
                            : expired
                              ? "Süresi doldu"
                              : "Etkin"}
                        </span>
                      </td>
                      <td>
                        {!item.revokedAt && (
                          <button
                            className="button small"
                            onClick={() => setRevokeId(item.id)}
                            aria-label={item.name + " anahtarını iptal et"}
                          >
                            <Trash2 size={14} /> İptal et
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card api-key-example">
        <h2>API'de kullanma</h2>
        <p className="muted">
          Anahtarı yalnız güvenilir sunucu ortamında saklayın. İsteklere Bearer
          başlığı olarak ekleyin; yazma işlemlerinde ayrıca Idempotency-Key
          kullanın.
        </p>
        <code>Authorization: Bearer fpsk_…</code>
        <small>Proje kapsamı: /api/v1/{scope}/tickets</small>
      </section>

      {created && (
        <div className="api-key-overlay">
          <div
            className="card api-key-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="key-created-title"
          >
            <span className="api-key-icon">
              <KeyRound size={24} />
            </span>
            <h2 id="key-created-title">Gizli anahtar oluşturuldu</h2>
            <p>
              Bu anahtar yalnız şimdi gösterilir. Güvenli bir yere kopyalayın;
              ekranı kapattıktan sonra yeniden görüntülenemez.
            </p>
            <label>
              Yeni API anahtarı
              <input
                readOnly
                value={created.key}
                onFocus={(e) => e.currentTarget.select()}
                aria-label="Yeni API anahtarı"
              />
            </label>
            <div className="api-key-dialog-actions">
              <button
                className="button primary"
                onClick={() => void copy()}
                autoFocus
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "Kopyalandı" : "Kopyala"}
              </button>
              <button
                className="button"
                onClick={() => {
                  setCreated(null);
                  setCopied(false);
                }}
              >
                Tamam
              </button>
            </div>
          </div>
        </div>
      )}

      {revokeId && (
        <div className="api-key-overlay">
          <div
            className="card api-key-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="key-revoke-title"
          >
            <h2 id="key-revoke-title">Anahtarı iptal et</h2>
            <p>
              Bu anahtarı kullanan entegrasyon yeni istekte erişimini kaybeder.
              İşlem geri alınamaz.
            </p>
            <div className="api-key-dialog-actions">
              <button
                className="button"
                onClick={() => setRevokeId(null)}
                disabled={busy}
              >
                Vazgeç
              </button>
              <button
                className="button primary"
                onClick={() => void revoke()}
                disabled={busy}
              >
                {busy ? "İptal ediliyor…" : "Anahtarı iptal et"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
