# PocketSmart AI

A FastAPI + Gemini budget recommendation assistant based on the supplied project specification.

## 1. Setup
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure Gemini
Copy `.env.example` to `.env` and set `GEMINI_API_KEY`. The app works without the key using deterministic fallback recommendations.

## 3. Run
```bash
uvicorn main:app --reload
```
Open http://127.0.0.1:8000

## Features
- Home, Party, and Jewelry planners
- Budget-aware allocation
- Optional jewelry image upload
- Gemini integration when API key is present
- SQLite registration/login
- Recommendation history
- Responsive HTML/CSS UI

## Important
The project uses estimated recommendations. It does not scrape or claim live product prices/availability. Real Amazon/Flipkart/IKEA/Swiggy/Zomato/OYO integrations should be added only through authorized APIs/affiliate feeds or other permitted data sources.
