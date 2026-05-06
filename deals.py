import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx

DEALS_FILE = "deals.json"

DEAL_SOURCES = [
    {
        "name": "Slickdeals",
        "url": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
        "icon": "🔥",
        "color": "#ff6b35",
        "description": "Community-voted frontpage deals",
    },
    {
        "name": "Slickdeals Popular",
        "url": "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1",
        "icon": "⭐",
        "color": "#f59e0b",
        "description": "Most popular deals on Slickdeals",
    },
    {
        "name": "9to5Toys",
        "url": "https://9to5toys.com/feed/",
        "icon": "🎮",
        "color": "#16a34a",
        "description": "Best deals on tech, toys & gadgets",
    },
    {
        "name": "9to5Mac Deals",
        "url": "https://9to5mac.com/category/deals/feed/",
        "icon": "🍎",
        "color": "#6366f1",
        "description": "Top Apple & Mac deals daily",
    },
    {
        "name": "The Verge Deals",
        "url": "https://www.theverge.com/rss/deals/index.xml",
        "icon": "⚡",
        "color": "#e11d48",
        "description": "Editor-picked deals from The Verge",
    },
    {
        "name": "CNET Deals",
        "url": "https://www.cnet.com/rss/deals/",
        "icon": "💡",
        "color": "#0284c7",
        "description": "Expert-curated deals from CNET",
    },
    {
        "name": "Ben's Bargains",
        "url": "https://bensbargains.net/feed/",
        "icon": "💰",
        "color": "#7c3aed",
        "description": "Hand-picked bargains across all categories",
    },
    {
        "name": "TechRadar Deals",
        "url": "https://www.techradar.com/feeds/tag/deals",
        "icon": "📡",
        "color": "#0891b2",
        "description": "Latest tech deals from TechRadar",
    },
    {
        "name": "Reddit Deals",
        "url": "https://www.reddit.com/r/deals/.rss",
        "icon": "👾",
        "color": "#ff4500",
        "description": "Hot deals from Reddit's deal hunters",
    },
    {
        "name": "Reddit Frugal",
        "url": "https://www.reddit.com/r/frugal/.rss",
        "icon": "💸",
        "color": "#a855f7",
        "description": "Smart spending from the frugal community",
    },
]

SEASON_KEYWORDS = {
    "spring": ["spring", "garden", "outdoor", "patio", "easter", "flower", "lawn", "mother's day", "planting"],
    "summer": ["summer", "beach", "pool", "bbq", "grill", "travel", "vacation", "sunscreen", "camping", "swim", "memorial day"],
    "fall": ["fall", "autumn", "halloween", "thanksgiving", "cozy", "sweater", "back to school", "pumpkin"],
    "winter": ["winter", "holiday", "christmas", "gift", "snow", "heater", "new year", "cyber monday", "black friday"],
}

CATEGORY_KEYWORDS = {
    "tech": ["laptop", "phone", "tablet", "headphone", "camera", "tv", "monitor", "keyboard", "mouse", "gaming",
             "computer", "speaker", "audio", "gpu", "cpu", "iphone", "android", "ipad", "macbook", "playstation",
             "xbox", "nintendo", "earbuds", "smartwatch", "router", "ssd", "ram"],
    "fashion": ["shirt", "pants", "dress", "shoes", "sneakers", "jacket", "coat", "clothing", "apparel", "jeans",
                "hoodie", "boots", "sandals", "bag", "wallet", "jewelry", "nike", "adidas", "levis", "fashion"],
    "travel": ["flight", "hotel", "vacation", "travel", "trip", "cruise", "airbnb", "booking", "resort", "airline"],
    "food": ["food", "restaurant", "pizza", "burger", "meal", "grocery", "doordash", "uber eats", "coffee",
             "starbucks", "chipotle", "delivery", "dining", "snack", "drink"],
    "home": ["furniture", "sofa", "bed", "kitchen", "appliance", "vacuum", "mattress", "home", "decor", "tools",
             "lamp", "chair", "table", "cleaning", "storage", "cookware", "blender"],
    "health": ["fitness", "gym", "supplement", "vitamin", "health", "wellness", "yoga", "protein", "workout",
               "exercise", "running", "whey", "creatine"],
    "beauty": ["makeup", "skincare", "beauty", "hair", "cosmetic", "lotion", "perfume", "serum", "moisturizer",
               "shampoo", "conditioner"],
}


def get_current_season() -> str:
    month = datetime.now().month
    if month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    elif month in [9, 10, 11]:
        return "fall"
    return "winter"


def detect_category(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "other"


def detect_season(title: str, description: str) -> Optional[str]:
    text = (title + " " + description).lower()
    current = get_current_season()
    if any(kw in text for kw in SEASON_KEYWORDS.get(current, [])):
        return current
    for s, keywords in SEASON_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return s
    return None


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def load_deals() -> dict:
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"deals": [], "user_deals": [], "last_updated": None}


def save_deals(data: dict):
    with open(DEALS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_top_deals(category: str = "all", season: str = "all", limit: int = 50) -> dict:
    data = load_deals()
    deals = data.get("deals", []) + data.get("user_deals", [])

    if category and category != "all":
        deals = [d for d in deals if d.get("category") == category]
    if season and season != "all":
        deals = [d for d in deals if d.get("season") == season]

    # Deduplicate by link
    seen = set()
    unique = []
    for d in deals:
        key = d.get("link", "")
        if key not in seen:
            seen.add(key)
            unique.append(d)

    # Sort: votes first, then most recent
    unique.sort(key=lambda d: (d.get("votes", 0), d.get("fetched_at", 0)), reverse=True)

    return {
        "deals": unique[:limit],
        "total": len(unique),
        "last_updated": data.get("last_updated"),
        "current_season": get_current_season(),
    }


def _extract_link(item: ET.Element) -> str:
    """Extract link from both RSS (<link>url</link>) and Atom (<link href="url"/>) formats."""
    # RSS format: text content
    link_el = item.find("link")
    if link_el is not None:
        if link_el.text and link_el.text.strip():
            return link_el.text.strip()
        # Atom format: href attribute
        href = link_el.get("href", "").strip()
        if href:
            return href

    # Atom namespace fallback
    atom_ns = "http://www.w3.org/2005/Atom"
    for link_el in item.findall(f"{{{atom_ns}}}link"):
        href = link_el.get("href", "").strip()
        if href:
            return href

    # guid as last resort (Slickdeals uses this)
    guid_el = item.find("guid")
    if guid_el is not None and guid_el.text and guid_el.text.startswith("http"):
        return guid_el.text.strip()

    return ""


async def fetch_rss_source(source: dict, client: httpx.AsyncClient) -> list:
    deals = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LifezAI/1.0; +https://lifez.ai)"}
        resp = await client.get(source["url"], headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        # Support both RSS <item> and Atom <entry>
        atom_ns = "http://www.w3.org/2005/Atom"
        items = root.findall(".//item") or root.findall(f".//{{{atom_ns}}}entry")

        for item in items[:25]:
            title_el = item.find("title") or item.find(f"{{{atom_ns}}}title")
            desc_el  = item.find("description") or item.find(f"{{{atom_ns}}}summary") or item.find(f"{{{atom_ns}}}content")
            pub_el   = item.find("pubDate") or item.find(f"{{{atom_ns}}}published") or item.find(f"{{{atom_ns}}}updated")

            title       = strip_html(title_el.text if title_el is not None else "")
            link        = _extract_link(item)
            description = strip_html(desc_el.text if desc_el is not None else "")[:250]
            pub_date    = (pub_el.text or "").strip()

            if not title or not link:
                continue

            deals.append({
                "id": abs(hash(link)) % (10 ** 9),
                "title": title,
                "link": link,
                "description": description,
                "source": source["name"],
                "source_icon": source["icon"],
                "source_color": source["color"],
                "pub_date": pub_date,
                "season": detect_season(title, description),
                "category": detect_category(title, description),
                "fetched_at": int(time.time()),
                "is_user_submitted": False,
                "votes": 0,
            })
    except Exception as e:
        print(f"  ⚠️  {source['name']}: {e}")
    return deals


async def refresh_deals() -> int:
    print(f"[{datetime.now().strftime('%H:%M')}] Refreshing deals...")
    all_new_deals = []

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[fetch_rss_source(src, client) for src in DEAL_SOURCES],
            return_exceptions=True,
        )

    for result in results:
        if isinstance(result, list):
            all_new_deals.extend(result)

    data = load_deals()
    data["deals"] = all_new_deals
    data["last_updated"] = datetime.now().isoformat()
    save_deals(data)
    print(f"✅ {len(all_new_deals)} deals from {len(DEAL_SOURCES)} sources")
    return len(all_new_deals)


async def hourly_refresh_loop():
    await refresh_deals()
    while True:
        await asyncio.sleep(3600)
        await refresh_deals()
