import asyncio
import importlib
import json
import os
import smtplib
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import Cookie, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from auth import (
    add_comment,
    create_token,
    delete_comment,
    get_comment_counts,
    get_comments,
    get_deal_like_counts,
    get_user_by_id,
    login_user,
    register_user,
    toggle_like,
    upsert_instagram_user,
    user_liked_deals,
    verify_token,
)
from deals import (
    DEAL_SOURCES,
    detect_category,
    detect_season,
    get_current_season,
    get_top_deals,
    hourly_refresh_loop,
    load_deals,
    refresh_deals,
    save_deals,
)
from products import filter_products, get_all_products
from recommender import get_recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(hourly_refresh_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "detail": exc.detail,
                "path": request.url.path,
                "method": request.method,
                "hint": "On Render, ensure Start Command is: python app.py",
            },
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Instagram OAuth ────────────────────────────────────────────────────────────

IG_APP_ID      = os.environ.get("INSTAGRAM_APP_ID", "")
IG_APP_SECRET  = os.environ.get("INSTAGRAM_APP_SECRET", "")
IG_REDIRECT    = os.environ.get("INSTAGRAM_REDIRECT_URI", "https://www.lifez.ai/auth/instagram/callback")


@app.get("/auth/instagram")
async def instagram_login():
    if not IG_APP_ID:
        return RedirectResponse(url="/?error=instagram_not_configured")
    params = (
        f"client_id={IG_APP_ID}"
        f"&redirect_uri={IG_REDIRECT}"
        f"&scope=instagram_business_basic"
        f"&response_type=code"
        f"&enable_fb_login=0"
        f"&force_authentication=1"
    )
    return RedirectResponse(url=f"https://www.instagram.com/oauth/authorize?{params}")


@app.get("/auth/instagram/callback")
async def instagram_callback(code: str = None, error: str = None):
    if error or not code:
        return RedirectResponse(url="/?error=instagram_denied")
    if not IG_APP_ID or not IG_APP_SECRET:
        return RedirectResponse(url="/?error=instagram_not_configured")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 1. Exchange code → short-lived token
            r1 = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id":     IG_APP_ID,
                    "client_secret": IG_APP_SECRET,
                    "grant_type":    "authorization_code",
                    "redirect_uri":  IG_REDIRECT,
                    "code":          code,
                },
            )
            token_data   = r1.json()
            access_token = token_data.get("access_token")
            ig_user_id   = str(token_data.get("user_id", ""))

            if not access_token:
                return RedirectResponse(url="/?error=instagram_token_failed")

            # 2. Fetch profile
            r2 = await client.get(
                f"https://graph.instagram.com/{ig_user_id}",
                params={
                    "fields":       "id,username,name,profile_picture_url",
                    "access_token": access_token,
                },
            )
            profile = r2.json()

        username = profile.get("username") or f"ig_{ig_user_id}"
        name     = profile.get("name") or username
        pic_url  = profile.get("profile_picture_url", "")

        user  = upsert_instagram_user(ig_user_id, username, name, pic_url)
        token = create_token(user["id"])

        resp = RedirectResponse(url="/")
        resp.set_cookie("session", token, max_age=30 * 24 * 3600, httponly=True, samesite="lax")
        return resp

    except Exception as e:
        print(f"Instagram OAuth error: {e}")
        return RedirectResponse(url="/?error=instagram_error")


@app.get("/api/auth/instagram/status")
async def instagram_status():
    """Let the frontend know whether Instagram login is configured."""
    return JSONResponse({"configured": bool(IG_APP_ID and IG_APP_SECRET)})


# ── Auth helper ────────────────────────────────────────────────────────────────

def current_user(session: str = None):
    if not session:
        return None
    uid = verify_token(session)
    return get_user_by_id(uid) if uid else None


# ── Auth endpoints ──────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def auth_register(request: Request):
    p = await request.json()
    try:
        user  = register_user(p.get("username",""), p.get("display_name",""), p.get("password",""))
        token = create_token(user["id"])
        resp  = JSONResponse({"success": True, "user": user})
        resp.set_cookie("session", token, max_age=30*24*3600, httponly=True, samesite="lax")
        return resp
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/api/auth/login")
async def auth_login(request: Request):
    p    = await request.json()
    user = login_user(p.get("username",""), p.get("password",""))
    if not user:
        return JSONResponse(status_code=401, content={"error": "Invalid username or password"})
    token = create_token(user["id"])
    resp  = JSONResponse({"success": True, "user": user})
    resp.set_cookie("session", token, max_age=30*24*3600, httponly=True, samesite="lax")
    return resp


@app.post("/api/auth/logout")
async def auth_logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie("session")
    return resp


@app.get("/api/auth/me")
async def auth_me(session: str = Cookie(default=None)):
    user = current_user(session)
    if not user:
        return JSONResponse({"user": None})
    liked = user_liked_deals(user["id"])
    return JSONResponse({"user": user, "liked_deals": list(liked)})


# ── Deal endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/deals")
async def get_deals(category: str = "all", season: str = "all", limit: int = 10,
                    session: str = Cookie(default=None)):
    result    = get_top_deals(category=category, season=season, limit=limit)
    user      = current_user(session)
    liked_set = user_liked_deals(user["id"]) if user else set()
    counts    = get_deal_like_counts()
    cc        = get_comment_counts()

    for d in result["deals"]:
        sid          = str(d["id"])
        d["likes"]   = counts.get(sid, 0) + d.get("votes", 0)
        d["comments"]= cc.get(sid, 0)
        d["user_liked"] = sid in liked_set
    return JSONResponse(content=result)


@app.post("/api/deals/submit")
async def submit_deal(request: Request):
    payload = await request.json()
    title = payload.get("title", "").strip()
    link = payload.get("link", "").strip()

    if not title or not link:
        return JSONResponse(status_code=400, content={"error": "Title and link are required"})

    deal = {
        "id": abs(hash(link + title)) % (10 ** 9),
        "title": title,
        "link": link,
        "description": payload.get("description", "")[:250],
        "category": payload.get("category") or detect_category(title, ""),
        "season": detect_season(title, "") or get_current_season(),
        "source": "Community",
        "source_icon": "👤",
        "source_color": "#06b6d4",
        "fetched_at": int(time.time()),
        "is_user_submitted": True,
        "votes": 0,
    }

    data = load_deals()
    data.setdefault("user_deals", []).insert(0, deal)
    save_deals(data)
    return JSONResponse({"success": True, "deal": deal})


@app.post("/api/deals/vote/{deal_id}")
async def vote_deal(deal_id: int, session: str = Cookie(default=None)):
    user = current_user(session)

    if user:
        # Logged-in: toggle like in user record
        is_liked = toggle_like(user["id"], deal_id)
        counts   = get_deal_like_counts()
        data     = load_deals()
        votes    = 0
        for lk in ["deals", "user_deals"]:
            for d in data.get(lk, []):
                if d["id"] == deal_id:
                    votes = d.get("votes", 0)
        total = counts.get(str(deal_id), 0) + votes
        return JSONResponse({"success": True, "liked": is_liked, "likes": total})
    else:
        # Anonymous: increment raw votes
        data = load_deals()
        for lk in ["deals", "user_deals"]:
            for d in data.get(lk, []):
                if d["id"] == deal_id:
                    d["votes"] = d.get("votes", 0) + 1
                    save_deals(data)
                    return JSONResponse({"success": True, "liked": True, "likes": d["votes"]})
    return JSONResponse(status_code=404, content={"error": "Deal not found"})


# ── Comment endpoints ──────────────────────────────────────────────────────────

@app.get("/api/deals/{deal_id}/comments")
async def get_deal_comments(deal_id: int):
    return JSONResponse({"comments": get_comments(deal_id)})


@app.post("/api/deals/{deal_id}/comments")
async def post_comment(deal_id: int, request: Request, session: str = Cookie(default=None)):
    user = current_user(session)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required to comment"})
    p = await request.json()
    try:
        comment = add_comment(deal_id, user, p.get("text", ""))
        return JSONResponse({"success": True, "comment": comment})
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.delete("/api/deals/{deal_id}/comments/{comment_id}")
async def del_comment(deal_id: int, comment_id: str, session: str = Cookie(default=None)):
    user = current_user(session)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required"})
    if delete_comment(deal_id, comment_id, user["id"]):
        return JSONResponse({"success": True})
    return JSONResponse(status_code=404, content={"error": "Comment not found"})


@app.post("/api/deals/refresh")
async def manual_refresh():
    count = await refresh_deals()
    return JSONResponse({"success": True, "count": count})


# ── Existing endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Image / Reel generation ───────────────────────────────────────────────────

@app.get("/api/deals/{deal_id}/card")
async def deal_post_card(deal_id: int):
    """1080×1080 Instagram post image for a deal."""
    from reel_gen import post_card
    data = load_deals()
    deal = next((d for d in data.get("deals", []) + data.get("user_deals", []) if d["id"] == deal_id), None)
    if not deal:
        return JSONResponse(status_code=404, content={"error": "Deal not found"})
    img_bytes = await asyncio.to_thread(post_card, deal)
    return Response(content=img_bytes, media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="lifezai-deal-{deal_id}.png"'})


@app.get("/api/deals/{deal_id}/story")
async def deal_story_card(deal_id: int):
    """1080×1920 Instagram Story / Reel cover image for a deal."""
    from reel_gen import story_card
    data = load_deals()
    deal = next((d for d in data.get("deals", []) + data.get("user_deals", []) if d["id"] == deal_id), None)
    if not deal:
        return JSONResponse(status_code=404, content={"error": "Deal not found"})
    img_bytes = await asyncio.to_thread(story_card, deal)
    return Response(content=img_bytes, media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="lifezai-story-{deal_id}.png"'})


@app.get("/api/deals/top/story")
async def top_deals_story_card():
    """1080×1920 daily top-5 deals story card."""
    from reel_gen import top_deals_story
    result = get_top_deals(limit=5)
    img_bytes = await asyncio.to_thread(top_deals_story, result["deals"])
    return Response(content=img_bytes, media_type="image/png",
                    headers={"Content-Disposition": 'attachment; filename="lifezai-top-deals.png"'})


# ── Suggestions ───────────────────────────────────────────────────────────────

def _send_suggestion_email(name: str, email: str, message: str):
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_addr   = "rapot2018@gmail.com"

    if not smtp_user or not smtp_pass:
        print(f"[suggestion] Email not configured — suggestion from {name or 'anon'}: {message[:80]}")
        return

    msg = MIMEMultipart("alternative")
    msg["From"]    = smtp_user
    msg["To"]      = to_addr
    msg["Subject"] = f"💡 New lifez.ai suggestion from {name or 'Anonymous'}"

    body = (
        f"New suggestion on lifez.ai\n\n"
        f"From:    {name or 'Anonymous'}\n"
        f"Email:   {email or 'Not provided'}\n\n"
        f"Message:\n{message}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr, msg.as_string())


@app.post("/api/suggest")
async def suggest(request: Request):
    payload = await request.json()
    message = payload.get("message", "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "Message is required"})

    name  = payload.get("name", "").strip()
    email = payload.get("email", "").strip()

    try:
        await asyncio.to_thread(_send_suggestion_email, name, email, message)
    except Exception as e:
        print(f"[suggestion] Email send failed: {e}")

    return JSONResponse({"success": True})


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html", media_type="text/html")


def run_groq_query(query: str):
    try:
        spec = importlib.import_module("groqtest")
        for name in ("get_response", "run", "main"):
            fn = getattr(spec, name, None)
            if callable(fn):
                try:
                    return fn(query)
                except TypeError:
                    return fn()
    except Exception:
        pass

    try:
        env = os.environ.copy()
        env["GROQ_QUERY"] = query
        proc = subprocess.run(
            [sys.executable, "groqtest.py"],
            capture_output=True, text=True, env=env, cwd=os.getcwd(),
        )
        if proc.returncode == 0:
            out = proc.stdout.strip()
            try:
                return json.loads(out)
            except Exception:
                return out
        return {"error": proc.stderr.strip()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/groq")
async def groq_api(request: Request):
    payload = await request.json()
    query = payload.get("query", "")
    result = run_groq_query(query)
    return JSONResponse(content={"query": query, "result": result})


@app.get("/api/recommend")
@app.get("/api/recommend/")
async def recommend_get():
    return JSONResponse(
        status_code=405,
        content={"detail": "Method Not Allowed", "message": 'Use POST with JSON body: {"requirement": "your search"}'},
    )


async def _recommend_handler(request: Request):
    try:
        payload = await request.json()
        requirement = payload.get("requirement", "")
        if not requirement:
            return JSONResponse(status_code=400, content={"error": "Requirement is required"})
        result = get_recommendations(requirement)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/recommend")
@app.post("/api/recommend/")
@app.post("/recommend")
@app.post("/recommend/")
async def get_product_recommendations(request: Request):
    return await _recommend_handler(request)


@app.get("/api/products")
async def get_products():
    return JSONResponse(content={"products": get_all_products()})


@app.post("/api/products/filter")
async def filter_product_list(request: Request):
    try:
        payload = await request.json()
        filters = payload.get("filters", {})
        results = filter_products(filters)
        return JSONResponse(content={"products": results, "count": len(results)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api")
@app.get("/api/")
async def api_info():
    return {
        "message": "Lifez.AI API",
        "endpoints": {
            "GET /": "Landing page (HTML)",
            "GET /health": "Health check",
            "GET /api/deals": "Top 10 deals (params: category, season)",
            "POST /api/deals/submit": "Submit a deal",
            "POST /api/deals/vote/{id}": "Vote for a deal",
            "POST /api/deals/refresh": "Force refresh deals",
            "POST /api/recommend": 'Product recommendations (body: {"requirement": "..."})',
            "GET /api/products": "List all products",
            "POST /api/products/filter": "Filter products",
        },
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    reload = not os.environ.get("PORT")
    uvicorn.run("app:app", host=host, port=port, reload=reload)
