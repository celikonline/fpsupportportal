import { useMemo, useState } from "react";
import { useLocation } from "react-router";
import {
  ArrowDownToLine,
  CircleAlert,
  FileChartColumnIncreasing,
  Search,
  ShieldCheck,
} from "lucide-react";

type ModuleKey =
  | "parties"
  | "money"
  | "accounts"
  | "orders"
  | "offers"
  | "stock"
  | "dispatch"
  | "receipts"
  | "ecommerce"
  | "cheques"
  | "reports";

type Row = { cells: string[]; state: string; searchable: string };
type ModuleConfig = {
  title: string;
  description: string;
  action: string;
  tabs?: string[];
  statuses?: string[];
  columns: string[];
  quickActions?: string[];
  rows: Row[];
};

const configs: Record<ModuleKey, ModuleConfig> = {
  parties: {
    title: "Cariler",
    description: "Müşteri ve tedarikçi hesaplarını yönetin.",
    action: "Yeni cari ekle",
    quickActions: [
      "Bakiye raporu",
      "Borçlular raporu",
      "Alacaklılar raporu",
      "Cari detay raporu",
      "İçe aktar",
    ],
    statuses: ["Müşteri", "Tedarikçi"],
    columns: ["CARİ ADI", "CARİ TÜRÜ", "BAKİYE DURUMU", "BAKİYE"],
    rows: [
      {
        cells: ["Mavi Kırtasiye Ltd.", "Müşteri", "Alacaklı", "₺ 12.840,00"],
        state: "Müşteri",
        searchable: "mavi kırtasiye müşteri alacaklı",
      },
      {
        cells: ["Kuzey Ofis A.Ş.", "Tedarikçi", "Borçlu", "₺ 6.840,50"],
        state: "Tedarikçi",
        searchable: "kuzey ofis tedarikçi borçlu",
      },
      {
        cells: ["Ada Yazılım A.Ş.", "Müşteri", "Dengede", "₺ 0,00"],
        state: "Müşteri",
        searchable: "ada yazılım müşteri dengede",
      },
    ],
  },
  money: {
    title: "Gelir & Gider",
    description: "Tahsilatları, ödemeleri ve gider fişlerini takip edin.",
    action: "Yeni işlem",
    quickActions: [
      "Yeni gelir",
      "Hızlı gider fişi",
      "Detaylı gider fişi",
      "Gider raporu",
    ],
    tabs: ["Giderler", "Gelirler"],
    statuses: ["Ödendi", "Bekliyor", "İptal"],
    columns: ["TARİH", "AÇIKLAMA", "CARİ", "DURUM", "TUTAR"],
    rows: [
      {
        cells: [
          "14.10.2026",
          "Ofis gideri",
          "Kuzey Ofis A.Ş.",
          "Ödendi",
          "₺ 2.450,00",
        ],
        state: "Ödendi",
        searchable: "ofis gideri kuzey ödendi",
      },
      {
        cells: [
          "12.10.2026",
          "Hizmet tahsilatı",
          "Mavi Kırtasiye Ltd.",
          "Bekliyor",
          "₺ 8.400,00",
        ],
        state: "Bekliyor",
        searchable: "hizmet tahsilatı mavi bekliyor",
      },
      {
        cells: [
          "08.10.2026",
          "Yazılım lisansı",
          "Ada Yazılım A.Ş.",
          "Ödendi",
          "₺ 1.200,00",
        ],
        state: "Ödendi",
        searchable: "yazılım lisansı ada ödendi",
      },
    ],
  },
  accounts: {
    title: "Hesaplar",
    description: "Kasa, banka, kart ve POS hesaplarındaki hareketleri izleyin.",
    action: "Yeni hesap ekle",
    quickActions: [
      "Hesap ekstresi",
      "Tahsilatlar raporu",
      "Ödemeler raporu",
      "Gün sonu raporu",
    ],
    tabs: ["Tümü", "Kasa", "Banka", "Kredi kartı", "POS"],
    statuses: ["Giriş", "Çıkış"],
    columns: ["TARİH", "HESAP", "İŞLEM", "AÇIKLAMA", "TUTAR"],
    rows: [
      {
        cells: ["14.10.2026", "Ana kasa", "Giriş", "Tahsilat", "₺ 8.400,00"],
        state: "Giriş",
        searchable: "ana kasa tahsilat giriş",
      },
      {
        cells: [
          "12.10.2026",
          "İş Bankası",
          "Çıkış",
          "Tedarikçi ödemesi",
          "₺ 2.450,00",
        ],
        state: "Çıkış",
        searchable: "iş bankası tedarikçi ödeme çıkış",
      },
      {
        cells: [
          "08.10.2026",
          "Şirket kartı",
          "Çıkış",
          "Yazılım lisansı",
          "₺ 1.200,00",
        ],
        state: "Çıkış",
        searchable: "şirket kartı yazılım lisansı çıkış",
      },
    ],
  },
  orders: {
    title: "Siparişler",
    description: "Siparişleri cari, tarih ve işlem durumuna göre izleyin.",
    action: "Yeni sipariş",
    quickActions: ["Sipariş raporları"],
    tabs: ["Siparişler"],
    statuses: ["Bekliyor", "Onaylandı", "Tamamlandı"],
    columns: ["TARİH", "SİPARİŞ NO", "CARİ", "DURUM", "TOPLAM"],
    rows: [
      {
        cells: [
          "14.10.2026",
          "SPR-DEMO-018",
          "Mavi Kırtasiye Ltd.",
          "Bekliyor",
          "₺ 12.840,00",
        ],
        state: "Bekliyor",
        searchable: "spr demo 018 mavi kırtasiye bekliyor",
      },
      {
        cells: [
          "11.10.2026",
          "SPR-DEMO-017",
          "Ada Yazılım A.Ş.",
          "Onaylandı",
          "₺ 24.900,00",
        ],
        state: "Onaylandı",
        searchable: "spr demo 017 ada yazılım onaylandı",
      },
    ],
  },
  offers: {
    title: "Proforma & Teklif",
    description:
      "Teklifleri ve proforma belgelerini hazırlık durumuna göre takip edin.",
    action: "Yeni belge",
    quickActions: ["Yeni teklif", "Yeni proforma fatura"],
    tabs: ["Proforma faturalar", "Teklifler"],
    statuses: ["Taslak", "Gönderildi", "Onaylandı", "Reddedildi"],
    columns: ["TARİH", "BELGE NO", "CARİ", "DURUM", "TOPLAM"],
    rows: [
      {
        cells: [
          "14.10.2026",
          "TEK-DEMO-012",
          "Mavi Kırtasiye Ltd.",
          "Gönderildi",
          "₺ 6.800,00",
        ],
        state: "Gönderildi",
        searchable: "tek demo 012 mavi teklif gönderildi",
      },
      {
        cells: [
          "10.10.2026",
          "PRO-DEMO-008",
          "Kuzey Ofis A.Ş.",
          "Taslak",
          "₺ 3.450,00",
        ],
        state: "Taslak",
        searchable: "pro demo 008 kuzey proforma taslak",
      },
    ],
  },
  stock: {
    title: "Stok",
    description:
      "Stok kartları, stok fişleri ve depo listelerini tek alanda görüntüleyin.",
    action: "Yeni stok işlemi",
    quickActions: ["Stok girişi", "Stok çıkışı", "Depolar arası transfer"],
    tabs: ["Stok kartları", "Stok fişleri", "Depolar"],
    statuses: ["Aktif", "Pasif"],
    columns: ["KAYIT", "KOD", "DEPO", "DURUM"],
    rows: [
      {
        cells: ["Demo Ürün A", "STK-DEMO-01", "Ana depo", "Aktif"],
        state: "Aktif",
        searchable: "demo ürün a stk demo 01 ana depo",
      },
      {
        cells: ["Demo Ürün B", "STK-DEMO-02", "İkinci depo", "Aktif"],
        state: "Aktif",
        searchable: "demo ürün b stk demo 02 ikinci depo",
      },
      {
        cells: ["Stok giriş fişi", "FIS-DEMO-01", "Ana depo", "Aktif"],
        state: "Aktif",
        searchable: "stok giriş fişi fis demo 01 ana depo",
      },
      {
        cells: ["Ana depo", "DPO-DEMO-01", "Ana depo", "Aktif"],
        state: "Aktif",
        searchable: "ana depo dpo demo 01 depo",
      },
    ],
  },
  dispatch: {
    title: "e-İrsaliye",
    description: "Giden ve gelen e-İrsaliyeleri ve taslakları takip edin.",
    action: "Yeni irsaliye",
    quickActions: ["e-Fatura seri ayarları"],
    tabs: ["Giden", "Gelen", "Taslaklar"],
    statuses: ["Onaylandı", "İşleniyor", "Reddedildi"],
    columns: ["TARİH", "İRSALİYE NO", "CARİ", "DURUM", "TÜR"],
    rows: [
      {
        cells: [
          "14.10.2026",
          "IRS-DEMO-011",
          "Mavi Kırtasiye Ltd.",
          "Onaylandı",
          "Giden",
        ],
        state: "Onaylandı",
        searchable: "irs demo 011 mavi giden onaylandı",
      },
      {
        cells: [
          "12.10.2026",
          "IRS-DEMO-010",
          "Kuzey Ofis A.Ş.",
          "İşleniyor",
          "Gelen",
        ],
        state: "İşleniyor",
        searchable: "irs demo 010 kuzey gelen işleniyor",
      },
    ],
  },
  receipts: {
    title: "e-SMM",
    description:
      "Serbest meslek makbuzlarını giden ve taslak durumlarına göre takip edin.",
    action: "Yeni e-SMM",
    quickActions: ["GİB e-Arşiv aktar", "Seri ayarları"],
    tabs: ["Giden", "Taslak"],
    statuses: ["Onaylandı", "İşleniyor", "Taslak"],
    columns: ["TARİH", "BELGE NO", "ALICI", "DURUM", "TUTAR"],
    rows: [
      {
        cells: [
          "13.10.2026",
          "SMM-DEMO-006",
          "Ada Yazılım A.Ş.",
          "Onaylandı",
          "₺ 4.200,00",
        ],
        state: "Onaylandı",
        searchable: "smm demo 006 ada yazılım onaylandı",
      },
      {
        cells: [
          "09.10.2026",
          "SMM-DEMO-005",
          "Kuzey Ofis A.Ş.",
          "Taslak",
          "₺ 2.750,00",
        ],
        state: "Taslak",
        searchable: "smm demo 005 kuzey ofis taslak",
      },
    ],
  },
  ecommerce: {
    title: "e-Ticaret",
    description:
      "Pazaryeri siparişlerini, entegrasyonları ve toplu faturalandırma kuyruğunu izleyin.",
    action: "Pazaryeri bağlantısı",
    quickActions: [
      "e-Fatura seri ayarları",
      "Fatura raporları",
      "Pazaryeri entegrasyonları",
      "Toplu faturalandır",
    ],
    tabs: ["Siparişler"],
    statuses: ["Faturalandırılacak", "Faturalandırıldı", "İptal"],
    columns: ["SİPARİŞ TARİHİ", "SİPARİŞ NO", "KANAL", "DURUM", "TOPLAM"],
    rows: [
      {
        cells: [
          "14.10.2026",
          "PAZ-DEMO-018",
          "Demo mağaza A",
          "Faturalandırılacak",
          "₺ 2.890,00",
        ],
        state: "Faturalandırılacak",
        searchable: "paz demo 018 mağaza a faturalandırılacak",
      },
      {
        cells: [
          "10.10.2026",
          "PAZ-DEMO-017",
          "Demo mağaza B",
          "Faturalandırıldı",
          "₺ 1.450,00",
        ],
        state: "Faturalandırıldı",
        searchable: "paz demo 017 mağaza b faturalandırıldı",
      },
    ],
  },
  cheques: {
    title: "Çek & Senet",
    description:
      "Alınan ve verilen çek/senet kayıtlarını işlem ve durumlarına göre takip edin.",
    action: "Yeni işlem",
    quickActions: [
      "Çek girişi",
      "Çek çıkışı",
      "Senet girişi",
      "Senet çıkışı",
      "Raporlar",
    ],
    tabs: ["Çek", "Senet"],
    statuses: ["Portföyde", "Tahsil edildi", "Ödendi"],
    columns: ["VADE TARİHİ", "BELGE NO", "CARİ", "DURUM", "TUTAR"],
    rows: [
      {
        cells: [
          "21.10.2026",
          "CEK-DEMO-004",
          "Mavi Kırtasiye Ltd.",
          "Portföyde",
          "₺ 5.000,00",
        ],
        state: "Portföyde",
        searchable: "çek cek demo 004 mavi portföyde",
      },
      {
        cells: [
          "25.10.2026",
          "SEN-DEMO-003",
          "Kuzey Ofis A.Ş.",
          "Ödendi",
          "₺ 3.200,00",
        ],
        state: "Ödendi",
        searchable: "senet sen demo 003 kuzey ödendi",
      },
    ],
  },
  reports: {
    title: "Raporlar",
    description:
      "Cari, fatura, gelir-gider ve hesap hareketlerine ilişkin rapor alanı.",
    action: "Rapor indir",
    columns: ["RAPOR", "AÇIKLAMA", "DÖNEM", "DURUM"],
    rows: [
      {
        cells: [
          "Fatura özeti",
          "Gelen ve giden belge sayıları",
          "Ekim 2026",
          "Demo",
        ],
        state: "Demo",
        searchable: "fatura özeti gelen giden belge",
      },
      {
        cells: [
          "KDV görünümü",
          "Satış ve alış vergi özeti",
          "Ekim 2026",
          "Demo",
        ],
        state: "Demo",
        searchable: "kdv görünümü vergi satış alış",
      },
      {
        cells: [
          "Cari bakiye",
          "Cari borç ve alacak özeti",
          "Ekim 2026",
          "Demo",
        ],
        state: "Demo",
        searchable: "cari bakiye borç alacak",
      },
    ],
  },
};

const labels: Record<ModuleKey, string> = {
  parties: "Cariler",
  money: "Gelir & Gider",
  accounts: "Hesaplar",
  orders: "Siparişler",
  offers: "Proforma & Teklif",
  stock: "Stok",
  dispatch: "e-İrsaliye",
  receipts: "e-SMM",
  ecommerce: "e-Ticaret",
  cheques: "Çek & Senet",
  reports: "Raporlar",
};

const keyFromPath: Record<string, ModuleKey> = {
  parties: "parties",
  money: "money",
  accounts: "accounts",
  orders: "orders",
  offers: "offers",
  stock: "stock",
  dispatch: "dispatch",
  receipts: "receipts",
  ecommerce: "ecommerce",
  cheques: "cheques",
  reports: "reports",
};

export function BusinessModulesPage() {
  const location = useLocation();
  const moduleKey =
    keyFromPath[location.pathname.split("/").filter(Boolean).at(-1) || ""] ||
    "parties";
  const config = configs[moduleKey];
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("Tümü");
  const [period, setPeriod] = useState("Bu ay");
  const [tab, setTab] = useState(config.tabs?.[0] || "Tümü");
  const [preview, setPreview] = useState<Row | null>(null);

  const rows = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("tr-TR");
    return config.rows.filter((row) => {
      const matchesStatus = status === "Tümü" || row.state === status;
      const matchesSearch =
        !needle || row.searchable.toLocaleLowerCase("tr-TR").includes(needle);
      const rowDate = row.cells.find((cell) =>
        /^\d{2}\.\d{2}\.\d{4}$/.test(cell),
      );
      const targetMonth =
        period === "Bu ay" ? "10.2026" : period === "Geçen ay" ? "09.2026" : "";
      const matchesPeriod =
        !rowDate || !targetMonth || rowDate.slice(3) === targetMonth;
      const matchesTab =
        !config.tabs ||
        ["Tümü", "Siparişler"].includes(tab) ||
        row.cells.some(
          (cell) =>
            cell.toLocaleLowerCase("tr-TR") === tab.toLocaleLowerCase("tr-TR"),
        ) ||
        (moduleKey === "money" &&
          ((tab === "Gelirler" && row.searchable.includes("tahsilat")) ||
            (tab === "Giderler" && row.searchable.includes("gider")))) ||
        (moduleKey === "accounts" &&
          ((tab === "Kasa" && row.searchable.includes("kasa")) ||
            (tab === "Banka" && row.searchable.includes("banka")) ||
            (tab === "Kredi kartı" && row.searchable.includes("kart")) ||
            (tab === "POS" && row.searchable.includes("pos")))) ||
        (moduleKey === "offers" &&
          ((tab === "Proforma faturalar" && row.searchable.includes("pro")) ||
            (tab === "Teklifler" && row.searchable.includes("teklif")))) ||
        (moduleKey === "stock" &&
          ((tab === "Stok kartları" && row.searchable.includes("ürün")) ||
            (tab === "Stok fişleri" && row.searchable.includes("fiş")) ||
            (tab === "Depolar" && row.searchable.includes("depo")))) ||
        (moduleKey === "dispatch" &&
          ((tab === "Giden" && row.searchable.includes("giden")) ||
            (tab === "Gelen" && row.searchable.includes("gelen")) ||
            (tab === "Taslaklar" && row.state === "Taslak"))) ||
        (moduleKey === "receipts" &&
          ((tab === "Giden" && row.state !== "Taslak") ||
            (tab === "Taslak" && row.state === "Taslak"))) ||
        (moduleKey === "cheques" &&
          ((tab === "Çek" && row.searchable.startsWith("çek")) ||
            (tab === "Senet" && row.searchable.startsWith("senet"))));
      return matchesStatus && matchesSearch && matchesTab && matchesPeriod;
    });
  }, [config, moduleKey, period, search, status, tab]);

  return (
    <div className="business-module">
      <div className="page-heading">
        <div>
          <span className="eyebrow">FATURAPORT · ÜRÜN MODÜLÜ</span>
          <h1>{labels[moduleKey]}</h1>
          <p>{config.description}</p>
        </div>
        <button
          className="button primary"
          disabled
          title="Canlı Faturaport servis bağlantısı bekleniyor"
        >
          {config.action}
        </button>
      </div>
      <div className="invoice-demo-notice" role="note">
        <CircleAlert size={18} />
        <div>
          <strong>Arayüz ön izlemesi</strong>
          <span>
            Sentetik demo kayıtları gösteriliyor. Canlı kayıt ve yazma işlemleri
            ürün API bağlantısından sonra açılacak.
          </span>
        </div>
      </div>
      {moduleKey === "reports" ? (
        <section className="business-report-grid">
          {config.rows.map((row) => (
            <article className="card" key={row.cells[0]}>
              <FileChartColumnIncreasing size={20} />
              <h2>{row.cells[0]}</h2>
              <p>{row.cells[1]}</p>
              <small>
                {row.cells[2]} · {row.cells[3]}
              </small>
              <button className="button small" disabled>
                <ArrowDownToLine size={15} /> İndir
              </button>
            </article>
          ))}
        </section>
      ) : (
        <section className="card business-list-card">
          <div className="invoice-section-heading">
            <div>
              <h2>{labels[moduleKey]} listesi</h2>
              <p>Kaydı arayın, sekme ve duruma göre daraltın.</p>
            </div>
            <span className="invoice-demo-badge">DEMO VERİSİ</span>
          </div>
          {config.tabs && config.tabs.length > 1 && (
            <div
              className="invoice-tabs"
              role="tablist"
              aria-label={`${labels[moduleKey]} görünümü`}
            >
              {config.tabs.map((item) => (
                <button
                  key={item}
                  className={tab === item ? "active" : ""}
                  role="tab"
                  aria-selected={tab === item}
                  onClick={() => setTab(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          )}
          <div className="invoice-filters">
            <label className="invoice-search">
              <Search size={16} />
              <span className="sr-only">{labels[moduleKey]} ara</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Ad, belge no veya açıklama ara"
              />
            </label>
            <label>
              <span className="sr-only">Dönem</span>
              <select
                aria-label="Dönem"
                value={period}
                onChange={(event) => setPeriod(event.target.value)}
              >
                <option>Bu ay</option>
                <option>Geçen ay</option>
                <option>Tüm tarihler</option>
              </select>
            </label>
            {config.statuses && (
              <label>
                <span className="sr-only">Durum</span>
                <select
                  aria-label="Durum"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option>Tümü</option>
                  {config.statuses.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
            )}
            <button
              className="button small"
              disabled
              title="Canlı servis bağlantısı bekleniyor"
            >
              <ArrowDownToLine size={15} /> Dışa aktar
            </button>
          </div>
          <div className="invoice-table-scroll">
            <table className="invoice-table">
              <thead>
                <tr>
                  {config.columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.searchable}>
                    {row.cells.map((cell, index) => (
                      <td key={config.columns[index]}>
                        {index === 0 &&
                        [
                          "money",
                          "accounts",
                          "orders",
                          "offers",
                          "dispatch",
                          "receipts",
                        ].includes(moduleKey) ? (
                          <strong>{cell}</strong>
                        ) : (
                          cell
                        )}
                      </td>
                    ))}
                    <td>
                      <button
                        className="invoice-preview-button"
                        onClick={() => setPreview(row)}
                      >
                        Ön izleme
                      </button>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={config.columns.length + 1}
                      className="invoice-empty"
                    >
                      Bu filtrelerle eşleşen demo kayıt bulunamadı.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="invoice-list-footer">
            {rows.length} demo kayıt gösteriliyor
            <span>
              Dışa aktarma ve kayıt işlemleri canlı API bağlantısıyla açılacak.
            </span>
          </div>
        </section>
      )}
      {config.quickActions && moduleKey !== "reports" && (
        <section className="card invoice-quick-actions">
          <div className="invoice-section-heading">
            <div>
              <h2>Yeni işlem</h2>
              <p>Referans Faturaport ekranındaki ilgili işlemler.</p>
            </div>
          </div>
          <div>
            {config.quickActions.map((action) => (
              <button
                className="button"
                key={action}
                disabled
                title="Canlı ürün API bağlantısı bekleniyor"
              >
                {action}
              </button>
            ))}
          </div>
        </section>
      )}
      {preview && (
        <div
          className="invoice-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setPreview(null);
          }}
        >
          <section
            className="card invoice-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="business-preview-title"
          >
            <button
              className="icon-button invoice-modal-close"
              aria-label="Ön izlemeyi kapat"
              onClick={() => setPreview(null)}
            >
              ×
            </button>
            <span className="eyebrow">DEMO KAYDI</span>
            <h2 id="business-preview-title">{preview.cells[0]}</h2>
            <p>{preview.searchable}</p>
            <dl>
              {preview.cells.slice(1).map((cell, index) => (
                <div key={`${cell}-${index}`}>
                  <dt>{config.columns[index + 1]}</dt>
                  <dd>{cell}</dd>
                </div>
              ))}
            </dl>
            <div className="invoice-demo-notice compact">
              <ShieldCheck size={17} />
              <span>
                Bu, arayüz geliştirmesi için kullanılan sentetik bir kayıttır.
              </span>
            </div>
            <button
              className="button invoice-modal-done"
              onClick={() => setPreview(null)}
            >
              Kapat
            </button>
          </section>
        </div>
      )}
      <p className="invoice-module-footnote">
        <ShieldCheck size={14} /> Gerçek finans verileri için sunucu tarafı rol
        kontrolü, ürün API’si ve denetim kaydı gerekir.
      </p>
    </div>
  );
}
