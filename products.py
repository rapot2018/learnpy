# Mock product database
PRODUCTS = [
    {
        "id": 1,
        "name": "Budget Laptop - Dell Inspiron",
        "category": "electronics",
        "price": 599,
        "specs": ["Intel i5", "8GB RAM", "256GB SSD", "15.6 inch display"],
        "rating": 4.2,
        "description": "Affordable laptop for everyday computing and light work"
    },
    {
        "id": 2,
        "name": "Professional Laptop - MacBook Pro",
        "category": "electronics",
        "price": 1999,
        "specs": ["M3 Chip", "16GB RAM", "512GB SSD", "14 inch display", "4K camera"],
        "rating": 4.8,
        "description": "High-performance laptop for professionals and developers"
    },
    {
        "id": 3,
        "name": "Gaming Laptop - ASUS ROG",
        "category": "electronics",
        "price": 1499,
        "specs": ["RTX 4060", "Intel i7", "16GB RAM", "512GB SSD", "165Hz display"],
        "rating": 4.6,
        "description": "Powerful gaming laptop with excellent graphics"
    },
    {
        "id": 4,
        "name": "Wireless Headphones - Sony WH-1000XM5",
        "category": "audio",
        "price": 399,
        "specs": ["Noise cancellation", "40hr battery", "Bluetooth 5.3", "Premium sound"],
        "rating": 4.7,
        "description": "Premium noise-cancelling wireless headphones"
    },
    {
        "id": 5,
        "name": "Budget Headphones - Anker Soundcore",
        "category": "audio",
        "price": 59,
        "specs": ["Wireless", "20hr battery", "Deep bass", "Comfortable fit"],
        "rating": 4.3,
        "description": "Affordable wireless headphones with great value"
    },
    {
        "id": 6,
        "name": "Smartphone - iPhone 15",
        "category": "mobile",
        "price": 999,
        "specs": ["A17 Pro chip", "6.1 inch display", "48MP camera", "5G"],
        "rating": 4.7,
        "description": "Latest iPhone with advanced camera and processing"
    },
    {
        "id": 7,
        "name": "Budget Smartphone - Samsung A54",
        "category": "mobile",
        "price": 449,
        "specs": ["Exynos 1280", "6.4 inch display", "50MP camera", "5G"],
        "rating": 4.4,
        "description": "Great mid-range smartphone with excellent camera"
    },
    {
        "id": 8,
        "name": "Tablet - iPad Pro",
        "category": "mobile",
        "price": 1099,
        "specs": ["M2 chip", "12.9 inch display", "ProMotion 120Hz", "Pen support"],
        "rating": 4.8,
        "description": "Professional-grade tablet for creative work"
    },
    {
        "id": 9,
        "name": "4K Monitor - Dell S2722DC",
        "category": "peripherals",
        "price": 699,
        "specs": ["4K resolution", "27 inch", "USB-C", "Thunderbolt 3"],
        "rating": 4.5,
        "description": "Professional 4K monitor with excellent color accuracy"
    },
    {
        "id": 10,
        "name": "Mechanical Keyboard - Corsair K95",
        "category": "peripherals",
        "price": 199,
        "specs": ["Mechanical switches", "RGB lighting", "Wireless", "Programmable"],
        "rating": 4.6,
        "description": "Premium mechanical keyboard for gaming and work"
    },
    {
        "id": 11,
        "name": "Smartwatch - Apple Watch Series 9",
        "category": "wearables",
        "price": 399,
        "specs": ["Retina display", "Heart rate monitor", "Blood oxygen tracking", "Fitness tracking", "Water resistant"],
        "rating": 4.8,
        "description": "Advanced smartwatch with health monitoring and fitness tracking"
    },
    {
        "id": 12,
        "name": "Smartwatch - Samsung Galaxy Watch 6",
        "category": "wearables",
        "price": 299,
        "specs": ["AMOLED display", "Heart rate sensor", "Sleep tracking", "5G ready", "7-day battery"],
        "rating": 4.6,
        "description": "Feature-rich smartwatch with excellent battery life"
    },
    {
        "id": 13,
        "name": "Fitness Tracker - Fitbit Charge 6",
        "category": "wearables",
        "price": 159,
        "specs": ["Sleep tracking", "Stress management", "GPS", "Water resistant", "Up to 7-day battery"],
        "rating": 4.4,
        "description": "Affordable fitness tracker for daily activity monitoring"
    }
]

def search_products_by_category(category: str) -> list:
    """Search products by category"""
    return [p for p in PRODUCTS if p["category"].lower() == category.lower()]

def search_products_by_price_range(min_price: int, max_price: int) -> list:
    """Search products within price range"""
    return [p for p in PRODUCTS if min_price <= p["price"] <= max_price]

def search_products_by_name(keyword: str) -> list:
    """Search products by name or description"""
    keyword = keyword.lower()
    return [p for p in PRODUCTS if keyword in p["name"].lower() or keyword in p["description"].lower()]

def get_all_products() -> list:
    """Get all products"""
    return PRODUCTS

def get_product_by_id(product_id: int) -> dict:
    """Get product by ID"""
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None

def filter_products(filters: dict) -> list:
    """Filter products by multiple criteria"""
    results = PRODUCTS
    
    if "category" in filters:
        results = [p for p in results if p["category"].lower() == filters["category"].lower()]
    
    if "min_price" in filters:
        results = [p for p in results if p["price"] >= filters["min_price"]]
    
    if "max_price" in filters:
        results = [p for p in results if p["price"] <= filters["max_price"]]
    
    if "rating_min" in filters:
        results = [p for p in results if p["rating"] >= filters["rating_min"]]
    
    if "keyword" in filters:
        keyword = filters["keyword"].lower()
        results = [p for p in results if keyword in p["name"].lower() or keyword in p["description"].lower()]
    
    return results
