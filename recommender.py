import os
import json
from products import PRODUCTS

# Initialize Groq client - will be set when API key is available
client = None

def init_groq():
    """Initialize Groq client if API key is available"""
    global client
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
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
    
    # Create a prompt for Groq to understand user requirements
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
    
    prompt = f"""You are a helpful shopping assistant. Based on the user's requirement, recommend the best products from our inventory.

Available Products:
{products_info}

User Requirement: {user_requirement}

Please respond with a JSON object containing:
1. "recommendations": an array of product IDs (integers) that best match the requirement
2. "reasoning": a brief explanation of why these products were chosen
3. "filters_applied": any filters applied (e.g., price range, category)
4. "summary": a helpful summary for the user

Respond ONLY with valid JSON, no other text."""

    try:
        message = client.messages.create(
            model="mixtral-8x7b-32768",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Parse the JSON response
        recommendation_data = json.loads(response_text)
        
        # Get the actual product objects
        product_ids = recommendation_data.get("recommendations", [])
        recommended_products = []
        
        for pid in product_ids:
            product = next((p for p in PRODUCTS if p["id"] == pid), None)
            if product:
                recommended_products.append(product)
        
        return {
            "success": True,
            "user_requirement": user_requirement,
            "recommended_products": recommended_products,
            "reasoning": recommendation_data.get("reasoning", ""),
            "filters_applied": recommendation_data.get("filters_applied", ""),
            "summary": recommendation_data.get("summary", ""),
            "count": len(recommended_products)
        }
        
    except json.JSONDecodeError:
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
        return {
            "success": False,
            "error": str(e),
            "user_requirement": user_requirement,
            "recommended_products": []
        }

# Initialize on import
init_groq()
