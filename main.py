from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
import os, sqlite3, json, secrets, hashlib, hmac, base64, re

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pocketsmart.db"

app = FastAPI(title="PocketSmart AI", version="2.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-this-secret-key"),
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------
# Database
# ---------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        planner TEXT NOT NULL,
        input_json TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------------------
# Password hashing
# ---------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return "pbkdf2_sha256$310000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ---------------------------
# Helpers
# ---------------------------
ALLOWED_PLANNERS = {"home", "party", "jewelry"}


def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    user = conn.execute("SELECT id, email, created_at FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def clean_budget(value) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("Budget must be a valid number.")
    if amount <= 0 or amount > 100_000_000:
        raise ValueError("Budget must be between ₹1 and ₹10 crore.")
    return round(amount, 2)


def parse_payload(data: str, budget: str):
    try:
        payload = json.loads(data or "{}")
        if not isinstance(payload, dict):
            raise ValueError
    except Exception:
        raise ValueError("Invalid planner data.")
    payload["budget"] = clean_budget(budget)
    return payload


def money(value):
    return f"₹{float(value):,.0f}"


def save_history(request: Request, planner: str, payload: dict, result: dict):
    uid = request.session.get("user_id")
    if not uid:
        return
    conn = get_db()
    conn.execute(
        "INSERT INTO history(user_id, planner, input_json, result_json) VALUES(?,?,?,?)",
        (uid, planner, json.dumps(payload), json.dumps(result))
    )
    conn.commit()
    conn.close()


# ---------------------------
# Deterministic AI fallback
# ---------------------------
def fallback_plan(planner: str, data: dict) -> dict:
    budget = float(data["budget"])

    if planner == "home":
        room = data.get("room", "room")
        style = data.get("style", "modern")
        items = data.get("items", "")
        allocations = [
            ("Furniture", 0.40, f"Choose practical {style} furniture for the {room}."),
            ("Lighting", 0.15, "Use layered LED lighting: ceiling, task and accent lights."),
            ("Storage", 0.20, "Prioritize modular storage that fits the room dimensions."),
            ("Decor", 0.15, "Add curtains, rugs, wall decor and a few plants without overcrowding."),
            ("Contingency", 0.10, "Keep this amount for delivery, installation and unexpected costs."),
        ]
        note = f"Starter {style} plan for a {room}."
        if items:
            note += f" Requested items: {items}."
    elif planner == "party":
        guests = int(float(data.get("guests", 0) or 0))
        event = data.get("event", "party")
        venue = data.get("venue", "flexible")
        allocations = [
            ("Food & beverages", 0.45, f"Plan food portions for about {guests} guests."),
            ("Venue", 0.20, f"Compare venues matching the {venue} preference."),
            ("Decoration", 0.12, "Use a focused theme with reusable decoration where possible."),
            ("Entertainment", 0.10, "Reserve a small amount for music, games or a host."),
            ("Photography", 0.05, "Use a basic photo/video package or a designated photographer."),
            ("Contingency", 0.08, "Keep a buffer for last-minute purchases."),
        ]
        note = f"Starter {event} plan for approximately {guests} guests."
    else:
        occasion = data.get("occasion", "special occasion")
        style = data.get("style", "classic")
        allocations = [
            ("Main jewelry", 0.70, f"Look for {style} pieces appropriate for the {occasion}."),
            ("Matching accessory", 0.15, "Consider earrings, bracelet or a complementary accessory."),
            ("Care & storage", 0.05, "Reserve a small amount for storage/care accessories."),
            ("Contingency", 0.10, "Keep a buffer for taxes, making charges or price changes."),
        ]
        note = f"Starter {style} jewelry plan for a {occasion}."

    recommendations = []
    for category, ratio, suggestion in allocations:
        amount = round(budget * ratio, 2)
        recommendations.append({
            "category": category,
            "suggestion": suggestion,
            "estimated_budget": amount,
            "platforms": ["Compare local sellers", "Amazon", "Flipkart"]
        })

    return {
        "planner": planner,
        "budget": budget,
        "summary": note + " Estimates are planning allocations, not live prices.",
        "recommendations": recommendations,
        "tips": [
            "Compare at least 2–3 sellers before buying.",
            "Keep receipts and check warranty/return conditions.",
            "Do not treat estimated prices as live availability or quotations."
        ],
        "source": "fallback"
    }


def call_gemini(planner: str, data: dict, image_bytes: Optional[bytes] = None, image_type: str = "image/jpeg"):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return fallback_plan(planner, data)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        budget = float(data["budget"])

        system_prompt = f"""
You are PocketSmart AI, a practical budget planning assistant.
Planner: {planner}
User input: {json.dumps(data, ensure_ascii=False)}

Create a realistic planning proposal. The user's total budget is INR {budget:.2f}.
Rules:
1. Return ONLY valid JSON. No markdown and no code fences.
2. Use exactly these top-level keys:
   summary, recommendations, tips
3. recommendations is an array. Each item must contain:
   category, suggestion, estimated_budget, platforms
4. Sum of estimated_budget must be <= the user's budget.
5. Do not claim live prices, inventory, delivery dates or availability.
6. Treat all amounts as estimates.
7. Never invent a direct purchase link.
8. If an uploaded image is present, use it only as visual context for the jewelry/outfit plan.
9. Give useful, concrete suggestions rather than generic motivational text.
"""

        contents = [system_prompt]
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_type))

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=contents,
        )

        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        if not isinstance(result.get("recommendations"), list):
            raise ValueError("Gemini returned invalid recommendations.")

        total = 0.0
        safe_recs = []
        for item in result["recommendations"]:
            amount = max(0.0, float(item.get("estimated_budget", 0)))
            total += amount
            safe_recs.append({
                "category": str(item.get("category", "Recommendation")),
                "suggestion": str(item.get("suggestion", "")),
                "estimated_budget": round(amount, 2),
                "platforms": item.get("platforms", []) if isinstance(item.get("platforms", []), list) else []
            })

        # Enforce budget even if the model makes a mistake.
        if total > budget and total > 0:
            factor = budget / total
            for item in safe_recs:
                item["estimated_budget"] = round(item["estimated_budget"] * factor, 2)

        return {
            "planner": planner,
            "budget": budget,
            "summary": str(result.get("summary", "AI plan generated.")),
            "recommendations": safe_recs,
            "tips": result.get("tips", []),
            "source": "gemini"
        }

    except Exception as exc:
        result = fallback_plan(planner, data)
        result["ai_note"] = f"Gemini was unavailable, so a local fallback plan was used."
        return result


# ---------------------------
# Pages
# ---------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": current_user(request)
    })


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": current_user(request), "error": None})


@app.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request, "user": None, "error": "Password must contain at least 6 characters."
        })
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return templates.TemplateResponse("register.html", {
            "request": request, "user": None, "error": "Enter a valid email address."
        })

    conn = get_db()
    try:
        conn.execute("INSERT INTO users(email,password_hash) VALUES(?,?)", (email, hash_password(password)))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": request, "user": None, "error": "Email is already registered."
        })
    conn.close()
    return RedirectResponse("/login?registered=1", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    registered = request.query_params.get("registered") == "1"
    return templates.TemplateResponse("login.html", {
        "request": request, "user": current_user(request), "error": None,
        "registered": registered
    })


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {
            "request": request, "user": None, "error": "Invalid email or password.", "registered": False
        })

    request.session.clear()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 8",
        (user["id"],)
    ).fetchall()
    count = conn.execute("SELECT COUNT(*) AS c FROM history WHERE user_id=?", (user["id"],)).fetchone()["c"]
    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "history": rows, "plan_count": count
    })


@app.get("/planner/{planner}", response_class=HTMLResponse)
def planner_page(request: Request, planner: str):
    if planner not in ALLOWED_PLANNERS:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(f"{planner}_planner.html", {
        "request": request, "user": current_user(request)
    })


@app.post("/generate/{planner}", response_class=HTMLResponse)
async def generate(
    request: Request,
    planner: str,
    budget: str = Form(...),
    data: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    if planner not in ALLOWED_PLANNERS:
        raise HTTPException(status_code=404, detail="Planner not found")

    try:
        payload = parse_payload(data, budget)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    image_bytes = None
    image_type = "image/jpeg"

    if image and image.filename:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed.")
        image_bytes = await image.read()
        if len(image_bytes) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image must be smaller than 8 MB.")
        image_type = image.content_type

    result = call_gemini(planner, payload, image_bytes, image_type)
    save_history(request, planner, payload, result)

    return templates.TemplateResponse("results.html", {
        "request": request, "user": current_user(request), "result": result
    })


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC",
        (user["id"],)
    ).fetchall()
    conn.close()

    return templates.TemplateResponse("history.html", {
        "request": request, "user": user, "history": rows
    })


@app.post("/history/{history_id}/delete")
def delete_history(request: Request, history_id: int):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    conn.execute("DELETE FROM history WHERE id=? AND user_id=?", (history_id, user["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse("/history", status_code=303)


# ---------------------------
# JSON API
# ---------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "PocketSmart AI", "version": "2.0.0"}


@app.post("/api/generate/{planner}")
async def api_generate(planner: str, payload: dict):
    if planner not in ALLOWED_PLANNERS:
        raise HTTPException(status_code=404, detail="Planner not found")
    if "budget" not in payload:
        raise HTTPException(status_code=400, detail="budget is required")
    try:
        payload["budget"] = clean_budget(payload["budget"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse(call_gemini(planner, payload))
