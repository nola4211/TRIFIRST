# 🏊🚴🏃 TriFirst — Your First Ironman, Simplified

A free, beginner-friendly AI training companion for people training for their first triathlon or Ironman. Connects to Strava, stores your training data, and gives you a personal AI coach (Coach Tri) that knows your actual workout history.

---

## 🗂 Project Structure

```
TRIFIRST/
├── .env                          # Your secret keys (never commit this)
├── .env.example                  # Template for .env
├── trifirst.db                   # SQLite database (auto-created on first run)
└── trifirst/
    ├── main.py                   # FastAPI app entry point
    ├── config.py                 # Loads environment variables
    ├── app.py                    # Streamlit UI
    ├── database/
    │   ├── db.py                 # SQLite connection + init_db()
    │   └── schema.sql            # All 8 database tables
    ├── integrations/
    │   ├── strava.py             # Strava OAuth + activity sync
    │   └── garmin.py             # Garmin placeholder (not yet built)
    ├── coach/
    │   └── ai_coach.py           # Coach Tri — Groq/Llama AI coach
    └── api/
        └── routes.py             # All FastAPI endpoints
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root `TRIFIRST/` folder with these values:

```
APP_NAME=TriFirst
ENV=development
DATABASE_PATH=trifirst.db
STRAVA_CLIENT_ID=your_strava_client_id
STRAVA_CLIENT_SECRET=your_strava_client_secret
GROQ_API_KEY=your_groq_api_key
```

| Variable | Where to get it |
|---|---|
| `STRAVA_CLIENT_ID` | [strava.com/settings/api](https://www.strava.com/settings/api) |
| `STRAVA_CLIENT_SECRET` | Same page as above |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys |

---

## 🚀 How to Run the App

You need **two terminal windows** running at the same time.

### Terminal 1 — Start the FastAPI backend:
```bash
cd TRIFIRST
python -m trifirst.main
```
Backend runs at: `http://localhost:8000`
Interactive API docs at: `http://localhost:8000/docs`

### Terminal 2 — Start the Streamlit UI:
```bash
cd TRIFIRST
streamlit run trifirst/app.py
```
UI opens automatically in your browser at: `http://localhost:8501`

---

## 📦 Install Dependencies

Run this once after cloning or pulling new changes:

```bash
pip install -r trifirst/requirements.txt
```

Current dependencies: `fastapi`, `uvicorn`, `python-dotenv`, `requests`, `httpx`, `groq`, `streamlit`, `plotly`

---

## 🔌 API Endpoints

All endpoints are testable at `http://localhost:8000/docs`

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/health` | Check server is running |
| GET | `/auth/strava` | Start Strava OAuth flow |
| GET | `/auth/strava/callback` | Strava redirects here after auth |
| POST | `/sync/strava` | Pull activities from Strava |
| GET | `/activities/{user_id}` | Get all activities for a user |
| POST | `/checkin` | Save a daily check-in |
| POST | `/coach/chat` | Chat with Coach Tri |

### Example: Sync Strava activities
```bash
curl -X POST http://localhost:8000/sync/strava \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

### Example: Chat with Coach Tri
```bash
curl -X POST http://localhost:8000/coach/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "message": "What should I focus on this week?"}'
```

---

## 🗄 Database Tables

The SQLite database (`trifirst.db`) has 8 tables:

| Table | What it stores |
|---|---|
| `users` | User profile (name, email, age) |
| `race_goals` | Target race name, date, distance |
| `fitness_background` | Swim/bike/run levels, weekly hours |
| `activities` | Every synced workout from Strava |
| `strava_tokens` | OAuth tokens for Strava API |
| `daily_checkins` | Sleep, energy, soreness, stress scores |
| `weekly_summaries` | AI-generated weekly training summaries |
| `coach_messages` | Full conversation history with Coach Tri |

---

## 🔄 Connecting Strava (First Time Setup)

1. Make sure your `.env` has `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`
2. Start the FastAPI backend (Terminal 1)
3. Open this URL in your browser:
```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&approval_prompt=force&scope=activity:read_all&redirect_uri=http://localhost:8000/auth/strava/callback
```
4. Authorize TriFirst on Strava
5. You'll see `{"message":"Strava connected successfully","user_id":1}`
6. Go to `/docs` and run `POST /sync/strava` with `{"user_id": 1}`

---

## 🤖 Current AI Model

Coach Tri runs on **Llama 3.3 70B** via Groq.
Model string: `llama-3.3-70b-versatile`

If Groq changes or deprecates the model, update this line in `trifirst/coach/ai_coach.py`:
```python
completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
```
Check current models at: [console.groq.com/docs/models](https://console.groq.com/docs/models)

---

## 🧠 AI Prompt — Resume This Project

Copy and paste this into any AI assistant (Claude, ChatGPT, Codex) to instantly get it up to speed:

```
I am building a Python app called TriFirst — a free, beginner-friendly 
AI triathlon training companion. Here is the current state of the project:

TECH STACK:
- Backend: FastAPI + SQLite (via trifirst/main.py)
- Frontend: Streamlit (trifirst/app.py)
- AI Coach: Groq API with llama-3.3-70b-versatile model
- Data: Strava API OAuth2 integration
- Language: Python, running on Mac with Miniconda (Python 3.13)

PROJECT STRUCTURE:
trifirst/
  main.py         — FastAPI app, runs on port 8000
  config.py       — loads .env vars (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, GROQ_API_KEY)
  app.py          — Streamlit dashboard + Coach Tri chat UI
  database/
    db.py         — SQLite helpers, init_db(), get_connection()
    schema.sql    — 8 tables: users, race_goals, fitness_background, 
                    activities, strava_tokens, daily_checkins, 
                    weekly_summaries, coach_messages
  integrations/
    strava.py     — full OAuth2 + activity sync (swim/bike/run only)
    garmin.py     — placeholder, not yet implemented
  coach/
    ai_coach.py   — build_user_context() + chat() using Groq
  api/
    routes.py     — endpoints: /health, /auth/strava, /auth/strava/callback,
                    /sync/strava, /activities/{user_id}, /checkin, /coach/chat

CURRENT STATE:
- Backend and Streamlit UI are fully working
- Strava OAuth connected, 20 real activities synced for user_id=1
- Coach Tri AI coach is working with real training data
- Daily check-in via sidebar is working
- user_id is hardcoded to 1 (no auth system yet)

TO RUN:
- Terminal 1: python -m trifirst.main  (FastAPI on port 8000)
- Terminal 2: streamlit run trifirst/app.py  (UI on port 8501)

WHAT IS NOT YET BUILT:
- Race goal setup / onboarding form
- Fitness background form  
- Weekly AI digest / summary generation
- Real user authentication
- Garmin integration

The app is built for beginner triathletes training for their first 
Ironman. The target user is someone who just signed up and doesn't 
know where to start. Keep everything simple, beginner-friendly, and free.
```

---

## ✅ What's Built vs What's Next

```
✅ Project structure + database schema
✅ Strava OAuth + automatic activity sync  
✅ FastAPI backend with all core endpoints
✅ Coach Tri — AI coach with real training context
✅ Streamlit dashboard with stats, charts, and chat
✅ Daily check-in (sidebar)

⬜ Race goal onboarding form
⬜ Fitness background form
⬜ Weekly AI digest
⬜ Garmin integration
⬜ User authentication
```

---

## 🐛 Common Issues

**`ModuleNotFoundError: No module named 'config'`**
Run from the repo root using `python -m trifirst.main` not `python trifirst/main.py`

**`GROQ_API_KEY` or `STRAVA_CLIENT_ID` is empty**
Check your `.env` file is in the root `TRIFIRST/` folder (not inside `trifirst/`)

**Strava sync returns 0 activities**
Make sure you're sending `user_id: 1` not `user_id: 0` in the request body

**Groq model error (decommissioned)**
Update model string in `ai_coach.py` — check [console.groq.com/docs/models](https://console.groq.com/docs/models)
