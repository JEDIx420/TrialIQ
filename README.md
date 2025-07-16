# TrialIQ: Multilingual Clinical Trial Eligibility MVP

## Overview
TrialIQ is a multilingual, voice-enabled clinical trial matching platform. It collects patient data via adaptive forms (text/voice), detects locale, applies region-specific rules, and recommends eligible trials. Includes a simple admin dashboard for analytics.

## Features
- Adaptive, decision-based form (text/voice, multilingual)
- Locale detection (language + country)
- Region-specific translations, units, and privacy
- Canonical response schema with ISO locale codes
- Rule-based, geo-aware trial scoring
- Ranked trial recommendations with match % and local site info
- Submission persistence for analytics
- Admin dashboard for monitoring and KPIs

## Tech Stack
- Python 3.9+
- FastAPI (API backend)
- Streamlit (UI/UX)
- SQLAlchemy (in-memory SQLite for MVP)
- Babel (i18n)
- Requests (for AI/translation APIs)
- Pydantic, Pandas, Geopy, Plotly

## Setup
1. **Clone repo & install dependencies:**
   ```bash
   pip install fastapi streamlit sqlalchemy pydantic pandas babel requests geopy uvicorn plotly
   ```
2. **Set environment variables:**
   - `DB_URL` (optional, defaults to in-memory SQLite)
   - `STT_API_KEY`, `TTS_API_KEY` (for voice features, optional in MVP)
   - `ADMIN_BEARER_SECRET` (for admin access)
   - `DEFAULT_LOCALE` (e.g., en-US)
   - `AI_API_KEY` (use the provided key)

3. **Run the app:**
   ```bash
   streamlit run trialiq.py
   ```

## Usage
- Users answer questions (text/voice) in their language.
- Get instant, region-appropriate trial matches.
- Admins can view submissions and KPIs via the dashboard.

## Notes
- This MVP uses in-memory DB and mock trial data.
- Voice features require valid API keys and internet.
- For production, connect to Hive/Impala and secure all endpoints.

---
**Hackathon MVP by Team TrialIQ, July 2025**
