# Restaurant Bot — Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Deploy on VPS (DigitalOcean/Hetzner)](#deploy-on-vps)
4. [Deploy on Railway](#deploy-on-railway)
5. [Deploy on Render](#deploy-on-render)
6. [Deploy with Docker](#deploy-with-docker)
7. [Environment Variables](#environment-variables)
8. [Database Setup](#database-setup)
9. [Domain & SSL](#domain--ssl)
10. [WhatsApp Setup](#whatsapp-setup)
11. [Cost Breakdown](#cost-breakdown)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.12+
- uv (Python package manager): `pip install uv`
- An Anthropic API key from https://console.anthropic.com
- (Optional) Docker for containerized deployment
- (Optional) PostgreSQL for production database

---

## Local Development

### Quick Start (2 minutes)

```bash
# 1. Clone the project
cd restaurant-bot

# 2. Create .env file
cp .env.example .env
# Edit .env — set your LLM_API_KEY

# 3. Install dependencies
uv sync

# 4. Start the server
uv run uvicorn src.restaurant_bot.main:app --host 0.0.0.0 --port 8005

# 5. Seed demo data (in a new terminal)
uv run python -m scripts.seed_demo
```

### URLs
- API Docs: http://localhost:8005/docs
- Admin Panel: http://localhost:8005/static/admin.html
- Chat Widget: http://localhost:8005/static/chat.html
- Demo Website: http://localhost:8005/static/demo.html
- Health Check: http://localhost:8005/health

### Demo Login
- Email: admin@goldenfork.com
- Password: admin123

---

## Deploy on VPS

Best for: Full control, cheapest long-term ($5-10/month)

### Step 1: Get a VPS

Recommended providers:
- **Hetzner** — $4.5/month (best value, EU/US servers)
- **DigitalOcean** — $6/month (easy UI)
- **Vultr** — $5/month
- **Linode** — $5/month

Minimum specs: 1 CPU, 1GB RAM, 25GB SSD, Ubuntu 22.04

### Step 2: SSH into your server

```bash
ssh root@your-server-ip
```

### Step 3: Install dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python 3.12
apt install -y python3.12 python3.12-venv python3-pip git

# Install uv
pip install uv

# Install Docker (optional, for Docker deployment)
curl -fsSL https://get.docker.com | sh
```

### Step 4: Clone and setup

```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/restaurant-bot.git
cd restaurant-bot

# Create .env
cp .env.example .env
nano .env
# Set: LLM_API_KEY=your-key-here
# Set: SECRET_KEY=a-random-secure-string
# Set: DATABASE_URL=sqlite+aiosqlite:///./restaurant_bot.db

# Install dependencies
uv sync

# Create database and seed
uv run python -m scripts.seed_demo
```

### Step 5: Run with systemd (auto-restart)

```bash
# Create systemd service
cat > /etc/systemd/system/restaurant-bot.service << 'EOF'
[Unit]
Description=Restaurant Bot API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/restaurant-bot
ExecStart=/root/.local/bin/uv run uvicorn src.restaurant_bot.main:app --host 0.0.0.0 --port 8005
Restart=always
RestartSec=5
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable restaurant-bot
systemctl start restaurant-bot

# Check status
systemctl status restaurant-bot

# View logs
journalctl -u restaurant-bot -f
```

### Step 6: Setup Nginx (reverse proxy + SSL)

```bash
apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
cat > /etc/nginx/sites-available/restaurant-bot << 'EOF'
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/restaurant-bot /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Get SSL certificate (after pointing domain to your server IP)
certbot --nginx -d yourdomain.com
```

Your bot is now live at `https://yourdomain.com`

---

## Deploy on Railway

Best for: Zero-config, auto-deploy from GitHub ($5/month)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/restaurant-bot.git
git push -u origin main
```

### Step 2: Deploy on Railway

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your restaurant-bot repo
4. Add environment variables:
   - `LLM_API_KEY` = your Anthropic key
   - `SECRET_KEY` = a random string
   - `PORT` = 8005
5. Railway auto-detects the Dockerfile and deploys

### Step 3: Get your URL

Railway gives you a URL like `restaurant-bot-production.up.railway.app`

---

## Deploy on Render

Best for: Free tier available, easy setup

### Step 1: Push to GitHub (same as above)

### Step 2: Create Web Service on Render

1. Go to https://render.com
2. New → Web Service → Connect GitHub repo
3. Settings:
   - Build Command: `pip install uv && uv sync`
   - Start Command: `uv run uvicorn src.restaurant_bot.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables (same as Railway)
5. Click Deploy

---

## Deploy with Docker

Best for: Consistent environments, easy scaling

### Development (SQLite + In-memory sessions)

```bash
docker build -t restaurant-bot .
docker run -p 8005:8000 --env-file .env restaurant-bot
```

### Production (PostgreSQL + Redis)

```bash
# Start everything
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f app

# Seed data
docker compose -f docker-compose.prod.yml exec app python -m scripts.seed_demo

# Stop
docker compose -f docker-compose.prod.yml down
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | Anthropic API key | `sk-ant-api03-...` |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./restaurant_bot.db` | Database connection string |
| `LLM_PROVIDER` | `anthropic` | LLM provider: anthropic, openai, google |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | Model to use |
| `SECRET_KEY` | Auto-generated | JWT signing key (set a fixed value in production!) |
| `SESSION_STORE` | `memory` | Session backend: memory, redis |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL (if SESSION_STORE=redis) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `DEFAULT_CURRENCY` | `USD` | Default currency for new restaurants |
| `DEFAULT_TIMEZONE` | `UTC` | Default timezone |

### Database URLs by provider

```bash
# SQLite (development)
DATABASE_URL=sqlite+aiosqlite:///./restaurant_bot.db

# PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/restaurant_bot

# MySQL (alternative)
DATABASE_URL=mysql+aiomysql://user:password@host:3306/restaurant_bot
```

---

## Database Setup

### SQLite (Default — Zero Setup)
Just start the app. Database file created automatically.

### PostgreSQL (Recommended for Production)

```bash
# Create database
sudo -u postgres createdb restaurant_bot
sudo -u postgres createuser bot -P  # set password

# Update .env
DATABASE_URL=postgresql+asyncpg://bot:yourpassword@localhost:5432/restaurant_bot

# Start app (tables created automatically on first run)
uv run uvicorn src.restaurant_bot.main:app --port 8005

# Seed data
uv run python -m scripts.seed_demo
```

---

## Domain & SSL

### Get a domain
- **Namecheap** — $8-12/year for .com
- **Cloudflare** — $8.57/year for .com (cheapest)
- **Google Domains** → Squarespace — $12/year

### Point domain to your server
1. In your domain registrar, add an A record:
   - Type: A
   - Name: @ (or your subdomain)
   - Value: your server IP
   - TTL: 300

2. Wait 5-10 minutes for DNS propagation

3. Get SSL with certbot:
```bash
certbot --nginx -d yourdomain.com
```

---

## WhatsApp Setup

### Step 1: Create Meta Business Account
1. Go to https://business.facebook.com
2. Create a business account (free)

### Step 2: Setup WhatsApp Business API
1. Go to https://developers.facebook.com
2. Create an App → Select "Business" type
3. Add WhatsApp product to your app
4. Go to WhatsApp → API Setup
5. Note your:
   - **Phone Number ID**
   - **WhatsApp Business Account ID**
   - **Temporary Access Token** (or generate a permanent one)

### Step 3: Configure Webhook
1. In Meta Dashboard → WhatsApp → Configuration
2. Set Webhook URL: `https://yourdomain.com/api/v1/webhooks/whatsapp`
3. Set Verify Token: any string you choose
4. Subscribe to: `messages`

### Step 4: Enter Credentials in Admin Panel
1. Go to your admin panel → Channels tab
2. Enable WhatsApp toggle
3. Enter Phone Number ID, Business Account ID, Access Token
4. Save

### Step 5: Test
Send a message to your WhatsApp Business number — the bot should reply!

### WhatsApp Pricing (Meta's charges)
- First 1,000 conversations/month: **FREE**
- After that: $0.005 - $0.08 per conversation (varies by country)
- Pakistan: ~$0.014 per conversation
- A "conversation" = 24-hour window of messages with one customer

---

## Cost Breakdown

### Fixed Costs (Monthly)

| Item | Cost | Notes |
|------|------|-------|
| VPS Server | $5-10/month | Hetzner/DigitalOcean |
| Domain | $1/month | ($12/year) |
| SSL | Free | Let's Encrypt via certbot |
| **Total Fixed** | **$6-11/month** | |

### Variable Costs (Per Restaurant)

| Item | Cost | Notes |
|------|------|-------|
| LLM API (Haiku) | $2-5/month | ~1000 AI queries/month per restaurant |
| WhatsApp API | $0-15/month | First 1000 free, then per-conversation |

### Revenue vs Cost Example

| Restaurants | Your Revenue | LLM Cost | Server | Profit |
|-------------|-------------|----------|--------|--------|
| 5 | $195-495/mo | $10-25 | $10 | **$160-460/mo** |
| 20 | $780-1980/mo | $40-100 | $20 | **$660-1860/mo** |
| 50 | $1950-4950/mo | $100-250 | $40 | **$1660-4660/mo** |

### LLM Cost Per $5

| Model | Cost/Query | Queries/$5 | Best For |
|-------|-----------|------------|----------|
| claude-haiku-4-5 | ~$0.003 | **~1,600** | Production (recommended) |
| claude-sonnet-4 | ~$0.015 | **~330** | Better quality responses |
| claude-opus-4 | ~$0.075 | **~65** | Not recommended for bots |

### Cost Optimization Tips

1. **Add more auto-replies** → 40-60% of messages FREE
2. **Add more FAQs** → another 10-20% FREE
3. **Use Haiku model** → cheapest, still very good
4. **Set max_conversation_turns** in config → prevents runaway conversations
5. **Rate limiting** → prevents abuse (already built in)

With good auto-replies + FAQs, expect: **60-70% of messages handled for FREE**

---

## Troubleshooting

### App won't start

```bash
# Check if port is in use
lsof -i :8005
# Kill if needed
kill -9 <PID>

# Check logs
journalctl -u restaurant-bot -f
```

### Database errors

```bash
# Reset database (WARNING: deletes all data)
rm restaurant_bot.db
uv run python -m scripts.seed_demo
```

### LLM errors

```bash
# Test your API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_KEY" \
  -H "content-type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

### WhatsApp not receiving messages

1. Check webhook URL is correct in Meta Dashboard
2. Check your server is publicly accessible (not localhost)
3. Check WhatsApp credentials in admin panel
4. Check server logs for errors

### Rate limited (429 errors)

The bot has built-in rate limiting (60 req/min per IP). If you're testing heavily:
- Wait 1 minute
- Or increase the limit in `middleware/rate_limit.py`

---

## Quick Reference

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/ready` | GET | No | Readiness check (DB connectivity) |
| `/docs` | GET | No | Swagger API docs |
| `/api/v1/auth/register` | POST | No | Register new restaurant |
| `/api/v1/auth/login` | POST | No | Login, get JWT token |
| `/api/v1/restaurants/{id}/chat` | POST | No | Chat with bot |
| `/api/v1/restaurants/{id}/menu` | GET | No | Get full menu |
| `/api/v1/restaurants/{id}/widget-config` | GET | No | Widget config (name, colors, buttons) |
| `/api/v1/restaurants/{id}/config` | GET/PUT/PATCH | Owner | Manage restaurant config |
| `/api/v1/restaurants/{id}/menu/categories` | POST | Staff | Add menu category |
| `/api/v1/restaurants/{id}/menu/items` | POST/PATCH/DELETE | Staff | Manage menu items |
| `/api/v1/restaurants/{id}/orders` | GET | Staff | List orders |
| `/api/v1/restaurants/{id}/orders/{id}/status` | PATCH | Staff | Update order status |
| `/api/v1/restaurants/{id}/reservations` | GET/POST | Staff | Manage reservations |
| `/api/v1/restaurants/{id}/tables` | GET/POST/PATCH/DELETE | Owner | Manage tables |
| `/api/v1/restaurants/{id}/auto-replies` | GET/POST/PATCH/DELETE | Owner | Manage auto-replies |
| `/api/v1/restaurants/{id}/faqs` | GET/POST/PATCH/DELETE | Owner | Manage FAQs |
| `/api/v1/restaurants/{id}/analytics` | GET | Owner | Dashboard analytics |
| `/api/v1/webhooks/whatsapp` | GET/POST | No | WhatsApp webhook |

### Static Pages

| URL | Description |
|-----|-------------|
| `/static/admin.html` | Admin dashboard |
| `/static/chat.html` | Full-page chat |
| `/static/demo.html` | Demo restaurant website with widget |
| `/static/widget.js` | Embeddable chat widget script |

### Makefile Commands

```bash
make install     # Install dependencies
make dev         # Start dev server
make migrate     # Run database migrations
make seed        # Seed demo data
make test        # Run tests
make docker-up   # Start with Docker
```
