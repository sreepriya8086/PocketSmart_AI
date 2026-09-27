# PocketSmart AI — Full Working Version

PocketSmart AI is a FastAPI web application for budget planning.

## Included
- Home interior planner
- Party/event planner
- Jewelry planner
- Optional outfit image upload for jewelry planning
- Gemini AI integration
- Local fallback planner when Gemini is not configured
- Registration and login
- Secure PBKDF2 password hashing
- SQLite database
- Personal recommendation history
- Delete history
- Dashboard
- JSON API
- Responsive dark UI
- Budget enforcement on AI output
- No fake live prices or availability claims

## Windows installation

Open PowerShell in this project folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## Gemini setup

Copy `.env.example` to `.env`.

Set:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
SECRET_KEY=your-long-random-secret
```

The application still works without a Gemini key using the built-in fallback engine.

## Run

```powershell
python -m uvicorn main:app --reload
```

Open:

http://127.0.0.1:8000

## API

Health:

```text
GET /api/health
```

Generate a home plan:

```text
POST /api/generate/home
Content-Type: application/json
```

Example:

```json
{
  "budget": 50000,
  "room": "Living Room",
  "style": "Modern",
  "items": "sofa, lights, table"
}
```

## Production notes

Use HTTPS, a strong SECRET_KEY, a production database, rate limiting, CSRF protection for public deployments, and authorized retailer/affiliate APIs if you later add real product prices or purchase links.
