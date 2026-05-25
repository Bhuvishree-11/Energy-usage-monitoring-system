# Energy Usage Monitoring System
## Stack: React.js · FastAPI · MySQL

---

## 📁 File overview

| File | Purpose |
|------|---------|
| `schema.sql` | MySQL DDL + seed data |
| `main.py` | FastAPI backend (all routes) |
| `requirements.txt` | Python dependencies |
| `App.jsx` | React frontend (full dashboard) |
| `.env.example` | Environment variable template |

---

## 🗄 1. Database Setup (MySQL)

```bash
mysql -u root -p < schema.sql
```

This creates the `energy_monitor` database, all tables, and inserts seed data.

**Demo login credentials (already seeded):**
- Email: `admin@ecotower.com`
- Password: `admin123`

---

## ⚙️ 2. Backend Setup (FastAPI)

```bash
# Create and activate virtualenv
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MySQL credentials

# Start the API server
uvicorn main:app --reload
```

API base URL : http://localhost:8000  
Swagger docs : http://localhost:8000/docs

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL username |
| `DB_PASSWORD` | *(empty)* | MySQL password |
| `DB_NAME` | `energy_monitor` | Database name |
| `SECRET_KEY` | *(insecure default)* | JWT signing secret |
| `TOKEN_EXPIRE_MINUTES` | `480` | JWT lifetime |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS origin |

---

## ⚛️ 3. Frontend Setup (React + Vite)

```bash
npm create vite@latest energy-monitor -- --template react
cd energy-monitor

npm install
npm install recharts lucide-react axios

# Replace src/App.jsx with the provided App.jsx
# In src/index.css, add: * { margin:0; padding:0; box-sizing: border-box; }

npm run dev
```

Frontend: http://localhost:5173

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | ✗ | Login → JWT |
| GET | `/health` | ✗ | Health check |
| GET | `/dashboard/{building_id}` | ✓ | Stats + charts |
| GET | `/buildings` | ✓ | All buildings |
| GET | `/buildings/{id}/floors` | ✓ | Floors in building |
| GET | `/floors/{id}/rooms` | ✓ | Rooms on floor |
| GET | `/buildings/{id}/devices` | ✓ | All devices in building |
| GET | `/rooms/{id}/devices` | ✓ | Devices in room |
| GET | `/devices/{id}/usage` | ✓ | Energy logs |
| POST | `/usage` | ✓ | Add energy reading |
| GET | `/buildings/{id}/alerts` | ✓ | All alerts |
| PATCH | `/alerts/{id}` | ✓ | Resolve / dismiss alert |
| GET | `/buildings/{id}/reports` | ✓ | Energy reports |
| POST | `/buildings/{id}/reports/generate` | ✓ | Auto-generate today's report |

All protected endpoints require `Authorization: Bearer <token>` header (handled automatically by the React app).

---

## 🌍 SDG Alignment
- **SDG 7** – Affordable and clean energy tracking  
- **SDG 11** – Sustainable cities & smart buildings  
- **SDG 12** – Responsible consumption monitoring  
- **SDG 13** – Carbon footprint visibility  
