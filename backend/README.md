# SmartWatt Backend
**FastAPI + MySQL backend wired to your energyiq1 frontend**

---

## Files
```
main.py                       ← FastAPI entry point
schema.sql                    ← MySQL schema + seed data
requirements.txt
.env.example                  ← copy to .env
app/
  core/
    database.py               ← connection pool + query helpers
    auth.py                   ← bcrypt + JWT
  routers/
    auth.py                   ← POST /auth/login  GET /auth/me
    dashboard.py              ← GET /dashboard/*
    buildings.py              ← buildings / floors / rooms CRUD
    devices.py                ← devices / sensors CRUD + toggle + simulate
    usage.py                  ← usage records + CSV export
    alerts.py                 ← alerts + resolve/dismiss
    reports_settings.py       ← reports generate + settings CRUD
```

---

## Quick Start

### 1. Database
```bash
mysql -u root -p < schema.sql
```

### 2. Backend
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env → set DB_PASSWORD and SECRET_KEY

uvicorn main:app --reload --port 8000
```
→ API: http://localhost:8000  
→ Docs: http://localhost:8000/docs

### 3. Frontend
Open `index.html` directly in a browser **or** serve with:
```bash
cd /path/to/energyiq1
npx serve .   # or python -m http.server 5500
```
Login: `admin@smartwatt.com` / `admin123`

---

## Wiring your frontend to this backend

In your `dashboard.html` and `index.html`, replace the hardcoded mock logic
with `fetch()` calls. Here's the pattern for each page:

### Login (index.html)
```js
// Replace the hardcoded check with:
const res  = await fetch('http://localhost:8000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: `username=${email}&password=${pass}`,
});
const data = await res.json();
localStorage.setItem('sw_token', data.access_token);
localStorage.setItem('sw_user',  JSON.stringify(data));
window.location.href = 'dashboard.html';
```

### Auth header helper (add once in dashboard.html)
```js
const TOKEN = localStorage.getItem('sw_token');
const H = { 'Authorization': `Bearer ${TOKEN}` };
```

### Dashboard KPIs
```js
const kpi = await fetch('/dashboard/kpi', { headers: H }).then(r=>r.json());
document.getElementById('kpi-energy').textContent = kpi.total_energy_display;
document.getElementById('kpi-cost').textContent   = kpi.monthly_cost_display;
document.getElementById('kpi-devices').textContent = kpi.active_devices;
document.getElementById('kpi-alerts').textContent  = kpi.open_alerts;
```

### Live chart
```js
const chart = await fetch('/dashboard/live-chart', { headers: H }).then(r=>r.json());
// Pass chart.labels and chart.datasets[0].data to Chart.js
```

### Facility tree (Buildings page)
```js
const tree = await fetch('/buildings/1/tree', { headers: H }).then(r=>r.json());
```

### Device grid
```js
const devs = await fetch('/buildings/1/devices', { headers: H }).then(r=>r.json());
```

### Device toggle switch
```js
await fetch(`/devices/${deviceId}/toggle`, { method: 'POST', headers: H });
```

### Sensor table + Simulate button
```js
// Load table
const sensors = await fetch('/sensors?building_id=1', { headers: H }).then(r=>r.json());
// Simulate button
await fetch('/sensors/simulate?building_id=1', { method: 'POST', headers: H });
```

### Usage records table
```js
const usage = await fetch('/usage?building_id=1&page=1&page_size=20', { headers: H }).then(r=>r.json());
```

### Export CSV button
```js
window.open(`http://localhost:8000/usage/export/csv?building_id=1`, '_blank');
```

### Resolve alert
```js
await fetch(`/alerts/${alertId}/resolve`, { method: 'POST', headers: H });
```

### Generate report
```js
await fetch(`/reports/1/generate`, { method: 'POST', headers: H });
```

### Settings save
```js
await fetch('/settings', {
  method: 'PATCH',
  headers: { ...H, 'Content-Type': 'application/json' },
  body: JSON.stringify({ global_power_threshold_kw: 150, alert_email_enabled: true }),
});
```

---

## API Reference (all endpoints)

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/login | Login → JWT |
| GET | /auth/me | Current user |
| GET | /dashboard/kpi | KPI cards |
| GET | /dashboard/live-chart | Line chart data |
| GET | /dashboard/donut-chart | Energy by type |
| GET | /dashboard/bar-chart | Floor-wise bar |
| GET | /dashboard/efficiency | Progress bars |
| GET | /dashboard/trend | 6-month trend |
| GET | /dashboard/top-consumers | Top 5 devices |
| GET | /dashboard/sdg | SDG card stats |
| GET | /buildings | All buildings |
| GET | /buildings/{id}/tree | Full nested tree |
| POST | /buildings | Create building |
| GET | /buildings/{id}/floors | Floors list |
| POST | /buildings/{id}/floors | Add floor |
| GET | /floors/{id}/rooms | Rooms list |
| POST | /floors/{id}/rooms | Add room |
| GET | /rooms/{id} | Room detail |
| PATCH | /rooms/{id} | Update room |
| GET | /buildings/{id}/devices | Device grid |
| GET | /devices/{id} | Device + mini chart |
| POST | /devices | Add device |
| PATCH | /devices/{id} | Update device |
| POST | /devices/{id}/toggle | Toggle on/off |
| DELETE | /devices/{id} | Remove device |
| GET | /sensors | Sensor table |
| POST | /sensors/simulate | Simulate readings |
| GET | /usage | Paginated records |
| POST | /usage | Add reading |
| POST | /usage/bulk | Batch ingest (≤500) |
| GET | /usage/export/csv | CSV download |
| GET | /usage/summary | Grouped summary |
| GET | /alerts | Alert list |
| GET | /alerts/count | Badge count |
| POST | /alerts/{id}/resolve | Resolve alert |
| POST | /alerts/{id}/dismiss | Dismiss alert |
| POST | /reports/{id}/generate | Generate report |
| GET | /reports/{id} | Report history |
| GET | /settings | Load settings |
| PATCH | /settings | Save settings |

---

**Built for SmartWatt by shettyhimaa/energyiq1**
