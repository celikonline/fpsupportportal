import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, type Ticket, type User, date } from "../shared/api";
import { PageHeading } from "./Tickets";

type Config = {
  enabled: boolean;
  botId: number | null;
  externalAgentIds: number[];
  instructions: string;
  modelReady: boolean;
  model: string;
  replyErrors?: { ticketId: string; error: string; attempts: number }[];
};
type Work = {
  id: string;
  ticketId: string;
  state: string;
  version: number;
  ticketVersion: number;
  assigneeId: number | null;
  reason: string;
  solution: string;
  leaseUntil: string | null;
  ticket: Ticket;
};
const states: Record<string, string> = {
  review: "PO değerlendirmesi",
  queued: "Dış agent kuyruğu",
  claimed: "Agent çalışıyor",
  human: "İnsana atandı",
  solution_review: "Çözüm onayı bekliyor",
  done: "Tamamlandı",
};

export function AgentsPage({
  scope,
  base,
  role,
  archived,
}: {
  scope: string;
  base: string;
  role: string;
  archived: boolean;
}) {
  const po = ["manager", "lead"].includes(role);
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [filter, setFilter] = useState("review");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const config = useQuery({
    queryKey: ["automation", scope],
    queryFn: () => api<Config>(scope + "/automation"),
    enabled: po,
  });
  const members = useQuery({
    queryKey: ["agent-members", scope],
    queryFn: () => api<(User & { role: string })[]>(scope + "/members"),
    enabled: po,
  });
  const works = useQuery({
    queryKey: ["work-items", scope, filter, page],
    queryFn: () =>
      api<{ results: Work[]; total: number }>(
        scope + `/work-items?state=${filter}&page=${page}`,
      ),
    refetchInterval: 15000,
  });
  const staff = (members.data || []).filter((m) =>
    ["agent", "manager", "lead"].includes(m.role),
  );

  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const values = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api(scope + "/automation", {
        method: "PUT",
        body: JSON.stringify({
          enabled: values.get("enabled") === "on",
          botId: values.get("botId") ? Number(values.get("botId")) : null,
          externalAgentIds: values.getAll("externalAgentIds").map(Number),
          instructions: values.get("instructions"),
        }),
      });
      await client.invalidateQueries({ queryKey: ["automation", scope] });
      setSuccess("Agent ayarları kaydedildi.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const decide = async (
    work: Work,
    action: string,
    assigneeId: number | null,
    reason: string,
  ) => {
    setError("");
    setSuccess("");
    await api(scope + "/work-items/tickets/" + work.ticketId, {
      method: "POST",
      body: JSON.stringify({
        action,
        assigneeId,
        reason,
        version: work.version,
        ticketVersion: work.ticket.version,
      }),
    });
    await client.invalidateQueries({ queryKey: ["work-items", scope] });
    await client.invalidateQueries({ queryKey: ["tickets", scope] });
    setSuccess(
      action === "approve"
        ? "Çözüm onaylandı ve müşteriye yayınlandı."
        : "İş yönlendirildi.",
    );
  };

  return (
    <>
      <PageHeading
        title="Agentlar ve PO iş akışı"
        subtitle="Müşteri iletişimi, iş değerlendirmesi ve çözüm kuyruğu."
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
      <div className="card agent-flow">
        <strong>
          Talep → PO değerlendirmesi → Dış agent / İnsan → Çözüm onayı → Müşteri
        </strong>
        <p>
          Portal agentı yeni taleplere ve müşteri mesajlarına model API’siyle
          yanıt verir. Dış agent kendisine atanmış işi MCP üzerinden alır; çözüm
          PO onayıyla yayınlanır.
        </p>
      </div>
      {po && config.isError && (
        <p className="error-banner">
          Agent ayarları okunamadı: {config.error.message}
        </p>
      )}
      {po && members.isError && (
        <p className="error-banner">Destek üyeleri yüklenemedi.</p>
      )}
      {po && config.data && (
        <section className="card agent-settings">
          <h2>Agent hesapları</h2>
          {!config.data.modelReady && (
            <p className="warning-banner">
              Müşteri agentı için sunucuda model bağlantısı henüz ayarlanmamış.
              AI_API_URL, AI_API_KEY ve AI_MODEL değerlerini tanımlayın.
            </p>
          )}
          <form key={JSON.stringify(config.data)} onSubmit={save}>
            <label>
              Müşteri agentı hesabı
              <select name="botId" defaultValue={config.data.botId ?? ""}>
                <option value="">Seçin</option>
                {staff.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="agent-checkbox">
              <input
                type="checkbox"
                name="enabled"
                defaultChecked={config.data.enabled}
                disabled={!config.data.modelReady}
              />{" "}
              Otomatik müşteri yanıtlarını etkinleştir
            </label>
            <fieldset>
              <legend>Dış agent hesapları</legend>
              <p className="muted">
                Her agent için ayrı destek hesabı seçin. PO ve müşteri agentı
                farklı hesaplarda çalışır.
              </p>
              {staff.map((m) => (
                <label key={m.id} className="agent-checkbox">
                  <input
                    type="checkbox"
                    name="externalAgentIds"
                    value={m.id}
                    defaultChecked={config.data!.externalAgentIds.includes(
                      m.id,
                    )}
                  />
                  {m.name}
                </label>
              ))}
            </fieldset>
            <label>
              Müşteri agentı yönergeleri
              <textarea
                name="instructions"
                defaultValue={config.data.instructions}
                maxLength={8000}
                rows={4}
                placeholder="Ürün bilgisi, yanıt üslubu ve ne zaman insan desteği isteneceği…"
              />
            </label>
            <p className="muted">
              Kaydetmeden önce Ayarlar’da güncel MFA koduyla doğrulayın.
              {config.data.model && ` Model: ${config.data.model}`}
            </p>
            <button className="button primary" disabled={busy || archived}>
              {busy ? "Kaydediliyor…" : "Ayarları kaydet"}
            </button>
          </form>
          {!!config.data.replyErrors?.length && (
            <div>
              <h3>Müşteri yanıtı hataları</h3>
              {config.data.replyErrors.map((job) => (
                <div key={job.ticketId} className="agent-work">
                  <Link to={base + "/tickets/" + job.ticketId}>Talebi aç</Link>
                  <p>
                    {job.error} ({job.attempts}/5 deneme)
                  </p>
                  <button
                    className="button"
                    disabled={busy || archived || !config.data!.enabled}
                    onClick={async () => {
                      setBusy(true);
                      setError("");
                      try {
                        await api(
                          scope +
                            "/automation/replies/" +
                            job.ticketId +
                            "/retry",
                          { method: "POST", body: "{}" },
                        );
                        await config.refetch();
                      } catch (cause) {
                        setError((cause as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Yeniden dene
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
      <section className="card agent-queue">
        <div className="api-key-section-head">
          <h2>{po ? "PO iş kuyruğu" : "Bana atanan işler"}</h2>
          <select
            aria-label="İş durumu"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setPage(1);
            }}
          >
            {Object.entries(states).map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {works.isPending && <p>İşler yükleniyor…</p>}
        {works.isError && (
          <p className="error-banner" role="alert">
            {works.error.message}
          </p>
        )}
        {works.data?.results.length === 0 && (
          <p className="muted">Bu aşamada iş bulunmuyor.</p>
        )}
        {works.data?.results.map((work) => (
          <WorkCard
            key={work.id + ":" + work.version + ":" + work.ticket.version}
            work={work}
            base={base}
            po={po && !archived}
            staff={staff}
            config={config.data}
            decide={decide}
          />
        ))}
        {works.data && works.data.total > 20 && (
          <div className="agent-pager">
            <button
              className="button"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Önceki
            </button>
            <span>Sayfa {page}</span>
            <button
              className="button"
              disabled={page * 20 >= works.data.total}
              onClick={() => setPage(page + 1)}
            >
              Sonraki
            </button>
          </div>
        )}
      </section>
      <section className="card agent-settings">
        <h2>Dış agentı bağlama</h2>
        <p>
          Seçtiğiniz dış agent hesabıyla giriş yapıp{" "}
          <Link to={base + "/keys"}>API anahtarları</Link> ekranından
          okuma/yazma anahtarı oluşturun. MCP sunucusunu{" "}
          <code>apps/mcp/server.py</code> ile çalıştırın. Bağlantı ve tüketim
          döngüsü için <code>docs/agent-workflow.md</code> rehberini kullanın.
        </p>
      </section>
    </>
  );
}

function WorkCard({
  work,
  base,
  po,
  staff,
  config,
  decide,
}: {
  work: Work;
  base: string;
  po: boolean;
  staff: (User & { role: string })[];
  config?: Config;
  decide: (
    work: Work,
    action: string,
    assignee: number | null,
    reason: string,
  ) => Promise<void>;
}) {
  const [action, setAction] = useState(
    work.state === "solution_review" &&
      work.ticketVersion === work.ticket.version
      ? "approve"
      : "external",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const choices = staff.filter((m) =>
    action === "external"
      ? config?.externalAgentIds.includes(m.id)
      : !config?.externalAgentIds.includes(m.id) && m.id !== config?.botId,
  );
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const values = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await decide(
        work,
        action,
        values.get("assigneeId") ? Number(values.get("assigneeId")) : null,
        String(values.get("reason")),
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <article className="agent-work">
      <div className="api-key-section-head">
        <Link to={base + "/tickets/" + work.ticketId}>
          <strong>
            {work.ticket.number} · {work.ticket.title}
          </strong>
        </Link>
        <span className="pill">{states[work.state]}</span>
      </div>
      {work.reason && <p className="message-body">{work.reason}</p>}
      {work.assigneeId && (
        <p className="muted">
          Atanan:{" "}
          {staff.find((m) => m.id === work.assigneeId)?.name ||
            work.ticket.assignee?.name ||
            work.assigneeId}
        </p>
      )}
      {work.leaseUntil && (
        <p className="muted">İş sahipliği: {date(work.leaseUntil)}</p>
      )}
      {work.solution && (
        <>
          <h3>Önerilen çözüm</h3>
          <p className="message-body">{work.solution}</p>
        </>
      )}
      {work.state === "solution_review" &&
        work.ticketVersion !== work.ticket.version && (
          <p className="warning-banner">
            Çözümden sonra talep değişti. İşi yeniden değerlendirip yönlendirin.
          </p>
        )}
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      {po &&
        !["closed", "cancelled", "resolved"].includes(work.ticket.status) && (
          <form onSubmit={submit}>
            <div className="form-two">
              <label>
                PO kararı
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                >
                  <option value="external">Dış agenta yönlendir</option>
                  <option value="human">İnsana yönlendir</option>
                  {work.state === "solution_review" &&
                    work.ticketVersion === work.ticket.version && (
                      <option value="approve">Çözümü onayla ve yayınla</option>
                    )}
                </select>
              </label>
              {action !== "approve" && (
                <label>
                  Atanan
                  <select
                    name="assigneeId"
                    required
                    key={action}
                    defaultValue=""
                  >
                    <option value="">Seçin</option>
                    {choices.map((m) => (
                      <option value={m.id} key={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            <label>
              Değerlendirme / kabul koşulları
              <textarea name="reason" required maxLength={4000} rows={2} />
            </label>
            <button className="button primary" disabled={busy}>
              {busy
                ? "İşleniyor…"
                : action === "approve"
                  ? "Onayla ve müşteriye yayınla"
                  : "İşi yönlendir"}
            </button>
          </form>
        )}
    </article>
  );
}
