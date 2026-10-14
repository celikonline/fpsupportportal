import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";
import {
  LayoutDashboard,
  Ticket as TicketIcon,
  Plus,
  Search,
  Bell,
  Settings,
  ShieldCheck,
  HelpCircle,
  LogOut,
  ChevronDown,
  Menu,
  Sun,
  Moon,
  ArrowUpRight,
  LifeBuoy,
  Building2,
  FolderKanban,
  LockKeyhole,
  KeyRound,
  Users,
  CheckCheck,
} from "lucide-react";
import {
  api,
  setCsrf,
  type User,
  type Tenant,
  type Project,
  roles,
} from "../shared/api";
import { TicketList, TicketDetail, NewTicket } from "../pages/Tickets";
import {
  SettingsPage,
  PrivacyPage,
  AuditPage,
  TenantAdminPage,
} from "../pages/Management";
import { InvitationPage } from "../pages/Invitations";
import { ApiKeysPage } from "../pages/ApiKeys";
import { AgentsPage } from "../pages/Agents";

type Session = {
  user: User | null;
  csrfToken: string;
  mfaEnabled: boolean;
  development: boolean;
  scanBypass: boolean;
  enrollmentRequired: boolean;
};
export function App() {
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () =>
      api<Session>("session").then((x) => {
        setCsrf(x.csrfToken);
        return x;
      }),
  });
  useEffect(() => {
    const expired = () => {
      client.removeQueries({ predicate: (q) => q.queryKey[0] !== "session" });
      void session.refetch();
    };
    window.addEventListener("fp-session-expired", expired);
    return () => window.removeEventListener("fp-session-expired", expired);
  }, [client, session.refetch]);
  if (session.isPending)
    return <div className="loading-page">Destek portalı yükleniyor…</div>;
  if (session.isError)
    return (
      <div className="loading-page error" role="alert">
        API'ye bağlanılamadı.{" "}
        <button className="button" onClick={() => void session.refetch()}>
          Tekrar dene
        </button>
      </div>
    );
  if (window.location.pathname === "/invite") return <InvitationPage />;
  if (!session.data.user)
    return (
      <Login
        onLogin={() => {
          client.clear();
          void session.refetch();
        }}
      />
    );
  if (session.data.enrollmentRequired)
    return (
      <main className="context-page">
        <Logo />
        <h1>Hesabınızı güvene alın</h1>
        <p>
          Çalışma alanlarınıza erişmeden önce iki aşamalı doğrulamayı
          etkinleştirin.
        </p>
        <SettingsPage
          scope=""
          project={accountProject}
          session={session.data}
          accountOnly
        />
      </main>
    );
  return (
    <Routes>
      <Route
        path="/t/:t/admin"
        element={<TenantAdministration session={session.data} />}
      />
      <Route path="/t/:t/p/:p/*" element={<Portal session={session.data} />} />
      <Route path="*" element={<SelectContext />} />
    </Routes>
  );
}
function Logo() {
  return (
    <div className="brand">
      <span className="brand-mark">
        f<span>p</span>
      </span>
      <div>
        faturaport<small>DESTEK PORTALI</small>
      </div>
    </div>
  );
}
function Login({ onLogin }: { onLogin: () => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      const result = await api<Session>("auth/login", {
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
    <div className="login-page">
      <section className="login-story">
        <Logo />
        <div>
          <span className="eyebrow">HER ADIMDA YANINIZDAYIZ</span>
          <h1>Birlikte çözelim.</h1>
          <p>
            Taleplerinizi tek yerden yönetin.
            <br />
            Ekibinizle iletişimde kalın, gelişmeleri takip edin.
          </p>
          <div className="story-ticket">
            <LifeBuoy size={34} />
            <strong>Size özel, güvenli destek.</strong>
            <span>
              Her proje için doğru ekip, her talep için açık iletişim.
            </span>
          </div>
        </div>
        <small>FaturaPort · Destek ve müşteri deneyimi</small>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <span className="pill">
            <ShieldCheck size={15} />
            Güvenli erişim
          </span>
          <h2>Hoş geldiniz</h2>
          <p className="muted">
            Destek portalına devam etmek için giriş yapın.
          </p>
          <label>
            Kullanıcı adı
            <input name="username" required autoComplete="username" />
          </label>
          <label>
            Parola
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            Doğrulama kodu <span className="muted">MFA etkinse</span>
            <input
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="6 haneli kod"
            />
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? "Giriş yapılıyor…" : "Giriş yap"}
            <ArrowUpRight size={18} />
          </button>
          <p className="login-note">
            <LockKeyhole size={15} />
            Verileriniz yetkili tenant ve proje kapsamında korunur.
          </p>
        </form>
      </section>
    </div>
  );
}
function SelectContext() {
  const navigate = useNavigate();
  const tenants = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<Tenant[]>("me/tenants"),
  });
  const [search] = useSearchParams();
  const [tenant, setTenant] = useState("");
  const active = tenant || search.get("tenant") || tenants.data?.[0]?.id || "";
  const projects = useQuery({
    queryKey: ["projects", active],
    queryFn: () => api<Project[]>("tenants/" + active + "/projects"),
    enabled: !!active,
  });
  return (
    <main className="context-page">
      <Logo />
      <div className="card">
        <span className="eyebrow">ÇALIŞMA ALANINIZ</span>
        <h1>Hangi projede devam edelim?</h1>
        <p className="muted">
          Yalnız erişim yetkiniz olan çalışma alanları gösterilir.
        </p>
        <label>
          Kuruluş
          <select value={active} onChange={(e) => setTenant(e.target.value)}>
            {tenants.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <div className="project-choices">
          {projects.data?.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/t/${active}/p/${p.id}`)}
            >
              <span className="project-symbol">
                <FolderKanban size={23} />
              </span>
              <div>
                <strong>{p.name}</strong>
                <small>{roles[p.role]}</small>
              </div>
              <ArrowUpRight size={19} />
            </button>
          ))}
        </div>
        {tenants.data?.find((x) => x.id === active)?.role === "admin" && (
          <Link className="button" to={`/t/${active}/admin`}>
            Kuruluş yönetimini aç
          </Link>
        )}
        {projects.data?.length === 0 && (
          <p>
            Henüz proje üyeliğiniz yok. Tenant yöneticinizden erişim isteyin.
          </p>
        )}
        {(projects.isError || tenants.isError) && (
          <p role="alert" className="error">
            Çalışma alanları yüklenemedi.
          </p>
        )}
      </div>
      <button
        className="button"
        onClick={() =>
          api("auth/logout", { method: "POST", body: "{}" }).then(() =>
            window.location.reload(),
          )
        }
      >
        Güvenli çıkış
      </button>
    </main>
  );
}
function TenantAdministration({ session }: { session: Session }) {
  const { t = "" } = useParams();
  return (
    <main className="tenant-management">
      <Logo />
      <div className="tenant-navigation">
        <Link className="button" to="/">
          Çalışma alanlarına dön
        </Link>
      </div>
      <SettingsPage
        accountOnly
        scope=""
        project={{
          id: "",
          name: "Kuruluş",
          code: "",
          role: "admin",
          archived: false,
          timezone: "Europe/Istanbul",
          firstResponseMinutes: 240,
          resolutionMinutes: 1440,
          businessStart: 9,
          businessEnd: 18,
          holidays: [],
          categories: [],
        }}
        session={session}
      />
      <TenantAdminPage tenantId={t} />
    </main>
  );
}
const accountProject: Project = {
  id: "",
  name: "Hesap",
  code: "",
  role: "admin",
  archived: false,
  timezone: "Europe/Istanbul",
  firstResponseMinutes: 240,
  resolutionMinutes: 1440,
  businessStart: 9,
  businessEnd: 18,
  holidays: [],
  categories: [],
};
function Portal({ session }: { session: Session }) {
  const { t = "", p = "" } = useParams();
  const scope = `tenants/${t}/projects/${p}`;
  const base = `/t/${t}/p/${p}`;
  const client = useQueryClient();
  const navigate = useNavigate();
  const [mobile, setMobile] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("fp-theme") === "dark",
  );
  const [showNotifications, setShowNotifications] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("fp-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    setMobile(false);
    setShowNotifications(false);
  }, [t, p]);
  const tenants = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<Tenant[]>("me/tenants"),
  });
  const projects = useQuery({
    queryKey: ["projects", t],
    queryFn: ({ signal }) =>
      api<Project[]>(`tenants/${t}/projects`, { signal }),
  });
  const project = projects.data?.find((x) => x.id === p);
  const tenant = tenants.data?.find((x) => x.id === t);
  const notifications = useQuery({
    queryKey: ["notifications", t, p],
    queryFn: ({ signal }) =>
      api<
        {
          id: string;
          ticketId: string;
          action: string;
          title: string;
          read: boolean;
        }[]
      >(scope + "/notifications", { signal }),
    enabled: !!project,
    refetchInterval: 30000,
  });
  const logout = async () => {
    await api("auth/logout", { method: "POST", body: "{}" });
    client.clear();
    navigate("/");
    window.location.reload();
  };
  if (projects.isPending)
    return <div className="loading-page">Proje yükleniyor…</div>;
  if (!project)
    return (
      <div className="context-page">
        <h1>Proje erişimi bulunamadı</h1>
        <p>Üyeliğiniz kaldırılmış veya bu proje için yetkiniz olmayabilir.</p>
        <Link className="button primary" to="/">
          Çalışma alanlarını aç
        </Link>
      </div>
    );
  const staff = ["manager", "lead", "agent"].includes(project.role);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        İçeriğe geç
      </a>
      <header className="topbar">
        <button
          className="icon-button mobile-menu"
          aria-label="Menüyü aç"
          onClick={() => setMobile(!mobile)}
        >
          <Menu size={21} />
        </button>
        <Logo />
        <div className="context-switch">
          <Building2 size={16} />
          <select
            aria-label="Kuruluş"
            value={t}
            onChange={(e) => navigate("/?tenant=" + e.target.value)}
          >
            {tenants.data?.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <span>/</span>
          <select
            aria-label="Proje"
            value={p}
            onChange={(e) => navigate(`/t/${t}/p/${e.target.value}`)}
          >
            {projects.data?.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </div>
        <div className="top-actions">
          <button
            className="icon-button"
            aria-label={dark ? "Açık temaya geç" : "Koyu temaya geç"}
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun size={19} /> : <Moon size={19} />}
          </button>
          <div className="notification-holder">
            <button
              className="icon-button"
              aria-label="Bildirimler"
              aria-expanded={showNotifications}
              onClick={() => setShowNotifications(!showNotifications)}
            >
              <Bell size={19} />
              {notifications.data?.some((x) => !x.read) && (
                <i className="notification-dot" />
              )}
            </button>
            {showNotifications && (
              <div className="notification-panel">
                <div className="panel-heading">
                  <strong>Bildirimler</strong>
                  <button
                    className="icon-button"
                    aria-label="Tümünü okundu işaretle"
                    onClick={() =>
                      api(scope + "/notifications", {
                        method: "POST",
                        body: "{}",
                      }).then(() =>
                        client.invalidateQueries({
                          queryKey: ["notifications", t, p],
                        }),
                      )
                    }
                  >
                    <CheckCheck size={18} />
                  </button>
                </div>
                {notifications.data?.map((n) => (
                  <Link
                    key={n.id}
                    to={base + "/tickets/" + n.ticketId}
                    onClick={() => setShowNotifications(false)}
                  >
                    {n.title}
                    <small>{n.read ? "Okundu" : "Yeni güncelleme"}</small>
                  </Link>
                ))}
                {!notifications.data?.length && (
                  <p className="muted">Yeni bildirim yok.</p>
                )}
              </div>
            )}
          </div>
          <Link
            className="icon-button"
            aria-label="Hesap ayarları"
            to={base + "/settings"}
          >
            <Settings size={19} />
          </Link>
          <div className="user-avatar">
            {session.user?.name
              .split(" ")
              .map((x) => x[0])
              .slice(0, 2)
              .join("")}
          </div>
        </div>
      </header>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Menüyü kapat"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <div className="workspace-label">ÇALIŞMA ALANI</div>
        <div className="workspace-card">
          <span className="project-symbol">
            <FolderKanban size={20} />
          </span>
          <div>
            <strong>{project.name}</strong>
            <small>{roles[project.role]}</small>
          </div>
        </div>
        <div className="nav-label">DESTEK</div>
        <nav onClick={() => setMobile(false)}>
          <NavLink end to={base}>
            <LayoutDashboard size={19} />
            Genel bakış
          </NavLink>
          <NavLink to={base + "/tickets"}>
            <TicketIcon size={19} />
            Destek talepleri
          </NavLink>
          {project.role !== "observer" && !project.archived && (
            <NavLink to={base + "/new"}>
              <Plus size={19} />
              Yeni talep
            </NavLink>
          )}
          <NavLink to={base + "/privacy"}>
            <ShieldCheck size={19} />
            Gizlilik merkezi
          </NavLink>
          <div className="nav-label">YÖNETİM</div>
          <NavLink to={base + "/settings"}>
            <Settings size={19} />
            Ayarlar
          </NavLink>
          <NavLink to={base + "/keys"}>
            <KeyRound size={19} />
            API anahtarları
          </NavLink>
          {staff && <NavLink to={base + "/agents"}><Users size={18} /> Agentlar ve PO</NavLink>}
          {tenant?.role === "admin" && (
            <NavLink to={base + "/admin"}>
              <Users size={19} />
              Kuruluş yönetimi
            </NavLink>
          )}
          {["admin", "auditor"].includes(tenant?.role || "") && (
            <NavLink to={base + "/audit"}>
              <LockKeyhole size={19} />
              Denetim kayıtları
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="support-tip">
            <LifeBuoy size={27} />
            <strong>Her talep bir çözümle başlar.</strong>
            <p>Doğru kategori ve ekran görüntüsü, süreci hızlandırır.</p>
            {project.role !== "observer" && !project.archived && (
              <Link to={base + "/new"}>
                Talep oluştur <ArrowUpRight size={15} />
              </Link>
            )}
          </div>
          <button className="logout" onClick={() => void logout()}>
            <LogOut size={17} />
            Güvenli çıkış
          </button>
        </div>
      </aside>
      <main id="main" className="main-content">
        <div className="breadcrumbs">
          {tenant?.name}
          <span>/</span>
          {project.name}
        </div>
        {session.scanBypass && (
          <div className="warning-banner">
            Geliştirme modu: antivirüs kontrolü devre dışı. Gerçek müşteri
            verisi kullanmayın.
          </div>
        )}
        {project.archived && (
          <div className="warning-banner">
            Bu proje arşivlenmiştir. Kayıtlar salt okunur.
          </div>
        )}
        <Routes>
          <Route
            index
            element={
              <TicketList
                scope={scope}
                base={base}
                dashboard
                staff={staff}
                write={project.role !== "observer" && !project.archived}
              />
            }
          />
          <Route
            path="tickets"
            element={
              <TicketList
                scope={scope}
                base={base}
                staff={staff}
                write={project.role !== "observer" && !project.archived}
              />
            }
          />
          <Route
            path="new"
            element={
              <NewTicket
                key={scope}
                scope={scope}
                base={base}
                write={project.role !== "observer" && !project.archived}
              />
            }
          />
          <Route
            path="tickets/:id"
            element={
              <TicketDetail
                key={scope}
                scope={scope}
                base={base}
                staff={staff}
                write={project.role !== "observer" && !project.archived}
                role={project.role}
              />
            }
          />
          <Route
            path="settings"
            element={
              <SettingsPage scope={scope} project={project} session={session} />
            }
          />
          <Route
            path="keys"
            element={
              <ApiKeysPage
                key={scope}
                scope={scope}
                base={base}
                projectName={project.name}
                canWrite={project.role !== "observer" && !project.archived}
                canBridge={project.role === "manager"}
                mfaEnabled={session.mfaEnabled}
              />
            }
          />
          {staff && <Route path="agents" element={<AgentsPage key={scope} scope={scope} base={base} role={project.role} archived={project.archived} />} />}
          <Route
            path="privacy"
            element={
              <PrivacyPage tenantId={t} admin={tenant?.role === "admin"} />
            }
          />
          <Route path="audit" element={<AuditPage tenantId={t} />} />
          <Route path="admin" element={<TenantAdminPage tenantId={t} />} />
          <Route
            path="*"
            element={
              <div className="card">
                <h1>Sayfa bulunamadı</h1>
                <Link to={base}>Genel bakışa dön</Link>
              </div>
            }
          />
        </Routes>
        <footer className="page-footer">
          <span>FaturaPort Destek</span>
          <span>
            <ShieldCheck size={13} />
            Yetkili erişim · Güvenli iletişim
          </span>
        </footer>
      </main>
    </div>
  );
}
