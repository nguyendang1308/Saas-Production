# SaaS Dashboard

Hệ thống quản lý SaaS Dashboard với xác thực, subscription, multi-tenant và báo cáo analytics.

---

## 🚀 Tech Stack

### Backend
- **FastAPI** (Python 3.12+) — Web framework
- **SQLAlchemy 2.0** (async) — ORM
- **PostgreSQL 16** — Database
- **Redis** — Cache, session store & rate limiting
- **JWT** — Authentication (python-jose)
- **bcrypt** — Password hashing

### Frontend (Phase 3)
- **Next.js 16** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**

### DevOps (Phase 5)
- **Docker & Docker Compose**
- **Nginx** — Reverse proxy
- **GitHub Actions** — CI/CD

---

## 📁 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Environment settings
│   │   ├── database.py          # SQLAlchemy async setup
│   │   ├── dependencies.py      # Reusable DI
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API routes
│   │   ├── services/            # Business logic
│   │   └── middleware/          # Auth & rate limit
│   ├── tests/                   # Pytest suite
│   ├── requirements.txt
│   ├── pytest.ini
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## ⚡ Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for local dev)
- [uv](https://github.com/astral-sh/uv) (recommended)

### 1. Clone & Setup

```bash
git clone <repo-url>
cd saas-dashboard
cp .env.example .env
```

### 2. Run with Docker

```bash
docker-compose up -d postgres redis
```

### 3. Run Backend (local dev)

```bash
cd backend
uv venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

uv pip install -r requirements.txt
export PYTHONPATH="."
uvicorn app.main:app --reload
```

Backend sẽ chạy tại: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `GET /health`

---

## 🔐 Authentication API

### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```
**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```
> Refresh token được set tự động trong `httpOnly` cookie.

### Refresh Token
```http
POST /api/auth/refresh
Cookie: refresh_token=<token>
```

### Logout
```http
POST /api/auth/logout
Authorization: Bearer <access_token>
Cookie: refresh_token=<token>
```

### Get Current User
```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

### OAuth — Google
```http
POST /api/auth/oauth/google
Content-Type: application/json

{
  "token": "<google_id_token>"
}
```

### OAuth — GitHub
```http
POST /api/auth/oauth/github
Content-Type: application/json

{
  "token": "<github_access_token>"
}
```

---

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | *(required)* |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token TTL | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh token TTL | `7` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | *(optional)* |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | *(optional)* |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID | *(optional)* |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret | *(optional)* |
| `ENVIRONMENT` | `development` / `production` | `development` |

---

## 🧪 Testing

```bash
cd backend
export PYTHONPATH="."
pytest tests/ -v
```

**Current status:** ✅ 18/18 tests passing

---

## 📅 Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| **Phase 1** | Authentication (JWT, OAuth, Rate Limit) | ✅ Complete |
| **Phase 2** | Subscription & Billing (Stripe, PayOS) | 🔄 Upcoming |
| **Phase 3** | Admin Dashboard UI (Next.js, shadcn/ui) | 🔄 Upcoming |
| **Phase 4** | Multi-Tenancy (PostgreSQL RLS) | 🔄 Upcoming |
| **Phase 5** | Docker Production & CI/CD | 🔄 Upcoming |

---

## 🛡️ Security Highlights

- **bcrypt** with 12 rounds for password hashing
- **JWT** access tokens (15 min) + refresh tokens (7 days)
- **HttpOnly** cookies for refresh tokens
- **Redis blacklist** for revoked tokens
- **Rate limiting** (5 login attempts / minute per IP)
- **CSRF protection** via SameSite=Lax cookies

---

## 📄 License

MIT
