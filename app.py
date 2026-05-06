import asyncio
import importlib
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

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

templates = Jinja2Templates(directory="templates")


# ── Deal endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/deals")
async def get_deals(category: str = "all", season: str = "all", limit: int = 10):
    result = get_top_deals(category=category, season=season, limit=limit)
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
async def vote_deal(deal_id: int):
    data = load_deals()
    for list_key in ["deals", "user_deals"]:
        for deal in data.get(list_key, []):
            if deal["id"] == deal_id:
                deal["votes"] = deal.get("votes", 0) + 1
                save_deals(data)
                return JSONResponse({"success": True, "votes": deal["votes"]})
    return JSONResponse(status_code=404, content={"error": "Deal not found"})


@app.post("/api/deals/refresh")
async def manual_refresh():
    count = await refresh_deals()
    return JSONResponse({"success": True, "count": count})


# ── Existing endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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
