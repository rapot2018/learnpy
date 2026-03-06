from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess
import sys
import json
import importlib
import os

app = FastAPI()

templates = Jinja2Templates(directory="templates")


def run_groq_query(query: str):
    # Try to call groqtest as a module with a helper function if available
    try:
        spec = importlib.import_module("groqtest")
        # prefer common helper names
        for name in ("get_response", "run", "main"):
            fn = getattr(spec, name, None)
            if callable(fn):
                try:
                    return fn(query)
                except TypeError:
                    # try without args
                    return fn()
    except Exception:
        pass

    # Fallback: run the script and capture stdout
    try:
        env = os.environ.copy()
        env["GROQ_QUERY"] = query
        proc = subprocess.run([sys.executable, "groqtest.py"], capture_output=True, text=True, env=env, cwd=os.getcwd())
        if proc.returncode == 0:
            # try parse JSON, else return raw
            out = proc.stdout.strip()
            try:
                return json.loads(out)
            except Exception:
                return out
        else:
            return {"error": proc.stderr.strip()}
    except Exception as e:
        return {"error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/groq")
async def groq_api(request: Request):
    payload = await request.json()
    query = payload.get("query", "")
    result = run_groq_query(query)
    return JSONResponse(content={"query": query, "result": result})


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
