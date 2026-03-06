from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Product Database (Mock data - can be replaced with real API calls)
PRODUCT_DATABASE = [
    # Laptops
    {"id": 1, "name": "Dell XPS 13 Laptop", "price": "$999.99", "rating": 4.7, "reviews": 2541, "category": "laptop", "image": "💻", "prime": True, "badge": "Best Seller"},
    {"id": 2, "name": "MacBook Air M2", "price": "$1,299.99", "rating": 4.8, "reviews": 3215, "category": "laptop", "image": "💻", "prime": True, "badge": "Premium"},
    {"id": 3, "name": "HP Pavilion 15", "price": "$649.99", "rating": 4.5, "reviews": 1823, "category": "laptop", "image": "💻", "prime": True},
    {"id": 4, "name": "ASUS VivoBook 14", "price": "$549.99", "rating": 4.6, "reviews": 1542, "category": "laptop", "image": "💻", "prime": True},
    
    # Headphones
    {"id": 5, "name": "Sony WH-1000XM4 Headphones", "price": "$348.99", "rating": 4.7, "reviews": 5123, "category": "headphones", "image": "🎧", "prime": True, "badge": "Best Seller"},
    {"id": 6, "name": "Apple AirPods Pro Max", "price": "$549.99", "rating": 4.8, "reviews": 2341, "category": "headphones", "image": "🎧", "prime": True, "badge": "Premium"},
    {"id": 7, "name": "Bose QuietComfort 45", "price": "$379.95", "rating": 4.6, "reviews": 3214, "category": "headphones", "image": "🎧", "prime": True},
    {"id": 8, "name": "Samsung Galaxy Buds Pro", "price": "$199.99", "rating": 4.5, "reviews": 2812, "category": "headphones", "image": "🎧", "prime": True},
    
    # Smartphones
    {"id": 9, "name": "iPhone 15 Pro", "price": "$999.00", "rating": 4.8, "reviews": 4521, "category": "phone", "image": "📱", "prime": True, "badge": "Latest"},
    {"id": 10, "name": "Samsung Galaxy S24", "price": "$899.99", "rating": 4.7, "reviews": 3845, "category": "phone", "image": "📱", "prime": True},
    {"id": 11, "name": "Google Pixel 8", "price": "$799.00", "rating": 4.6, "reviews": 2156, "category": "phone", "image": "📱", "prime": True},
    {"id": 12, "name": "OnePlus 12", "price": "$729.99", "rating": 4.5, "reviews": 1923, "category": "phone", "image": "📱", "prime": True},
    
    # Phone Accessories
    {"id": 13, "name": "Premium Phone Case", "price": "$29.99", "rating": 4.4, "reviews": 8234, "category": "case", "image": "📦", "prime": True},
    {"id": 14, "name": "Screen Protector Glass", "price": "$9.99", "rating": 4.3, "reviews": 12543, "category": "case", "image": "🛡️", "prime": True},
    {"id": 15, "name": "Fast Charging Cable", "price": "$14.99", "rating": 4.5, "reviews": 9821, "category": "case", "image": "🔌", "prime": True},
    {"id": 16, "name": "Wireless Charging Pad", "price": "$24.99", "rating": 4.6, "reviews": 6234, "category": "case", "image": "🔌", "prime": True},
    
    # Tablets
    {"id": 17, "name": "iPad Air", "price": "$599.00", "rating": 4.7, "reviews": 2342, "category": "tablet", "image": "📱", "prime": True},
    {"id": 18, "name": "Samsung Galaxy Tab S9", "price": "$549.99", "rating": 4.6, "reviews": 1834, "category": "tablet", "image": "📱", "prime": True},
    {"id": 19, "name": "Microsoft Surface Go", "price": "$399.99", "rating": 4.5, "reviews": 1523, "category": "tablet", "image": "📱", "prime": True},
    
    # Smartwatches
    {"id": 20, "name": "Apple Watch Series 9", "price": "$399.00", "rating": 4.7, "reviews": 3421, "category": "watch", "image": "⌚", "prime": True},
    {"id": 21, "name": "Garmin Epix Gen 2", "price": "$499.99", "rating": 4.6, "reviews": 1876, "category": "watch", "image": "⌚", "prime": True},
    {"id": 22, "name": "Samsung Galaxy Watch 6", "price": "$299.99", "rating": 4.5, "reviews": 2543, "category": "watch", "image": "⌚", "prime": True},
    
    # Cameras
    {"id": 23, "name": "Sony A6700 Mirrorless", "price": "$1,398.00", "rating": 4.8, "reviews": 876, "category": "camera", "image": "📷", "prime": True, "badge": "Premium"},
    {"id": 24, "name": "Canon EOS R50", "price": "$799.00", "rating": 4.6, "reviews": 654, "category": "camera", "image": "📷", "prime": True},
    {"id": 25, "name": "GoPro HERO 12", "price": "$399.99", "rating": 4.7, "reviews": 3456, "category": "camera", "image": "📷", "prime": True},
    
    # Home Appliances
    {"id": 26, "name": "Robot Vacuum Cleaner", "price": "$299.99", "rating": 4.5, "reviews": 4321, "category": "appliance", "image": "🤖", "prime": True},
    {"id": 27, "name": "Smart WiFi Speaker", "price": "$89.99", "rating": 4.4, "reviews": 5234, "category": "appliance", "image": "🔊", "prime": True},
    {"id": 28, "name": "Smart Thermostat", "price": "$249.99", "rating": 4.6, "reviews": 2134, "category": "appliance", "image": "🌡️", "prime": True},
]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/search")
def search_products(q: str = Query(..., min_length=1)):
    """
    Search products by name or category
    Usage: /api/search?q=laptop
    """
    query = q.lower().strip()
    
    # Filter products by name or category
    results = [
        product for product in PRODUCT_DATABASE
        if query in product["name"].lower() or 
           query in product["category"].lower()
    ]
    
    return {
        "query": q,
        "count": len(results),
        "products": results
    }

@app.get("/hello")
def hello():
    return {"message": "Hello Ramesh"}

@app.get("/goodbye")
def goodbye():
    return {"message": "Goodbye Ramesh"}

# Mount static files only if directory exists
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")