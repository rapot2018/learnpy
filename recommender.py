import os
import json
from products import PRODUCTS
from config import GROQ_API_KEY

# Initialize Groq client - will be set when API key is available
client = None

def init_groq():
    """Initialize Groq client if API key is available"""
    global client
    # Try to get API key from config first, then environment variable
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            print("✅ Groq AI initialized successfully!")
            return True
        except Exception as e:
            print(f"Failed to initialize Groq: {e}")
            return False
    return False

def get_recommendations(user_requirement: str) -> dict:
    """
    Get product recommendations based on user requirement using Groq AI.
    
    Args:
        user_requirement: User's natural language requirement
        
    Returns:
        dict: Contains recommended products and reasoning
    """
    
    # Check if Groq is available
    if not client:
        # Fallback: return top products based on keyword matching
        products_info = json.dumps([
            {
                "id": p["id"],
                "name": p["name"],
                "category": p["category"],
                "price": p["price"],
                "specs": p["specs"],
                "rating": p["rating"],
                "description": p["description"]
            }
            for p in PRODUCTS
        ], indent=2)
        
        # Simple keyword-based recommendation
        keyword = user_requirement.lower()
        recommended_ids = []
        for product in PRODUCTS:
            if any(word in product["name"].lower() or word in product["description"].lower() 
                   for word in keyword.split()):
                recommended_ids.append(product["id"])
        
        if not recommended_ids:
            recommended_ids = [1, 2, 3]  # Default to first 3 products
        
        recommended_products = [p for p in PRODUCTS if p["id"] in recommended_ids]
        
        return {
            "success": True,
            "user_requirement": user_requirement,
            "recommended_products": recommended_products,
            "reasoning": "Using keyword matching (Groq API key not configured)",
            "filters_applied": "None",
            "summary": f"Found {len(recommended_products)} products matching your requirement",
            "count": len(recommended_products)
        }
    
    prompt = f"""You are a helpful shopping assistant. Recommend real products that match the user's requirement. Use your knowledge of actual products (brands, models, prices) available in the market.

User Requirement: {user_requirement}

Respond with a JSON object containing:
1. "recommendations": an array of 3-5 product objects. Each product MUST have: id (integer 1-99), name (string), category (string, e.g. electronics/audio/mobile/peripherals/wearables), price (number in USD), specs (array of strings, key features), rating (number 0-5), description (string).
2. "reasoning": a brief explanation of why these products were chosen
3. "filters_applied": any filters applied (e.g., price range, category)
4. "summary": a helpful summary for the user

Use real product names and approximate real prices. Respond ONLY with valid JSON, no other text."""

    try:
        # Call Groq API with latest available model
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        
        response_text = response.choices[0].message.content
        
        # Extract JSON from response (it might be wrapped in markdown code blocks)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
        
        # Parse the JSON response
        recommendation_data = json.loads(json_str)
        
        # Use products directly from Groq response (real products from Groq's knowledge)
        raw_products = recommendation_data.get("recommendations", [])
        recommended_products = []
        for i, p in enumerate(raw_products):
            if isinstance(p, dict) and "name" in p:
                specs = p.get("specs", [])
                if isinstance(specs, str):
                    specs = [s.strip() for s in specs.split(",")] if specs else []
                product = {
                    "id": int(p["id"]) if isinstance(p.get("id"), (int, float)) else (i + 1),
                    "name": str(p["name"]),
                    "category": str(p.get("category", "electronics")),
                    "price": int(p["price"]) if isinstance(p.get("price"), (int, float)) else int(float(p.get("price", 0))),
                    "specs": specs if isinstance(specs, list) else [],
                    "rating": float(p["rating"]) if isinstance(p.get("rating"), (int, float)) else float(p.get("rating", 4.0)),
                    "description": str(p.get("description", "")),
                }
                recommended_products.append(product)

        if not recommended_products:
            recommended_products = PRODUCTS[:3]

        return {
            "success": True,
            "user_requirement": user_requirement,
            "recommended_products": recommended_products,
            "reasoning": recommendation_data.get("reasoning", ""),
            "filters_applied": recommendation_data.get("filters_applied", ""),
            "summary": recommendation_data.get("summary", ""),
            "count": len(recommended_products)
        }
        
    except json.JSONDecodeError as e:
        # Log the error for debugging
        print(f"JSON Parse Error: {e}")
        print(f"Response was: {response_text[:200]}")
        # If response is not valid JSON, try to extract product recommendations manually
        return {
            "success": True,
            "user_requirement": user_requirement,
            "recommended_products": PRODUCTS[:3],  # Return top 3 as fallback
            "reasoning": "Using default recommendations",
            "filters_applied": "None",
            "summary": "Could not parse AI response, showing popular products",
            "count": 3
        }
    except Exception as e:
        # Log the error and return fallback recommendations
        print(f"Groq API Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return {
            "success": True,
            "user_requirement": user_requirement,
            "recommended_products": PRODUCTS[:3],  # Return top 3 as fallback
            "reasoning": "Could not reach AI service, showing popular products",
            "filters_applied": "None",
            "summary": "AI Service temporarily unavailable. Showing popular products.",
            "count": 3
        }

# Initialize on import
init_groq()
