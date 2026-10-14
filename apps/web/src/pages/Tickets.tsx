import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  ArrowUpRight,
  Clock3,
  Ticket as TicketIcon,
  CheckCircle2,
  MessageSquare,
  ArrowLeft,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  UserRound,
  Paperclip,
  Activity,
  LockKeyhole,
} from "lucide-react";
import {
  api,
  command,
  date,
  statuses,
  priorities,
  type Ticket,
  type TicketPage,
  type User,
} from "../shared/api";
import {
  AttachmentComposer,
  AttachmentList,
  clipboardImages,
} from "../features/Attachments";

export function PageHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}
function Status({ value }: { value: string }) {
  return (
    <span className={"status " + value}>
      <i />
      {statuses[value] || value}
    </span>
  );
}
export function TicketList({
  scope,
  base,
  dashboard = false,
  staff,
  write,
}: {
  scope: string;
  base: string;
  dashboard?: boolean;
  staff: boolean;
  write: boolean;
}) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [page, setPage] = useState(1);
  const [mine, setMine] = useState(false);
  const list = useQuery({
    queryKey: ["tickets", scope, q, status, priority, page, mine],
    queryFn: ({ signal }) =>
      api<TicketPage>(
        scope +
          "/tickets?" +
          new URLSearchParams({
            q,
            status,
            priority,
            page: String(page),
            mine: mine ? "1" : "0",
          }),
        { signal },
      ),
  });
  const stats = list.data?.stats;
  const tickets = list.data?.results || [];
  return (
    <>
      <PageHeading
        title={dashboard ? "Genel bakış" : "Destek talepleri"}
        subtitle={
          dashboard
            ? "Talepleriniz, gelişmeler ve ekibinizin gündemi bir arada."
            : "İhtiyacınız olan desteği bulun, ilerlemeyi takip edin."
        }
        action={
          write && (
            <Link className="button primary" to={base + "/new"}>
              <Plus size={18} />
              Yeni talep oluştur
            </Link>
          )
        }
      />
      {dashboard && (
        <div className="hero">
          <div>
            <span className="eyebrow">İYİ İŞLER, GÜÇLÜ DESTEK</span>
            <h2>
              İşinize odaklanın.
              <br />
              Çözüm için buradayız.
            </h2>
            <p>
              Bir sorunuz veya geliştirme fikriniz mi var?
              <br />
              Talebinizi paylaşın, birlikte ilerleyelim.
            </p>
            {write && (
              <Link className="hero-link" to={base + "/new"}>
                Yeni bir talep başlat <ArrowUpRight size={17} />
              </Link>
            )}
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="art-ticket">
              <span />
              <span />
              <span />
              <i>
                <CheckCircle2 size={24} />
              </i>
            </div>
            <div className="art-bubble">
              <MessageSquare size={27} />
            </div>
            <div className="art-check">
              <ShieldCheck size={30} />
            </div>
          </div>
        </div>
      )}
      <div className="kpi-row">
        <div className="kpi">
          <span className="kpi-icon lavender">
            <TicketIcon size={24} />
          </span>
          <div>
            <p>Açık talepler</p>
            <strong>{stats?.open ?? "—"}</strong>
            <small>Çözüm süreci devam eden</small>
          </div>
        </div>
        <div className="kpi">
          <span className="kpi-icon amber">
            <Clock3 size={24} />
          </span>
          <div>
            <p>Yanıt bekleyen</p>
            <strong>{stats?.waiting ?? "—"}</strong>
            <small>Talep sahibinin yanıtı bekleniyor</small>
          </div>
        </div>
        <div className="kpi">
          <span className="kpi-icon aqua">
            <CheckCircle2 size={24} />
          </span>
          <div>
            <p>Çözülen talepler</p>
            <strong>{stats?.resolved ?? "—"}</strong>
            <small>Tamamlanan destek süreci</small>
          </div>
        </div>
      </div>
      <section className="card ticket-list">
        <div className="section-heading">
          <div>
            <h2>{dashboard ? "Son talepler" : "Tüm talepler"}</h2>
            <p className="muted">
              {list.data?.total ?? 0} talep · mevcut filtreleriniz ve
              yetkileriniz kapsamında
            </p>
          </div>
          <span className="subtle-icon">
            <SlidersHorizontal size={20} />
          </span>
        </div>
        <div className="list-toolbar">
          <div className="tabs">
            <button
              className={!mine ? "active" : ""}
              onClick={() => {
                setMine(false);
                setPage(1);
              }}
            >
              Tüm talepler
            </button>
            {staff && (
              <button
                className={mine ? "active" : ""}
                onClick={() => {
                  setMine(true);
                  setPage(1);
                }}
              >
                Bana atanan
              </button>
            )}
          </div>
          <div className="filters">
            <label className="search-input">
              <Search size={17} />
              <input
                aria-label="Talep ara"
                placeholder="Taleplerde ara…"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <select
              aria-label="Durum filtresi"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Tüm durumlar</option>
              {Object.entries(statuses).map(([key, value]) => (
                <option key={key} value={key}>
                  {value}
                </option>
              ))}
            </select>
            <select
              aria-label="Öncelik filtresi"
              value={priority}
              onChange={(e) => {
                setPriority(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Tüm öncelikler</option>
              {Object.entries(priorities).map(([key, value]) => (
                <option key={key} value={key}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </div>
        {list.isError ? (
          <div className="empty-state error" role="alert">
            {list.error.message}
            <button className="button" onClick={() => void list.refetch()}>
              Tekrar dene
            </button>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>TALEP</th>
                  <th>DURUM</th>
                  <th>ÖNCELİK</th>
                  <th>ATANAN</th>
                  <th>SON GÜNCELLEME</th>
                  <th>
                    <span className="sr-only">Aç</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td>
                      <Link
                        className="ticket-title"
                        to={base + "/tickets/" + ticket.id}
                      >
                        <small>
                          {ticket.number} <span>· {ticket.category}</span>
                        </small>
                        <strong>{ticket.title}</strong>
                      </Link>
                    </td>
                    <td>
                      <Status value={ticket.status} />
                    </td>
                    <td>
                      <span className={"priority " + ticket.priority}>
                        <i />
                        {priorities[ticket.priority]}
                      </span>
                    </td>
                    <td>
                      {ticket.assignee ? (
                        <div className="table-user">
                          <span>
                            {ticket.assignee.name
                              .split(" ")
                              .map((x) => x[0])
                              .join("")}
                          </span>
                          {ticket.assignee.name}
                        </div>
                      ) : (
                        <span className="muted">Atanmadı</span>
                      )}
                    </td>
                    <td className="muted">
                      {date(ticket.updatedAt)}
                      {ticket.slaRisk && (
                        <small className="sla-alert">SLA hedefi aşıldı</small>
                      )}
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        aria-label={ticket.number + " talebini aç"}
                        to={base + "/tickets/" + ticket.id}
                      >
                        <ArrowUpRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {list.isPending && (
              <div className="empty-state">Talepler yükleniyor…</div>
            )}
            {!list.isPending && !tickets.length && (
              <div className="empty-state">
                <TicketIcon size={32} />
                <strong>Henüz bir talep yok</strong>
                <p>
                  Yeni bir talep oluşturabilir veya filtrelerinizi
                  değiştirebilirsiniz.
                </p>
              </div>
            )}
          </div>
        )}
        <div className="table-footer">
          <span>
            {list.data?.total ?? 0} kayıt · Sayfa {page}
          </span>
          <div>
            <button
              className="icon-button"
              disabled={page === 1}
              aria-label="Önceki sayfa"
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={17} />
            </button>
            <button className="page-number">{page}</button>
            <button
              className="icon-button"
              disabled={page * 20 >= (list.data?.total ?? 0)}
              aria-label="Sonraki sayfa"
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={17} />
            </button>
          </div>
        </div>
      </section>
      {dashboard && (
        <div className="bottom-grid">
          <section className="card info-card">
            <span className="kpi-icon lavender">
              <Paperclip size={23} />
            </span>
            <div>
              <h3>Görsel paylaşın, daha hızlı anlaşalım.</h3>
              <p>
                Ekran görüntünüzü doğrudan yanıt alanına yapıştırın. Dosyalar
                erişime açılmadan önce güvenlik taramasından geçer.
              </p>
            </div>
          </section>
          <section className="card info-card">
            <span className="kpi-icon aqua">
              <LockKeyhole size={23} />
            </span>
            <div>
              <h3>Her proje, kendi çalışma alanı.</h3>
              <p>
                Talepleriniz ve ekleriniz yalnız yetkili kullanıcılarla
                paylaşılır. Gizlilik merkezinden başvurularınızı takip
                edebilirsiniz.
              </p>
              <Link to={base + "/privacy"}>
                Gizlilik merkezini aç <ArrowUpRight size={14} />
              </Link>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
export function NewTicket({
  scope,
  base,
  write,
}: {
  scope: string;
  base: string;
  write: boolean;
}) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const projectInfo = useQuery({
    queryKey: ["project-settings", scope],
    queryFn: () => api<{ categories: string[] }>(scope + "/settings"),
  });
  const [fileBusy, setFileBusy] = useState(false);
  const [paste, setPaste] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!write || fileBusy) return;
    const body = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      const ticket = await command<Ticket>(
        scope + "/tickets",
        {
          ...body,
          tags: String(body.tags || "")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          draftId: draft || undefined,
        },
        key,
      );
      void client.invalidateQueries({ queryKey: ["tickets"] });
      navigate(base + "/tickets/" + ticket.id);
    } catch (x) {
      setError((x as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (!write)
    return (
      <div className="card">
        <h1>Bu projede talep oluşturma yetkiniz yok.</h1>
      </div>
    );
  return (
    <>
      <Link className="back-link" to={base + "/tickets"}>
        <ArrowLeft size={16} />
        Taleplere dön
      </Link>
      <PageHeading
        title="Yeni destek talebi"
        subtitle="İhtiyacınızı paylaşın. Doğru ekibe birlikte ulaştıralım."
      />
      <div className="form-layout">
        <form className="card ticket-form" onSubmit={submit}>
          <div className="section-heading">
            <h2>Talep bilgileri</h2>
            <span className="pill">Yeni talep</span>
          </div>
          <label>
            Başlık <span className="required">*</span>
            <input
              name="title"
              required
              maxLength={200}
              placeholder="Sorununuzu kısaca özetleyin"
            />
          </label>
          <div className="form-two">
            <label>
              Kategori
              <select name="category">
                {(projectInfo.data?.categories.length
                  ? projectInfo.data.categories
                  : [
                      "Genel",
                      "Entegrasyon",
                      "Hesap ve erişim",
                      "Raporlama",
                      "Hata bildirimi",
                      "Geliştirme önerisi",
                    ]
                ).map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              Öncelik
              <select name="priority" defaultValue="normal">
                {Object.entries(priorities).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Etiketler
            <input
              name="tags"
              maxLength={330}
              placeholder="Örnek: entegrasyon, mobil"
            />
          </label>
          <label>
            Açıklama <span className="required">*</span>
            <textarea
              name="description"
              required
              maxLength={20000}
              rows={7}
              placeholder="Ne yapmak istediniz, ne oldu? Tekrarlama adımlarını ve beklediğiniz sonucu paylaşabilirsiniz."
              onPaste={(e) => {
                const images = clipboardImages(e);
                if (images.length) {
                  e.preventDefault();
                  setPaste(images);
                }
              }}
            />
          </label>
          <div className="label">Ekler</div>
          <AttachmentComposer
            scope={scope}
            onDraft={setDraft}
            onBusy={setFileBusy}
            pasteFiles={paste}
          />
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="form-actions">
            <Link className="button" to={base + "/tickets"}>
              Vazgeç
            </Link>
            <button className="button primary" disabled={busy || fileBusy}>
              <Send size={17} />
              {busy
                ? "Gönderiliyor…"
                : fileBusy
                  ? "Dosya taraması bekleniyor"
                  : "Talebi gönder"}
            </button>
          </div>
        </form>
        <aside className="form-help">
          <div className="card">
            <span className="kpi-icon aqua">
              <MessageSquare size={23} />
            </span>
            <h3>İyi bir başlangıç, hızlı bir çözüm.</h3>
            <p>Talebinizi anlaşılır ve kısa bir başlıkla tanımlayın.</p>
            <ul>
              <li>Sorunun oluştuğu ekranı belirtin.</li>
              <li>Tekrarlama adımlarını paylaşın.</li>
              <li>Varsa hata mesajını ekleyin.</li>
              <li>Ekran görüntülerini yapıştırın.</li>
            </ul>
          </div>
          <div className="privacy-note">
            <ShieldCheck size={21} />
            <p>
              Parola, kart numarası veya kimlik belgesi paylaşmayın. Ekran
              görüntülerindeki kişisel bilgileri maskeleyin.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
export function TicketDetail({
  scope,
  base,
  staff,
  write,
  role,
}: {
  scope: string;
  base: string;
  staff: boolean;
  write: boolean;
  role: string;
}) {
  const { id = "" } = useParams();
  return (
    <TicketDetailContent
      key={scope + id}
      scope={scope}
      base={base}
      staff={staff}
      write={write}
      role={role}
    />
  );
}
function TicketDetailContent({
  scope,
  base,
  staff,
  write,
  role,
}: {
  scope: string;
  base: string;
  staff: boolean;
  write: boolean;
  role: string;
}) {
  const { id = "" } = useParams();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["ticket", scope, id],
    queryFn: ({ signal }) => api<Ticket>(scope + "/tickets/" + id, { signal }),
  });
  const members = useQuery({
    queryKey: ["members", scope],
    queryFn: () => api<(User & { role: string })[]>(scope + "/members"),
    enabled: staff,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [fileBusy, setFileBusy] = useState(false);
  const [visibility, setVisibility] = useState("public");
  const [paste, setPaste] = useState<File[]>([]);
  const [body, setBody] = useState("");
  const [composer, setComposer] = useState(0);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const ticket = query.data;
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["ticket", scope, id] });
    void client.invalidateQueries({ queryKey: ["tickets"] });
  };
  const update = async (changes: unknown) => {
    if (!ticket) return;
    setError("");
    try {
      await api(scope + "/tickets/" + id, {
        method: "PATCH",
        headers: { "If-Match": `"${ticket.version}"` },
        body: JSON.stringify(changes),
      });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const reply = async (e: FormEvent) => {
    e.preventDefault();
    if (fileBusy) return;
    setBusy(true);
    setError("");
    try {
      await command(
        scope + "/tickets/" + id + "/comments",
        { body, visibility, draftId: draft || undefined },
        key,
      );
      setBody("");
      setDraft("");
      setPaste([]);
      setComposer((x) => x + 1);
      setKey(crypto.randomUUID());
      refresh();
    } catch (x) {
      setError((x as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const transition = async (e: FormEvent) => {
    e.preventDefault();
    if (!ticket) return;
    setError("");
    try {
      await api(scope + "/tickets/" + id + "/transitions", {
        method: "POST",
        headers: { "If-Match": `"${ticket.version}"` },
        body: JSON.stringify({ status: target, reason }),
      });
      setTarget("");
      setReason("");
      refresh();
    } catch (x) {
      setError((x as Error).message);
    }
  };
  if (query.isPending)
    return <div className="card empty-state">Talep yükleniyor…</div>;
  if (query.isError || !ticket)
    return (
      <div className="card empty-state error" role="alert">
        {query.error?.message || "Talep bulunamadı."}
      </div>
    );
  const transitions: Record<string, string[]> = {
    new: ["triaged", "cancelled"],
    triaged: ["in_progress", "cancelled"],
    in_progress: [
      "waiting_requester",
      "waiting_internal",
      "resolved",
      "cancelled",
    ],
    waiting_requester: ["in_progress", "resolved", "cancelled"],
    waiting_internal: ["in_progress", "resolved", "cancelled"],
    resolved: ["in_progress", "closed"],
  };
  const choices = staff
    ? transitions[ticket.status] || []
    : ticket.status === "new"
      ? ["cancelled"]
      : ticket.status === "resolved"
        ? ["in_progress", "closed"]
        : [];
  return (
    <>
      <Link className="back-link" to={base + "/tickets"}>
        <ArrowLeft size={16} />
        Taleplere dön
      </Link>
      <PageHeading
        title={ticket.title}
        subtitle={
          ticket.number +
          " · " +
          ticket.category +
          " · " +
          date(ticket.createdAt)
        }
        action={<Status value={ticket.status} />}
      />
      {error && (
        <div role="alert" className="error-banner">
          {error}
        </div>
      )}
      <div className="detail-layout">
        <div className="detail-main">
          <section className="card conversation">
            <div className="section-heading">
              <h2>Talep açıklaması</h2>
              <span className="muted inline">
                <UserRound size={16} />
                {ticket.requester.name}
              </span>
            </div>
            <p className="message-body">{ticket.description}</p>
            <AttachmentList scope={scope} files={ticket.attachments} />
          </section>
          <section className="card conversation">
            <div className="section-heading">
              <h2>Yazışmalar</h2>
              <span className="muted">{ticket.comments.length} mesaj</span>
            </div>
            {ticket.comments.map((comment) => (
              <article
                className={
                  "message " +
                  (comment.visibility === "internal" ? "internal" : "")
                }
                key={comment.id}
              >
                <div className="message-header">
                  <div className="table-user">
                    <span>
                      {comment.author.name
                        .split(" ")
                        .map((x) => x[0])
                        .join("")}
                    </span>
                    <strong>{comment.author.name}</strong>
                    {comment.source === "customer_agent" && <span className="pill">AI müşteri agentı</span>}
                    {comment.source === "external_agent" && <span className="pill">PO onaylı agent çözümü</span>}
                  </div>
                  <small>{date(comment.createdAt)}</small>
                </div>
                {comment.visibility === "internal" && (
                  <span className="internal-label">
                    <LockKeyhole size={13} />
                    İç not · Yalnız destek ekibi
                  </span>
                )}
                <p className="message-body">{comment.body}</p>
                <AttachmentList scope={scope} files={comment.attachments} />
              </article>
            ))}
            {!ticket.comments.length && (
              <div className="empty-state">
                Henüz mesaj yok. İlk yanıtı siz paylaşabilirsiniz.
              </div>
            )}
            {write && !["closed", "cancelled"].includes(ticket.status) && (
              <form
                className={
                  "reply-form " + (visibility === "internal" ? "internal" : "")
                }
                onSubmit={reply}
              >
                <div className="reply-toolbar">
                  <strong>
                    {visibility === "internal"
                      ? "Destek ekibine iç not"
                      : "Yanıtınızı paylaşın"}
                  </strong>
                  {staff && (
                    <select
                      aria-label="Yanıt görünürlüğü"
                      value={visibility}
                      onChange={(e) => {
                        setVisibility(e.target.value);
                        setDraft("");
                        setPaste([]);
                        setComposer((x) => x + 1);
                      }}
                    >
                      <option value="public">Müşteriye yanıt</option>
                      <option value="internal">İç not</option>
                    </select>
                  )}
                </div>
                <textarea
                  aria-label="Yanıt"
                  required
                  rows={5}
                  maxLength={20000}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder={
                    visibility === "internal"
                      ? "Bu mesaj yalnız destek ekibi tarafından görülebilir."
                      : "Yanıtınızı yazın veya ekran görüntüsünü yapıştırın…"
                  }
                  onPaste={(e) => {
                    const images = clipboardImages(e);
                    if (images.length) {
                      e.preventDefault();
                      setPaste(images);
                    }
                  }}
                />
                <AttachmentComposer
                  key={composer}
                  scope={scope}
                  ticketId={id}
                  visibility={visibility}
                  onDraft={setDraft}
                  onBusy={setFileBusy}
                  pasteFiles={paste}
                />
                <div className="form-actions">
                  <span className="muted inline">
                    {visibility === "internal" ? (
                      <LockKeyhole size={15} />
                    ) : (
                      <MessageSquare size={15} />
                    )}{" "}
                    {visibility === "internal"
                      ? "Müşteriye görünmez"
                      : "Talebin yetkili kullanıcıları görebilir"}
                  </span>
                  <button
                    className="button primary"
                    disabled={busy || fileBusy}
                  >
                    <Send size={16} />
                    {busy
                      ? "Gönderiliyor…"
                      : fileBusy
                        ? "Tarama bekleniyor"
                        : "Gönder"}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
        <aside className="detail-side">
          <section className="card">
            <h3>Talep bilgileri</h3>
            <label>
              Öncelik
              {staff && write ? (
                <select
                  value={ticket.priority}
                  onChange={(e) => void update({ priority: e.target.value })}
                >
                  {Object.entries(priorities).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              ) : (
                <span className={"priority " + ticket.priority}>
                  {priorities[ticket.priority]}
                </span>
              )}
            </label>
            <label>
              Atanan kişi
              {staff && write ? (
                <select
                  value={ticket.assignee?.id || ""}
                  onChange={(e) =>
                    void update({
                      assigneeId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">Atanmadı</option>
                  {members.data
                    ?.filter((m) =>
                      ["manager", "lead", "agent"].includes(m.role),
                    )
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                </select>
              ) : (
                <span>{ticket.assignee?.name || "Atanmadı"}</span>
              )}
            </label>
            <label>
              Talep sahibi<span>{ticket.requester.name}</span>
            </label>
            <label>
              Etiketler
              {staff && write ? (
                <input
                  defaultValue={ticket.tags.join(", ")}
                  key={ticket.tags.join(",")}
                  aria-label="Talep etiketleri"
                  onBlur={(e) => {
                    const tags = e.target.value
                      .split(",")
                      .map((x) => x.trim())
                      .filter(Boolean);
                    if (tags.join(",") !== ticket.tags.join(","))
                      void update({ tags });
                  }}
                />
              ) : (
                <span>{ticket.tags.join(", ") || "—"}</span>
              )}
            </label>
            {role === "manager" && (
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={ticket.legalHold}
                  disabled={!write}
                  onChange={(e) => void update({ legalHold: e.target.checked })}
                />
                Hukuki muhafaza (MFA gerekir)
              </label>
            )}
            <div className="divider" />
            <h3 className="inline">
              <Clock3 size={17} />
              SLA hedefleri
            </h3>
            <div className="sla-field">
              <small>İlk yanıt hedefi</small>
              <strong>{date(ticket.firstResponseDue)}</strong>
            </div>
            <div className="sla-field">
              <small>Çözüm hedefi</small>
              <strong>{date(ticket.resolutionDue)}</strong>
            </div>
            {ticket.slaRisk && (
              <p className="error inline">
                <AlertCircle size={16} />
                SLA hedefi aşıldı
              </p>
            )}
            {ticket.status === "waiting_requester" && (
              <small className="muted">
                Çözüm süresi müşteri yanıtı beklenirken duraklatılır.
              </small>
            )}
            {write && choices.length > 0 && (
              <form className="transition-form" onSubmit={transition}>
                <div className="divider" />
                <label>
                  Durum değiştir
                  <select
                    required
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                  >
                    <option value="">Yeni durum seçin</option>
                    {choices.map((k) => (
                      <option key={k} value={k}>
                        {statuses[k]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Gerekçe
                  <textarea
                    required
                    maxLength={1000}
                    rows={3}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Değişiklik veya çözüm açıklaması"
                  />
                </label>
                <button className="button full" type="submit">
                  Durumu güncelle
                </button>
              </form>
            )}
          </section>
          <section className="card">
            <h3 className="inline">
              <Activity size={17} />
              Talep geçmişi
            </h3>
            <div className="timeline">
              {ticket.events.map((event) => (
                <div key={event.id}>
                  <i />
                  <strong>
                    {statuses[event.detail] || event.detail || event.action}
                  </strong>
                  {event.reason && <small>{event.reason}</small>}
                  <small>{date(event.createdAt)}</small>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
