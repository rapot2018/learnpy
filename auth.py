"""
User auth, sessions, per-user likes, and comments.
No extra dependencies — uses stdlib hashlib + hmac for everything.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

USERS_FILE    = Path("users.json")
COMMENTS_FILE = Path("comments.json")
SECRET_KEY    = os.environ.get("SECRET_KEY", "lifezai-secret-change-in-prod")

AVATARS = ["🦁","🐯","🦊","🐺","🦋","🌟","🔥","⚡","🎯","🎪","🦄","🐬","🎸","🏄","🧑‍💻"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_pw(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return dk.hex(), salt


def _verify_pw(password: str, hashed: str, salt: str) -> bool:
    dk, _ = _hash_pw(password, salt)
    return hmac.compare_digest(dk, hashed)


def _load(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, default=str))


def load_users() -> dict:
    return _load(USERS_FILE, {"users": {}})


def load_comments() -> dict:
    return _load(COMMENTS_FILE, {"comments": {}})


def _public(user: dict) -> dict:
    return {
        "id":                  user["id"],
        "username":            user["username"],
        "display_name":        user["display_name"],
        "avatar":              user.get("avatar", "👤"),
        "profile_picture_url": user.get("profile_picture_url", ""),
        "is_instagram":        user.get("is_instagram", False),
    }


# ── Session tokens (signed, no JWT lib) ───────────────────────────────────────

def create_token(user_id: str) -> str:
    ts      = str(int(time.time()))
    payload = f"{user_id}:{ts}"
    sig     = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_token(token: str, max_age: int = 30 * 24 * 3600) -> Optional[str]:
    try:
        user_id, ts, sig = token.rsplit(":", 2)
        payload  = f"{user_id}:{ts}"
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts) > max_age:
            return None
        return user_id
    except Exception:
        return None


# ── Users ─────────────────────────────────────────────────────────────────────

def register_user(username: str, display_name: str, password: str) -> dict:
    username = username.lower().strip()
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if not username.replace("_", "").replace(".", "").isalnum():
        raise ValueError("Username can only contain letters, numbers, _ and .")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    data = load_users()
    if username in data["users"]:
        raise ValueError("Username already taken — try another")

    hashed, salt = _hash_pw(password)
    user = {
        "id":           secrets.token_hex(8),
        "username":     username,
        "display_name": display_name.strip() or username,
        "avatar":       AVATARS[len(data["users"]) % len(AVATARS)],
        "hashed":       hashed,
        "salt":         salt,
        "created_at":   datetime.now().isoformat(),
        "liked_deals":  [],
    }
    data["users"][username] = user
    _save(USERS_FILE, data)
    return _public(user)


def login_user(username: str, password: str) -> Optional[dict]:
    username = username.lower().strip()
    data     = load_users()
    user     = data["users"].get(username)
    if not user or not _verify_pw(password, user["hashed"], user["salt"]):
        return None
    return _public(user)


def get_user_by_id(user_id: str) -> Optional[dict]:
    for user in load_users()["users"].values():
        if user["id"] == user_id:
            return _public(user)
    return None


def upsert_instagram_user(ig_id: str, username: str, name: str, pic_url: str) -> dict:
    """Create or update a user authenticated via Instagram OAuth."""
    data = load_users()
    # Find existing account with this Instagram ID
    for key, u in data["users"].items():
        if u.get("instagram_id") == ig_id:
            u["display_name"]        = name
            u["profile_picture_url"] = pic_url
            _save(USERS_FILE, data)
            return _public(u)
    # New Instagram user
    user = {
        "id":                  secrets.token_hex(8),
        "username":            username.lower(),
        "display_name":        name or username,
        "avatar":              "📸",
        "profile_picture_url": pic_url,
        "instagram_id":        ig_id,
        "is_instagram":        True,
        "hashed":              "",
        "salt":                "",
        "created_at":          datetime.now().isoformat(),
        "liked_deals":         [],
    }
    data["users"][username.lower()] = user
    _save(USERS_FILE, data)
    return _public(user)


def get_user_by_username(username: str) -> Optional[dict]:
    user = load_users()["users"].get(username.lower())
    return _public(user) if user else None


# ── Per-user likes ────────────────────────────────────────────────────────────

def toggle_like(user_id: str, deal_id: int) -> bool:
    """Returns True = liked, False = unliked."""
    data  = load_users()
    found = None
    for user in data["users"].values():
        if user["id"] == user_id:
            found = user
            break
    if not found:
        return False

    liked = found.setdefault("liked_deals", [])
    sid   = str(deal_id)
    if sid in liked:
        liked.remove(sid)
        _save(USERS_FILE, data)
        return False
    liked.append(sid)
    _save(USERS_FILE, data)
    return True


def user_liked_deals(user_id: str) -> set:
    for user in load_users()["users"].values():
        if user["id"] == user_id:
            return set(user.get("liked_deals", []))
    return set()


def get_deal_like_counts() -> dict[str, int]:
    """Returns {deal_id_str: like_count}."""
    counts = {}
    for user in load_users()["users"].values():
        for did in user.get("liked_deals", []):
            counts[did] = counts.get(did, 0) + 1
    return counts


# ── Comments ──────────────────────────────────────────────────────────────────

def add_comment(deal_id: int, user: dict, text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("Comment cannot be empty")
    if len(text) > 500:
        raise ValueError("Comment too long (max 500 characters)")

    data = load_comments()
    key  = str(deal_id)
    data["comments"].setdefault(key, [])

    comment = {
        "id":           secrets.token_hex(6),
        "deal_id":      deal_id,
        "user_id":      user["id"],
        "username":     user["username"],
        "display_name": user["display_name"],
        "avatar":       user["avatar"],
        "text":         text,
        "ts":           int(time.time()),
        "created_at":   datetime.now().isoformat(),
    }
    data["comments"][key].append(comment)
    _save(COMMENTS_FILE, data)
    return comment


def get_comments(deal_id: int) -> list:
    return load_comments()["comments"].get(str(deal_id), [])


def get_comment_counts() -> dict[str, int]:
    return {k: len(v) for k, v in load_comments()["comments"].items()}


def delete_comment(deal_id: int, comment_id: str, user_id: str) -> bool:
    data     = load_comments()
    key      = str(deal_id)
    comments = data["comments"].get(key, [])
    for i, c in enumerate(comments):
        if c["id"] == comment_id and c["user_id"] == user_id:
            comments.pop(i)
            _save(COMMENTS_FILE, data)
            return True
    return False
