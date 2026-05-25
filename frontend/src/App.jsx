// App.jsx  – Energy Usage Monitoring System
// Requires: npm install recharts lucide-react axios
// Start: npm run dev  (Vite)

import { useState, useEffect, createContext, useContext } from "react";
import axios from "axios";
import {
    LineChart, Line, BarChart, Bar, XAxis, YAxis,
    CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
Zap, Building2, AlertTriangle, FileBarChart2, Cpu,
LogOut, LayoutDashboard, Bell, ChevronRight,
CheckCircle2, XCircle, Leaf, Thermometer, Sun,
} from "lucide-react";

// ─── Config ────────────────────────────────────────────────────
const API = "http://localhost:8000";
axios.defaults.baseURL = API;

// ─── Auth context ───────────────────────────────────────────────
const AuthCtx = createContext(null);
const useAuth = () => useContext(AuthCtx);

// ─── Axios token interceptor ────────────────────────────────────
function setAuthToken(token) {
if (token) {
    axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    localStorage.setItem("em_token", token);
} else {
    delete axios.defaults.headers.common["Authorization"];
    localStorage.removeItem("em_token");
    localStorage.removeItem("em_user");
}
}

// ─── Helpers ────────────────────────────────────────────────────
const fmt = (n, d = 2) => Number(n ?? 0).toFixed(d);
const STATUS_COLOR = {
active: "#16a34a",
resolved: "#2563eb",
dismissed: "#6b7280",
online: "#16a34a",
offline: "#dc2626",
faulty: "#f97316",
inactive: "#6b7280",
occupied: "#2563eb",
vacant: "#9ca3af",
};

// ═══════════════════════════════════════════════════════════════
// 1. LOGIN PAGE
// ═══════════════════════════════════════════════════════════════
function LoginPage({ onLogin }) {
const [email, setEmail] = useState("admin@ecotower.com");
const [password, setPassword] = useState("admin123");
const [error, setError] = useState("");
const [loading, setLoading] = useState(false);

async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    const { data } = await axios.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    setAuthToken(data.access_token);
    localStorage.setItem("em_user", JSON.stringify(data));
    onLogin(data);
    } catch {
    setError("Invalid email or password.");
    } finally {
    setLoading(false);
    }
}

return (
    <div style={styles.loginWrapper}>
    <div style={styles.loginCard}>
        <div style={styles.loginBrand}>
        <Zap size={32} color="#16a34a" />
        <h1 style={styles.loginTitle}>EnergyIQ</h1>
        </div>
        <p style={styles.loginSub}>Smart Building Energy Monitor</p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
            <label style={styles.label}>Email</label>
            <input style={styles.input} type="email" value={email}
            onChange={e => setEmail(e.target.value)} required />
        </div>
        <div>
            <label style={styles.label}>Password</label>
            <input style={styles.input} type="password" value={password}
            onChange={e => setPassword(e.target.value)} required />
        </div>
        {error && <p style={{ color: "#dc2626", fontSize: 13 }}>{error}</p>}
        <button style={styles.btnPrimary} type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
        </button>
        </form>
        <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 16, textAlign: "center" }}>
        Demo: admin@ecotower.com / admin123
        </p>
    </div>
    </div>
);
}

// ═══════════════════════════════════════════════════════════════
// 2. SIDEBAR
// ═══════════════════════════════════════════════════════════════
const NAV = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "devices", label: "Devices", Icon: Cpu },
  { id: "alerts", label: "Alerts", Icon: Bell },
  { id: "reports", label: "Reports", Icon: FileBarChart2 },
];

function Sidebar({ page, setPage, user, onLogout }) {
  return (
    <aside style={styles.sidebar}>
      <div style={styles.sidebarBrand}>
        <Zap size={22} color="#16a34a" />
        <span style={{ fontWeight: 700, fontSize: 18, color: "#111" }}>EnergyIQ</span>
      </div>
      <nav style={{ flex: 1, padding: "8px 0" }}>
        {NAV.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setPage(id)}
            style={{ ...styles.navItem, ...(page === id ? styles.navActive : {}) }}>
            <Icon size={18} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div style={styles.sidebarFooter}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#111" }}>{user.name}</div>
        <div style={{ fontSize: 12, color: "#6b7280", textTransform: "capitalize" }}>{user.role}</div>
        <button onClick={onLogout} style={styles.logoutBtn}>
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  );
}

// ═══════════════════════════════════════════════════════════════
// 3. DASHBOARD PAGE
// ═══════════════════════════════════════════════════════════════
function DashboardPage({ buildingId }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const { data } = await axios.get(`/dashboard/${buildingId}`);
        setStats(data);
      } catch { /* handle */ }
      setLoading(false);
    }
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [buildingId]);

  if (loading) return <div style={styles.loading}>Loading dashboard…</div>;
  if (!stats) return <div style={styles.loading}>No data available.</div>;

  const CARDS = [
    { label: "Energy Today", value: `${fmt(stats.total_energy_today_kwh)} kWh`, Icon: Zap, color: "#16a34a" },
    { label: "Active Devices", value: stats.active_devices, Icon: Cpu, color: "#2563eb" },
    { label: "Active Alerts", value: stats.active_alerts, Icon: AlertTriangle, color: "#dc2626" },
    { label: "Carbon Today", value: `${fmt(stats.carbon_today_kg)} kg CO₂`, Icon: Leaf, color: "#059669" },
  ];

  return (
    <div style={styles.page}>
      <h2 style={styles.pageTitle}>Dashboard</h2>
      <div style={styles.cardGrid}>
        {CARDS.map(({ label, value, Icon, color }) => (
          <div key={label} style={styles.statCard}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <p style={styles.statLabel}>{label}</p>
                <p style={{ ...styles.statValue, color }}>{value}</p>
              </div>
              <Icon size={28} color={color} style={{ opacity: 0.7 }} />
            </div>
          </div>
        ))}
      </div>

      <div style={styles.chartGrid}>
        <div style={styles.chartCard}>
          <h3 style={styles.cardTitle}>Hourly Consumption (Last 12 hrs)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={stats.hourly_usage}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0fdf4" />
              <XAxis dataKey="hour" tickFormatter={h => `${h}:00`} tick={{ fontSize: 11 }} />
              <YAxis unit=" kWh" tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`${v} kWh`, "Usage"]} />
              <Line type="monotone" dataKey="kwh" stroke="#16a34a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={styles.chartCard}>
          <h3 style={styles.cardTitle}>Room-wise Usage Today</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.room_usage} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0fdf4" />
              <XAxis type="number" unit=" kWh" tick={{ fontSize: 11 }} />
              <YAxis dataKey="room_number" type="category" tick={{ fontSize: 11 }} width={40} />
              <Tooltip formatter={v => [`${v} kWh`, "Usage"]} />
              <Bar dataKey="kwh" fill="#16a34a" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 4. DEVICES PAGE
// ═══════════════════════════════════════════════════════════════
function DevicesPage({ buildingId }) {
  const [devices, setDevices] = useState([]);
  const [selected, setSelected] = useState(null);
  const [usage, setUsage] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`/buildings/${buildingId}/devices`)
      .then(r => setDevices(r.data))
      .finally(() => setLoading(false));
  }, [buildingId]);

  function selectDevice(dev) {
    setSelected(dev);
    axios.get(`/devices/${dev.device_id}/usage?limit=20`)
      .then(r => setUsage(r.data));
  }

  if (loading) return <div style={styles.loading}>Loading devices…</div>;

  return (
    <div style={styles.page}>
      <h2 style={styles.pageTitle}>Devices</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {devices.map(dev => (
            <div key={dev.device_id}
              onClick={() => selectDevice(dev)}
              style={{
                ...styles.listCard,
                borderLeft: `4px solid ${STATUS_COLOR[dev.device_status] || "#9ca3af"}`,
                cursor: "pointer",
                background: selected?.device_id === dev.device_id ? "#f0fdf4" : "#fff",
              }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <p style={{ fontWeight: 600, fontSize: 14, margin: 0 }}>{dev.device_name}</p>
                  <p style={{ fontSize: 12, color: "#6b7280", margin: "2px 0 0" }}>
                    {dev.device_type} · {dev.power_rating_watts}W
                  </p>
                </div>
                <span style={{
                  ...styles.badge,
                  background: STATUS_COLOR[dev.device_status] + "20",
                  color: STATUS_COLOR[dev.device_status],
                }}>
                  {dev.device_status}
                </span>
              </div>
            </div>
          ))}
        </div>
        <div style={styles.chartCard}>
          {selected ? (
            <>
              <h3 style={styles.cardTitle}>{selected.device_name} – Recent Usage</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={[...usage].reverse()}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0fdf4" />
                  <XAxis dataKey="timestamp" tickFormatter={t => t?.slice(11, 16)}
                    tick={{ fontSize: 10 }} />
                  <YAxis unit=" kWh" tick={{ fontSize: 10 }} />
                  <Tooltip formatter={v => [`${v} kWh`, "Usage"]} />
                  <Line type="monotone" dataKey="energy_consumed_kwh"
                    stroke="#2563eb" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {["Time", "kWh", "Voltage", "Current"].map(h => (
                      <th key={h} style={styles.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {usage.slice(0, 5).map(u => (
                    <tr key={u.usage_id}>
                      <td style={styles.td}>{u.timestamp?.slice(11, 16)}</td>
                      <td style={styles.td}>{fmt(u.energy_consumed_kwh, 4)}</td>
                      <td style={styles.td}>{u.voltage ?? "—"}V</td>
                      <td style={styles.td}>{u.current_ampere ?? "—"}A</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div style={{ color: "#9ca3af", textAlign: "center", paddingTop: 60, fontSize: 14 }}>
              Select a device to see usage
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 5. ALERTS PAGE
// ═══════════════════════════════════════════════════════════════
function AlertsPage({ buildingId }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () =>
    axios.get(`/buildings/${buildingId}/alerts`)
      .then(r => setAlerts(r.data))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, [buildingId]);

  async function updateAlert(id, newStatus) {
    await axios.patch(`/alerts/${id}`, { status: newStatus });
    load();
  }

  if (loading) return <div style={styles.loading}>Loading alerts…</div>;

  const active = alerts.filter(a => a.status === "active");
  const resolved = alerts.filter(a => a.status !== "active");

  return (
    <div style={styles.page}>
      <h2 style={styles.pageTitle}>Alerts</h2>
      {active.length > 0 && (
        <>
          <h3 style={styles.sectionTitle}>Active ({active.length})</h3>
          {active.map(a => (
            <AlertCard key={a.alert_id} alert={a} onUpdate={updateAlert} />
          ))}
        </>
      )}
      {resolved.length > 0 && (
        <>
          <h3 style={{ ...styles.sectionTitle, marginTop: 24 }}>Resolved / Dismissed</h3>
          {resolved.map(a => (
            <AlertCard key={a.alert_id} alert={a} onUpdate={updateAlert} />
          ))}
        </>
      )}
      {alerts.length === 0 && (
        <div style={{ color: "#6b7280", textAlign: "center", paddingTop: 60 }}>
          No alerts found.
        </div>
      )}
    </div>
  );
}

function AlertCard({ alert: a, onUpdate }) {
  const isActive = a.status === "active";
  return (
    <div style={{
      ...styles.listCard,
      borderLeft: `4px solid ${isActive ? "#dc2626" : "#9ca3af"}`,
      marginBottom: 10,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <AlertTriangle size={16} color={isActive ? "#dc2626" : "#9ca3af"} />
            <p style={{ fontWeight: 600, fontSize: 14, margin: 0 }}>{a.alert_type}</p>
            <span style={{
              ...styles.badge,
              background: (STATUS_COLOR[a.status] || "#9ca3af") + "20",
              color: STATUS_COLOR[a.status] || "#9ca3af",
            }}>{a.status}</span>
          </div>
          <p style={{ fontSize: 13, color: "#374151", margin: "4px 0 0" }}>{a.alert_message}</p>
          <p style={{ fontSize: 11, color: "#9ca3af", margin: "4px 0 0" }}>
            {a.triggered_time?.replace("T", " ").slice(0, 19)}
            {a.threshold_value != null && ` · Threshold: ${a.threshold_value} kWh`}
          </p>
        </div>
        {isActive && (
          <div style={{ display: "flex", gap: 8, flexShrink: 0, marginLeft: 12 }}>
            <button style={styles.btnSmallGreen}
              onClick={() => onUpdate(a.alert_id, "resolved")}>
              <CheckCircle2 size={14} /> Resolve
            </button>
            <button style={styles.btnSmallGray}
              onClick={() => onUpdate(a.alert_id, "dismissed")}>
              <XCircle size={14} /> Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 6. REPORTS PAGE
// ═══════════════════════════════════════════════════════════════
function ReportsPage({ buildingId }) {
  const [reports, setReports] = useState([]);
  const [generating, setGenerating] = useState(false);

  const load = () =>
    axios.get(`/buildings/${buildingId}/reports`).then(r => setReports(r.data));

  useEffect(() => { load(); }, [buildingId]);

  async function generateReport() {
    setGenerating(true);
    await axios.post(`/buildings/${buildingId}/reports/generate`);
    await load();
    setGenerating(false);
  }

  return (
    <div style={styles.page}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={styles.pageTitle}>Energy Reports</h2>
        <button style={styles.btnPrimary} onClick={generateReport} disabled={generating}>
          {generating ? "Generating…" : "Generate Today's Report"}
        </button>
      </div>
      <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        {reports.map(r => (
          <div key={r.report_id} style={styles.listCard}>
            <div style={{ display: "flex", justify: "space-between", alignItems: "center", gap: 20 }}>
              <div style={{ flex: 1 }}>
                <p style={{ fontWeight: 600, fontSize: 14, margin: 0 }}>
                  Report – {r.report_date}
                </p>
                <p style={{ fontSize: 12, color: "#6b7280", margin: "4px 0 0" }}>
                  Report #{r.report_id}
                </p>
              </div>
              <div style={{ display: "flex", gap: 24 }}>
                <div style={{ textAlign: "right" }}>
                  <p style={{ fontSize: 12, color: "#9ca3af", margin: 0 }}>Total Energy</p>
                  <p style={{ fontSize: 18, fontWeight: 700, color: "#16a34a", margin: 0 }}>
                    {fmt(r.total_energy_kwh)} kWh
                  </p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p style={{ fontSize: 12, color: "#9ca3af", margin: 0 }}>Carbon</p>
                  <p style={{ fontSize: 18, fontWeight: 700, color: "#059669", margin: 0 }}>
                    {fmt(r.carbon_emission_estimate)} kg
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
        {reports.length === 0 && (
          <div style={{ color: "#6b7280", textAlign: "center", paddingTop: 60 }}>
            No reports yet. Click "Generate" to create one.
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 7. SHELL / ROUTER
// ═══════════════════════════════════════════════════════════════
function Shell({ user, onLogout }) {
  const [page, setPage] = useState("dashboard");
  const buildingId = user.building_id ?? 1;

  const PageComponent = {
    dashboard: <DashboardPage buildingId={buildingId} />,
    devices: <DevicesPage buildingId={buildingId} />,
    alerts: <AlertsPage buildingId={buildingId} />,
    reports: <ReportsPage buildingId={buildingId} />,
  }[page];

  return (
    <div style={styles.shell}>
      <Sidebar page={page} setPage={setPage} user={user} onLogout={onLogout} />
      <main style={styles.main}>{PageComponent}</main>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 8. ROOT
// ═══════════════════════════════════════════════════════════════
export default function App() {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem("em_user");
      const token = localStorage.getItem("em_token");
      if (saved && token) {
        setAuthToken(token);
        return JSON.parse(saved);
      }
    } catch { /* ignore */ }
    return null;
  });

  function handleLogin(data) { setUser(data); }
  function handleLogout() { setAuthToken(null); setUser(null); }

  if (!user) return <LoginPage onLogin={handleLogin} />;
  return <Shell user={user} onLogout={handleLogout} />;
}

// ═══════════════════════════════════════════════════════════════
// 9. STYLES
// ═══════════════════════════════════════════════════════════════
const styles = {
  loginWrapper: {
    minHeight: "100vh", display: "flex", alignItems: "center",
    justifyContent: "center", background: "#f0fdf4",
  },
  loginCard: {
    background: "#fff", padding: 36, borderRadius: 16,
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)", width: 360,
  },
  loginBrand: { display: "flex", alignItems: "center", gap: 10, marginBottom: 4 },
  loginTitle: { fontSize: 24, fontWeight: 800, color: "#111", margin: 0 },
  loginSub: { color: "#6b7280", fontSize: 13, margin: "0 0 24px" },
  label: { fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 },
  input: {
    width: "100%", padding: "10px 12px", borderRadius: 8,
    border: "1.5px solid #d1d5db", fontSize: 14, outline: "none",
    boxSizing: "border-box", fontFamily: "inherit",
  },
  btnPrimary: {
    background: "#16a34a", color: "#fff", border: "none",
    borderRadius: 8, padding: "10px 20px", fontSize: 14,
    fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
  },
  shell: { display: "flex", minHeight: "100vh", background: "#f9fafb" },
  sidebar: {
    width: 220, background: "#fff", borderRight: "1px solid #e5e7eb",
    display: "flex", flexDirection: "column", padding: 16, flexShrink: 0,
  },
  sidebarBrand: { display: "flex", alignItems: "center", gap: 8, marginBottom: 24 },
  navItem: {
    display: "flex", alignItems: "center", gap: 10, width: "100%",
    padding: "10px 12px", border: "none", background: "transparent",
    borderRadius: 8, cursor: "pointer", fontSize: 14, color: "#374151",
    fontFamily: "inherit", fontWeight: 500, marginBottom: 2,
    transition: "background 0.15s",
  },
  navActive: { background: "#f0fdf4", color: "#16a34a" },
  sidebarFooter: {
    borderTop: "1px solid #e5e7eb", paddingTop: 16, marginTop: 8,
  },
  logoutBtn: {
    display: "flex", alignItems: "center", gap: 6, marginTop: 10,
    background: "transparent", border: "1px solid #e5e7eb", borderRadius: 6,
    padding: "6px 10px", fontSize: 12, color: "#6b7280", cursor: "pointer",
    fontFamily: "inherit",
  },
  main: { flex: 1, overflow: "auto" },
  page: { padding: 28, maxWidth: 1100 },
  pageTitle: { fontSize: 22, fontWeight: 700, color: "#111", margin: "0 0 20px" },
  sectionTitle: { fontSize: 14, fontWeight: 600, color: "#374151", margin: "0 0 10px" },
  loading: { padding: 40, color: "#6b7280", textAlign: "center" },
  cardGrid: {
    display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
    gap: 16, marginBottom: 24,
  },
  statCard: {
    background: "#fff", borderRadius: 12, padding: 20,
    border: "1px solid #e5e7eb",
  },
  statLabel: { fontSize: 12, color: "#6b7280", margin: "0 0 4px", fontWeight: 500 },
  statValue: { fontSize: 22, fontWeight: 700, margin: 0 },
  chartGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 },
  chartCard: {
    background: "#fff", borderRadius: 12, padding: 20,
    border: "1px solid #e5e7eb",
  },
  cardTitle: { fontSize: 14, fontWeight: 600, color: "#374151", margin: "0 0 16px" },
  listCard: {
    background: "#fff", borderRadius: 10, padding: "14px 16px",
    border: "1px solid #e5e7eb",
  },
  badge: {
    fontSize: 11, fontWeight: 600, padding: "2px 8px",
    borderRadius: 20, display: "inline-block",
  },
  table: { width: "100%", borderCollapse: "collapse", marginTop: 16, fontSize: 12 },
  th: { textAlign: "left", color: "#6b7280", fontWeight: 600, padding: "6px 8px", borderBottom: "1px solid #e5e7eb" },
  td: { padding: "6px 8px", borderBottom: "1px solid #f3f4f6", color: "#374151" },
  btnSmallGreen: {
    display: "flex", alignItems: "center", gap: 4,
    background: "#f0fdf4", color: "#16a34a", border: "1px solid #bbf7d0",
    borderRadius: 6, padding: "5px 10px", fontSize: 12, cursor: "pointer",
    fontFamily: "inherit", fontWeight: 500,
  },
  btnSmallGray: {
    display: "flex", alignItems: "center", gap: 4,
    background: "#f9fafb", color: "#6b7280", border: "1px solid #e5e7eb",
    borderRadius: 6, padding: "5px 10px", fontSize: 12, cursor: "pointer",
    fontFamily: "inherit", fontWeight: 500,
  },
};
