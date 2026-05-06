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

GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="

DEAL_SOURCES = [
    {
        "name": "Hot Deals",
        "url": GN + "best+deals+today+sale",
        "icon": "🔥",
        "color": "#ff6b35",
        "description": "Hottest deals across the web right now",
    },
    {
        "name": "Tech Deals",
        "url": GN + "tech+deals+discount+sale",
        "icon": "💻",
        "color": "#6366f1",
        "description": "Best discounts on gadgets & electronics",
    },
    {
        "name": "Amazon Deals",
        "url": GN + "amazon+deals+sale+discount",
        "icon": "📦",
        "color": "#f59e0b",
        "description": "Top Amazon sales & lightning deals",
    },
    {
        "name": "Fashion Deals",
        "url": GN + "fashion+clothing+deals+sale+coupon",
        "icon": "👗",
        "color": "#ec4899",
        "description": "Best fashion & clothing discounts",
    },
    {
        "name": "Travel Deals",
        "url": GN + "travel+flight+hotel+deals+discount",
        "icon": "✈️",
        "color": "#0891b2",
        "description": "Flight, hotel and vacation deals",
    },
    {
        "name": "Home Deals",
        "url": GN + "home+furniture+appliance+deals+sale",
        "icon": "🏠",
        "color": "#16a34a",
        "description": "Home, furniture & appliance discounts",
    },
    {
        "name": "Spring Deals",
        "url": GN + "spring+2026+deals+sale+discount",
        "icon": "🌸",
        "color": "#84cc16",
        "description": "Best seasonal spring deals",
    },
    {
        "name": "Coupon Deals",
        "url": GN + "coupon+promo+code+discount+deal",
        "icon": "🎟️",
        "color": "#7c3aed",
        "description": "Latest coupons and promo codes",
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


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_link(item: ET.Element) -> str:
    """Handle both RSS <link>url</link> and Atom <link href='url'/>."""
    link_el = item.find("link")
    if link_el is not None:
        if link_el.text and link_el.text.strip().startswith("http"):
            return link_el.text.strip()
        href = link_el.get("href", "").strip()
        if href:
            return href
    ns = "http://www.w3.org/2005/Atom"
    for el in item.findall(f"{{{ns}}}link"):
        href = el.get("href", "").strip()
        if href:
            return href
    guid = item.find("guid")
    if guid is not None and (guid.text or "").startswith("http"):
        return guid.text.strip()
    return ""


async def fetch_rss_source(source: dict, client: httpx.AsyncClient) -> list:
    deals = []
    try:
        resp = await client.get(source["url"], headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()

        # Strip any BOM / leading whitespace before parsing
        text = resp.text.strip().lstrip("﻿")
        root = ET.fromstring(text)

        ns = "http://www.w3.org/2005/Atom"
        items = root.findall(".//item") or root.findall(f".//{{{ns}}}entry")

        for item in items[:25]:
            def _find(el, tag, ns_tag):
                e = el.find(tag)
                return e if e is not None else el.find(ns_tag)

            title_el = _find(item, "title",       f"{{{ns}}}title")
            desc_el  = _find(item, "description", f"{{{ns}}}summary") or item.find(f"{{{ns}}}content")
            pub_el   = _find(item, "pubDate",     f"{{{ns}}}published") or item.find(f"{{{ns}}}updated")

            title       = strip_html(title_el.text if title_el is not None else "")
            link        = _extract_link(item)
            description = strip_html(desc_el.text if desc_el is not None else "")[:250]
            pub_date    = (pub_el.text or "").strip() if pub_el is not None else ""

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
        print(f"  ✓  {source['name']}: {len(deals)} deals")
    except Exception as e:
        print(f"  ⚠️  {source['name']}: {e}")
    return deals


async def refresh_deals() -> int:
    print(f"[{datetime.now().strftime('%H:%M')}] Refreshing deals...")
    all_new_deals = []

    async with httpx.AsyncClient() as client:
        for src in DEAL_SOURCES:
            deals = await fetch_rss_source(src, client)
            all_new_deals.extend(deals)
            await asyncio.sleep(0.8)   # avoid triggering rate-limits

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
