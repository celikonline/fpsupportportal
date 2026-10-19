import { useMemo, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import {
  ArrowDownToLine,
  ArrowUpRight,
  CircleAlert,
  FileChartColumnIncreasing,
  FileText,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";

type InvoiceStatus = "Onaylandı" | "İşleniyor" | "Reddedildi" | "Taslak";
type Invoice = {
  id: string;
  number: string;
  date: string;
  party: string;
  direction: "Giden" | "Gelen";
  kind: string;
  status: InvoiceStatus;
  amount: number;
  currency: "TRY" | "EUR" | "USD";
  read: boolean;
  printed: boolean;
};

// Synthetic records keep the UI useful while no FaturaPort invoice API is connected.
const demoInvoices: Invoice[] = [
  {
    id: "demo-1",
    number: "DEMO-2026-0018",
    date: "2026-10-14",
    party: "Mavi Kırtasiye Ltd.",
    direction: "Giden",
    kind: "e-Arşiv · Satış",
    status: "Onaylandı",
    amount: 12840,
    currency: "TRY",
    read: true,
    printed: true,
  },
  {
    id: "demo-2",
    number: "DEMO-2026-0017",
    date: "2026-10-13",
    party: "Kuzey Ofis A.Ş.",
    direction: "Gelen",
    kind: "e-Fatura · Alış",
    status: "İşleniyor",
    amount: 6840.5,
    currency: "TRY",
    read: false,
    printed: false,
  },
  {
    id: "demo-3",
    number: "DEMO-2026-0016",
    date: "2026-10-11",
    party: "Ada Yazılım A.Ş.",
    direction: "Giden",
    kind: "e-Fatura · Satış",
    status: "Onaylandı",
    amount: 24900,
    currency: "TRY",
    read: true,
    printed: false,
  },
  {
    id: "demo-4",
    number: "DEMO-2026-0015",
    date: "2026-10-10",
    party: "Kuzey Ofis A.Ş.",
    direction: "Giden",
    kind: "e-Arşiv · İade",
    status: "Reddedildi",
    amount: 1720,
    currency: "TRY",
    read: true,
    printed: false,
  },
  {
    id: "demo-5",
    number: "DEMO-2026-0014",
    date: "2026-10-08",
    party: "Mavi Kırtasiye Ltd.",
    direction: "Gelen",
    kind: "e-Fatura · Alış",
    status: "Onaylandı",
    amount: 315,
    currency: "EUR",
    read: true,
    printed: true,
  },
  {
    id: "demo-6",
    number: "DEMO-2026-0013",
    date: "2026-10-06",
    party: "Ada Yazılım A.Ş.",
    direction: "Giden",
    kind: "e-Arşiv · Satış",
    status: "Taslak",
    amount: 4250,
    currency: "TRY",
    read: true,
    printed: false,
  },
  {
    id: "demo-7",
    number: "DEMO-2026-0012",
    date: "2026-10-03",
    party: "Kuzey Ofis A.Ş.",
    direction: "Gelen",
    kind: "e-Fatura · Alış",
    status: "Onaylandı",
    amount: 189.9,
    currency: "USD",
    read: false,
    printed: true,
  },
  {
    id: "demo-8",
    number: "DEMO-2026-0011",
    date: "2026-09-29",
    party: "Mavi Kırtasiye Ltd.",
    direction: "Giden",
    kind: "e-Arşiv · Satış",
    status: "İşleniyor",
    amount: 9900,
    currency: "TRY",
    read: true,
    printed: false,
  },
  {
    id: "demo-delivery-1",
    number: "IRS-DEMO-0004",
    date: "2026-10-05",
    party: "Kuzey Ofis A.Ş.",
    direction: "Giden",
    kind: "e-İrsaliye · Taslak",
    status: "Taslak",
    amount: 0,
    currency: "TRY",
    read: true,
    printed: false,
  },
];

const money = (amount: number, currency: Invoice["currency"]) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);

const shortDate = (value: string) =>
  new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" }).format(
    new Date(value + "T12:00:00"),
  );

function statusClass(status: InvoiceStatus) {
  return status.toLocaleLowerCase("tr-TR").replaceAll("ı", "i");
}

export function InvoicesPage({ base }: { base: string }) {
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Tümü");
  const [month, setMonth] = useState("2026-10");
  const [currency, setCurrency] = useState("Tümü");
  const [readStatus, setReadStatus] = useState("Tümü");
  const [printStatus, setPrintStatus] = useState("Tümü");
  const [draftType, setDraftType] = useState("Faturalar");
  const [selected, setSelected] = useState<Invoice | null>(null);

  const screen = location.pathname.split("/").filter(Boolean).at(-1);
  const current =
    screen === "incoming" || screen === "drafts" || screen === "reports"
      ? screen
      : "outgoing";
  const currentInvoices = useMemo(() => {
    let result = demoInvoices;
    if (current === "incoming")
      result = result.filter(
        (invoice) =>
          invoice.direction === "Gelen" &&
          !invoice.kind.startsWith("e-İrsaliye"),
      );
    else if (current === "drafts")
      result = result.filter(
        (invoice) =>
          invoice.status === "Taslak" &&
          (draftType === "İrsaliyeler"
            ? invoice.kind.startsWith("e-İrsaliye")
            : !invoice.kind.startsWith("e-İrsaliye")),
      );
    else if (current === "outgoing")
      result = result.filter(
        (invoice) =>
          invoice.direction === "Giden" &&
          !invoice.kind.startsWith("e-İrsaliye"),
      );
    if (month !== "all")
      result = result.filter((invoice) => invoice.date.startsWith(month));
    if (status !== "Tümü")
      result = result.filter((invoice) => invoice.status === status);
    if (currency !== "Tümü")
      result = result.filter((invoice) => invoice.currency === currency);
    if (readStatus !== "Tümü")
      result = result.filter(
        (invoice) => invoice.read === (readStatus === "Okundu"),
      );
    if (printStatus !== "Tümü")
      result = result.filter(
        (invoice) => invoice.printed === (printStatus === "Yazdırıldı"),
      );
    const normalized = query.trim().toLocaleLowerCase("tr-TR");
    if (normalized) {
      result = result.filter((invoice) =>
        `${invoice.number} ${invoice.party} ${invoice.kind} ${invoice.status}`
          .toLocaleLowerCase("tr-TR")
          .includes(normalized),
      );
    }
    return result;
  }, [
    current,
    currency,
    draftType,
    month,
    printStatus,
    query,
    readStatus,
    status,
  ]);

  const summary = useMemo(() => {
    const currentMonth = demoInvoices.filter(
      (invoice) =>
        invoice.date.startsWith("2026-10") &&
        !invoice.kind.startsWith("e-İrsaliye"),
    );
    return {
      total: currentMonth.length,
      outgoing: currentMonth.filter((invoice) => invoice.direction === "Giden")
        .length,
      incoming: currentMonth.filter((invoice) => invoice.direction === "Gelen")
        .length,
      attention: currentMonth.filter((invoice) =>
        ["İşleniyor", "Reddedildi"].includes(invoice.status),
      ).length,
    };
  }, []);

  return (
    <div className="invoice-module">
      <div className="page-heading">
        <div>
          <span className="eyebrow">FİNANS · E-BELGE YÖNETİMİ</span>
          <h1>Faturalar</h1>
          <p>Gelen ve giden faturalarınızı tek ekrandan izleyin.</p>
        </div>
        <button
          className="button primary"
          disabled
          title="Canlı e-belge servisi bağlantısı bekleniyor"
        >
          <FileText size={17} /> Yeni fatura
        </button>
      </div>

      <div className="invoice-demo-notice" role="note">
        <CircleAlert size={18} />
        <div>
          <strong>Arayüz ön izlemesi</strong>
          <span>
            Listede yalnızca sentetik demo verisi bulunur. Canlı
            FaturaPort/e-belge bağlantısı henüz yapılmadı.
          </span>
        </div>
      </div>

      {current !== "reports" && (
        <>
          <div className="invoice-kpis">
            <article className="invoice-kpi">
              <span>Bu ay toplam</span>
              <strong>{summary.total}</strong>
              <small>demo fatura</small>
            </article>
            <article className="invoice-kpi">
              <span>Giden</span>
              <strong>{summary.outgoing}</strong>
              <small>demo fatura</small>
            </article>
            <article className="invoice-kpi">
              <span>Gelen</span>
              <strong>{summary.incoming}</strong>
              <small>demo fatura</small>
            </article>
            <article className="invoice-kpi attention">
              <span>İşlem bekleyen</span>
              <strong>{summary.attention}</strong>
              <small>inceleme gerekli</small>
            </article>
          </div>

          <section className="card invoice-list-card">
            <div className="invoice-section-heading">
              <div>
                <h2>
                  {current === "incoming"
                    ? "Gelen faturalar"
                    : current === "drafts"
                      ? draftType === "İrsaliyeler"
                        ? "Taslak irsaliyeler"
                        : "Taslak faturalar"
                      : "Giden faturalar"}
                </h2>
                <p>Belge durumu, tarih ve cari bilgisine göre arayın.</p>
              </div>
              <span className="invoice-demo-badge">DEMO VERİSİ</span>
            </div>
            {current === "drafts" ? (
              <div
                className="invoice-tabs"
                role="tablist"
                aria-label="Taslak türü"
              >
                {(["Faturalar", "İrsaliyeler"] as const).map((item) => (
                  <button
                    key={item}
                    role="tab"
                    aria-selected={draftType === item}
                    className={draftType === item ? "active" : ""}
                    onClick={() => setDraftType(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            ) : (
              <div
                className="invoice-tabs"
                role="tablist"
                aria-label="Fatura türü"
              >
                <NavLink
                  end
                  to={base + "/invoices"}
                  className={current === "outgoing" ? "active" : ""}
                >
                  Giden
                </NavLink>
                <NavLink
                  to={base + "/invoices/incoming"}
                  className={current === "incoming" ? "active" : ""}
                >
                  Gelen
                </NavLink>
                <NavLink to={base + "/invoices/drafts"}>Taslaklar</NavLink>
              </div>
            )}
            <div className="invoice-filters">
              <label className="invoice-search">
                <Search size={16} />
                <span className="sr-only">Fatura ara</span>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Fatura no veya cari ara"
                />
              </label>
              <label>
                <span className="sr-only">Dönem</span>
                <select
                  aria-label="Dönem"
                  value={month}
                  onChange={(event) => setMonth(event.target.value)}
                >
                  <option value="2026-10">Ekim 2026</option>
                  <option value="2026-09">Eylül 2026</option>
                  <option value="all">Tüm tarihler</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Durum</span>
                <select
                  aria-label="Durum"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option>Tümü</option>
                  <option>Onaylandı</option>
                  <option>İşleniyor</option>
                  <option>Reddedildi</option>
                  <option>Taslak</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Para birimi</span>
                <select
                  aria-label="Para birimi"
                  value={currency}
                  onChange={(event) => setCurrency(event.target.value)}
                >
                  <option>Tümü</option>
                  <option value="TRY">₺ TRY</option>
                  <option value="EUR">€ EUR</option>
                  <option value="USD">$ USD</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Okunma durumu</span>
                <select
                  aria-label="Okunma durumu"
                  value={readStatus}
                  onChange={(event) => setReadStatus(event.target.value)}
                >
                  <option>Tümü</option>
                  <option>Okundu</option>
                  <option>Okunmadı</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Yazdırılma durumu</span>
                <select
                  aria-label="Yazdırılma durumu"
                  value={printStatus}
                  onChange={(event) => setPrintStatus(event.target.value)}
                >
                  <option>Tümü</option>
                  <option>Yazdırıldı</option>
                  <option>Yazdırılmadı</option>
                </select>
              </label>
              <button
                className="button small invoice-export"
                disabled
                title="Dışa aktarma canlı servis bağlantısıyla etkinleşecek"
              >
                <ArrowDownToLine size={15} /> Dışa aktar
              </button>
            </div>
            <div className="invoice-table-scroll">
              <table className="invoice-table">
                <thead>
                  <tr>
                    <th>
                      {current === "drafts" && draftType === "İrsaliyeler"
                        ? "İRSALİYE TARİHİ"
                        : "FATURA TARİHİ"}
                    </th>
                    <th>
                      {current === "drafts" && draftType === "İrsaliyeler"
                        ? "İRSALİYE NUMARASI"
                        : "FATURA NUMARASI"}
                    </th>
                    <th>CARİ</th>
                    <th>TÜR</th>
                    <th>DURUM</th>
                    <th>TUTAR</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {currentInvoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{shortDate(invoice.date)}</td>
                      <td>
                        <strong>{invoice.number}</strong>
                      </td>
                      <td>{invoice.party}</td>
                      <td>{invoice.kind}</td>
                      <td>
                        <span
                          className={`invoice-status ${statusClass(invoice.status)}`}
                        >
                          {invoice.status}
                        </span>
                      </td>
                      <td className="invoice-amount">
                        {money(invoice.amount, invoice.currency)}
                      </td>
                      <td>
                        <button
                          className="invoice-preview-button"
                          onClick={() => setSelected(invoice)}
                        >
                          Ön izleme
                        </button>
                      </td>
                    </tr>
                  ))}
                  {currentInvoices.length === 0 && (
                    <tr>
                      <td colSpan={7} className="invoice-empty">
                        Bu filtrelerle eşleşen demo fatura yok.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="invoice-list-footer">
              {currentInvoices.length} demo kayıt gösteriliyor{" "}
              <span>Canlı veri bağlantısı yapılınca sayfalama açılacak.</span>
            </div>
          </section>
          <section className="card invoice-quick-actions">
            <div className="invoice-section-heading">
              <div>
                <h2>Fatura işlemleri</h2>
                <p>Referans portaldaki yardımcı işlemler.</p>
              </div>
            </div>
            <div>
              <button className="button" disabled>
                GİB e-Arşiv faturası aktar
              </button>
              <button className="button" disabled>
                e-Fatura seri ayarları
              </button>
              <button className="button" disabled>
                KDV vergi raporu
              </button>
              <button className="button" disabled>
                e-Fatura tasarımları
              </button>
              <button className="button" disabled>
                Toplu PDF indir / yazdır
              </button>
            </div>
          </section>
          {current === "drafts" && (
            <section className="card invoice-quick-actions">
              <div className="invoice-section-heading">
                <div>
                  <h2>Taslak işlemleri</h2>
                  <p>Taslak belge hazırlama ve toplu faturalandırma akışı.</p>
                </div>
              </div>
              <div>
                <button className="button" disabled>
                  Yeni taslak fatura
                </button>
                <button className="button" disabled>
                  Yeni taslak irsaliye
                </button>
                <button className="button" disabled>
                  Toplu faturalandır
                </button>
              </div>
            </section>
          )}
        </>
      )}

      {current === "reports" && (
        <section className="invoice-reports">
          <div className="invoice-section-heading">
            <div>
              <h2>Fatura raporları</h2>
              <p>
                İlk sürüm rapor ekranı; değerler sentetik demo kayıtlardan
                hesaplanır.
              </p>
            </div>
            <FileChartColumnIncreasing size={25} />
          </div>
          <div className="invoice-report-grid">
            <article className="card">
              <span>GİDEN FATURALAR</span>
              <strong>{summary.outgoing}</strong>
              <small>Ekim 2026 · demo kayıt</small>
            </article>
            <article className="card">
              <span>GELEN FATURALAR</span>
              <strong>{summary.incoming}</strong>
              <small>Ekim 2026 · demo kayıt</small>
            </article>
            <article className="card">
              <span>İŞLEM BEKLEYEN</span>
              <strong>{summary.attention}</strong>
              <small>Durum incelemesi gerekli</small>
            </article>
          </div>
          <div className="card invoice-report-actions">
            <h3>Bağlantı bekleyen işlemler</h3>
            <p>
              Canlı e-belge servisi ve yetki kapsamı bağlanana kadar bu işlemler
              kapalıdır.
            </p>
            <div>
              <button className="button" disabled>
                Fatura raporu indir
              </button>
              <button className="button" disabled>
                KDV vergi raporu
              </button>
              <button className="button" disabled>
                Toplu PDF indir
              </button>
              <button className="button" disabled>
                Fatura serileri ve tasarımlar
              </button>
            </div>
          </div>
        </section>
      )}

      {selected && (
        <div
          className="invoice-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelected(null);
          }}
        >
          <section
            className="card invoice-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="invoice-preview-title"
          >
            <button
              className="icon-button invoice-modal-close"
              aria-label="Ön izlemeyi kapat"
              onClick={() => setSelected(null)}
            >
              <X size={18} />
            </button>
            <span className="eyebrow">SENTETİK ÖN İZLEME</span>
            <h2 id="invoice-preview-title">{selected.number}</h2>
            <p>
              {selected.party} · {shortDate(selected.date)}
            </p>
            <dl>
              <div>
                <dt>Belge türü</dt>
                <dd>{selected.kind}</dd>
              </div>
              <div>
                <dt>Yön</dt>
                <dd>{selected.direction}</dd>
              </div>
              <div>
                <dt>Durum</dt>
                <dd>{selected.status}</dd>
              </div>
              <div>
                <dt>Toplam</dt>
                <dd>{money(selected.amount, selected.currency)}</dd>
              </div>
            </dl>
            <div className="invoice-demo-notice compact">
              <ShieldCheck size={17} />
              <span>
                Ön izleme yalnızca demo kaydıdır; resmi belge niteliği taşımaz.
              </span>
            </div>
            <button
              className="button invoice-modal-done"
              onClick={() => setSelected(null)}
            >
              Kapat
            </button>
          </section>
        </div>
      )}

      <p className="invoice-module-footnote">
        <ShieldCheck size={14} /> Canlı müşteri faturalarına erişim için sunucu
        tarafı rol kontrolü, ürün API’si ve denetim kaydı entegrasyonu gerekir.
      </p>
      {current === "reports" && (
        <Link className="invoice-report-back" to={base + "/invoices"}>
          <ArrowUpRight size={15} /> Fatura listesine dön
        </Link>
      )}
    </div>
  );
}
