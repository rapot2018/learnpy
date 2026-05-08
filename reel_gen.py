"""
Generate Instagram-ready images for deals.
  - post_card()  → 1080×1080 square (Instagram Feed post)
  - story_card() → 1080×1920 vertical (Instagram Story / Reel cover)
"""
import io
import os
import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path("static/SpaceGrotesk-Bold.ttf")
FONT_URL  = "https://github.com/floriankarsten/space-grotesk/raw/master/fonts/ttf/SpaceGrotesk-Bold.ttf"

SOURCE_COLORS = {
    "Hot Deals":       ("#ff6b35", "#f97316"),
    "Tech Deals":      ("#6366f1", "#8b5cf6"),
    "Amazon Deals":    ("#f59e0b", "#f97316"),
    "Fashion Deals":   ("#ec4899", "#db2777"),
    "Travel Deals":    ("#0891b2", "#06b6d4"),
    "Home Deals":      ("#16a34a", "#22c55e"),
    "Gaming Deals":    ("#7c3aed", "#a855f7"),
    "Software Deals":  ("#0891b2", "#06b6d4"),
    "Student Deals":   ("#16a34a", "#22c55e"),
    "Clearance Sales": ("#dc2626", "#ef4444"),
    "Pet Deals":       ("#d97706", "#f59e0b"),
    "Kids & Baby":     ("#ec4899", "#f472b6"),
    "Sports & Outdoors": ("#15803d", "#16a34a"),
    "Streaming Deals": ("#e11d48", "#f43f5e"),
    "Grocery Deals":   ("#059669", "#10b981"),
    "Luxury Deals":    ("#92400e", "#b45309"),
    "Spring Deals":    ("#84cc16", "#a3e635"),
    "Coupon Deals":    ("#7c3aed", "#8b5cf6"),
    "Community":       ("#0891b2", "#06b6d4"),
}

CAT_ICONS = {
    "tech": "💻", "fashion": "👗", "travel": "✈️", "food": "🍔",
    "home": "🏡", "health": "💪", "beauty": "✨", "gaming": "🎮",
    "kids": "🧸", "pets": "🐾", "streaming": "📺", "student": "🎓",
    "other": "🏷️",
}


def _ensure_font():
    if FONT_PATH.exists():
        return
    try:
        import httpx
        r = httpx.get(FONT_URL, follow_redirects=True, timeout=20)
        r.raise_for_status()
        FONT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FONT_PATH.write_bytes(r.content)
    except Exception as e:
        print(f"Font download failed: {e}")


def _font(size: int) -> ImageFont.FreeTypeFont:
    _ensure_font()
    if FONT_PATH.exists():
        try:
            return ImageFont.truetype(str(FONT_PATH), size)
        except Exception:
            pass
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _gradient_bg(img: Image.Image, c1: str, c2: str):
    draw = ImageDraw.Draw(img)
    W, H = img.size

    def hex_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    r1, g1, b1 = hex_rgb(c1)
    r2, g2, b2 = hex_rgb(c2)
    for y in range(H):
        t = y / H
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _wrap_text(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text, width=max_chars)


def post_card(deal: dict) -> bytes:
    """1080×1080 square card for Instagram Feed."""
    W = H = 1080
    src    = deal.get("source", "Lifez.AI")
    c1, c2 = SOURCE_COLORS.get(src, ("#1d4ed8", "#2563eb"))

    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _gradient_bg(img, c1, c2)

    # Dark overlay for readability
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    img.paste(Image.new("RGB", (W, H), (0, 0, 0)), mask=overlay.split()[3])

    # Re-apply gradient on top of overlay (blended)
    img2 = Image.new("RGB", (W, H))
    _gradient_bg(img2, c1, c2)
    img = Image.blend(img, img2, 0.55)
    draw = ImageDraw.Draw(img)

    # Top: Lifez.AI logo
    draw.text((60, 60), "💰 Lifez.AI", font=_font(42), fill=(255, 255, 255))
    draw.text((60, 112), "Life's Too Short for Full Price", font=_font(22), fill=(255, 255, 255, 180))

    # Divider
    draw.rectangle([60, 150, W - 60, 153], fill=(255, 255, 255, 60))

    # Source badge
    source_icon = deal.get("source_icon", "🔥")
    draw.text((60, 175), f"{source_icon} {src}", font=_font(28), fill=(255, 255, 220))

    # Category
    cat      = deal.get("category", "other")
    cat_icon = CAT_ICONS.get(cat, "🏷️")
    draw.text((W - 60 - 200, 180), f"{cat_icon} {cat}", font=_font(26), fill=(255, 255, 255, 180))

    # Deal title (large, center stage)
    title = deal.get("title", "")
    lines = _wrap_text(title, 32)[:4]
    y = 280
    for line in lines:
        draw.text((60, y), line, font=_font(52), fill=(255, 255, 255))
        y += 70

    # Description
    desc  = deal.get("description", "")
    if desc:
        dlines = _wrap_text(desc, 55)[:3]
        y += 20
        for dl in dlines:
            draw.text((60, y), dl, font=_font(30), fill=(255, 255, 255, 200))
            y += 42

    # Big emoji watermark (background)
    big_icon = source_icon or "🔥"
    draw.text((W - 180, H - 260), big_icon, font=_font(180), fill=(255, 255, 255, 25))

    # CTA bar at bottom
    draw.rectangle([0, H - 140, W, H], fill=(0, 0, 0, 180))
    draw.text((60, H - 110), "🔗 Grab this deal at lifez.ai", font=_font(34), fill=(255, 255, 255))
    draw.text((60, H - 65),  "#deals #lifezai #savemoney #dealsoftheday", font=_font(22), fill=(200, 200, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def story_card(deal: dict) -> bytes:
    """1080×1920 vertical card for Instagram Stories / Reels cover."""
    W, H = 1080, 1920
    src   = deal.get("source", "Lifez.AI")
    c1, c2 = SOURCE_COLORS.get(src, ("#1d4ed8", "#0a0a2e"))

    img  = Image.new("RGB", (W, H))
    _gradient_bg(img, c1, c2)
    draw = ImageDraw.Draw(img)

    # Dark center overlay
    draw.rectangle([0, H//4, W, 3*H//4], fill=(0, 0, 0, 100))

    # Top logo area
    draw.text((W//2 - 130, 120), "💰 Lifez.AI", font=_font(58), fill=(255, 255, 255))
    draw.text((W//2 - 200, 192), "Life's Too Short for Full Price", font=_font(30), fill=(255, 255, 255, 200))

    # Source
    source_icon = deal.get("source_icon", "🔥")
    draw.text((W//2 - 80, 340), f"{source_icon} {src}", font=_font(36), fill=(255, 255, 220))

    # Big emoji
    cat_icon = CAT_ICONS.get(deal.get("category", "other"), "🏷️")
    draw.text((W//2 - 80, 460), cat_icon, font=_font(160), fill=(255, 255, 255, 220))

    # Deal title
    title = deal.get("title", "")
    lines = _wrap_text(title, 24)[:5]
    y = 700
    for line in lines:
        tw = draw.textlength(line, font=_font(60))
        draw.text(((W - tw) // 2, y), line, font=_font(60), fill=(255, 255, 255))
        y += 82

    # Description
    desc = deal.get("description", "")
    if desc:
        dlines = _wrap_text(desc, 40)[:3]
        y += 24
        for dl in dlines:
            tw = draw.textlength(dl, font=_font(34))
            draw.text(((W - tw) // 2, y), dl, font=_font(34), fill=(255, 255, 255, 200))
            y += 48

    # Bottom CTA
    draw.rectangle([0, H - 220, W, H], fill=(0, 0, 0, 200))
    cta = "🔗 Link in bio → lifez.ai"
    tw  = draw.textlength(cta, font=_font(42))
    draw.text(((W - tw)//2, H - 190), cta, font=_font(42), fill=(255, 255, 255))

    tags = "#deals #lifezai #savemoney #dealsoftheday #shopping"
    tw   = draw.textlength(tags, font=_font(26))
    draw.text(((W - tw)//2, H - 130), tags, font=_font(26), fill=(200, 200, 255))

    ts = datetime.now().strftime("%b %d, %Y")
    tw = draw.textlength(ts, font=_font(22))
    draw.text(((W - tw)//2, H - 70), ts, font=_font(22), fill=(200, 200, 200))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def top_deals_story(deals: list) -> bytes:
    """1080×1920 story card showing top 5 deals — for daily auto-post."""
    W, H = 1080, 1920
    img  = Image.new("RGB", (W, H), (10, 10, 30))
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        t = y / H
        r = int(10 + 20 * t)
        g = int(10 + 15 * t)
        b = int(30 + 50 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Top bar
    draw.rectangle([0, 0, W, 8], fill="#2563eb")

    # Logo
    draw.text((80, 80),  "💰 Lifez.AI", font=_font(72), fill=(255, 255, 255))
    draw.text((80, 168), "Life's Too Short for Full Price", font=_font(32), fill=(180, 200, 255))

    # Today's date
    draw.text((80, 230), f"🔥 Top Deals — {datetime.now().strftime('%B %d, %Y')}", font=_font(36), fill=(255, 220, 100))

    # Divider
    draw.rectangle([80, 290, W - 80, 294], fill=(255, 255, 255, 60))

    # Deal rows
    y = 330
    for i, deal in enumerate(deals[:5]):
        src   = deal.get("source", "")
        c1, _ = SOURCE_COLORS.get(src, ("#2563eb", "#1d4ed8"))
        icon  = deal.get("source_icon", "🔥")
        title = deal.get("title", "")
        if len(title) > 45:
            title = title[:42] + "…"

        # Row bg
        row_color = (20, 25, 50) if i % 2 == 0 else (15, 20, 45)
        draw.rounded_rectangle([60, y, W - 60, y + 220], radius=20, fill=row_color)

        # Rank circle
        rc = (40, 60, 120) if i > 0 else (29, 78, 216)
        draw.ellipse([90, y + 30, 160, y + 100], fill=rc)
        n_font = _font(36)
        nw = draw.textlength(str(i + 1), font=n_font)
        draw.text((125 - nw//2, y + 42), str(i + 1), font=n_font, fill=(255, 255, 255))

        # Source
        draw.text((182, y + 28), f"{icon} {src}", font=_font(26), fill=c1)
        # Title
        draw.text((182, y + 72), title, font=_font(34), fill=(240, 240, 255))
        # Category
        cat = CAT_ICONS.get(deal.get("category", "other"), "🏷️")
        draw.text((182, y + 120), cat + " " + deal.get("category", "other"), font=_font(24), fill=(150, 160, 200))

        y += 240

    # Bottom
    draw.rectangle([0, H - 160, W, H], fill=(10, 10, 30))
    cta = "🔗 See all deals at lifez.ai"
    tw  = draw.textlength(cta, font=_font(40))
    draw.text(((W - tw)//2, H - 140), cta, font=_font(40), fill=(255, 255, 255))
    tags = "#deals #lifezai #savemoney #dealsoftheday"
    tw   = draw.textlength(tags, font=_font(28))
    draw.text(((W - tw)//2, H - 80), tags, font=_font(28), fill=(150, 160, 220))

    draw.rectangle([0, H - 8, W, H], fill="#ec4899")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
