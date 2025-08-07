from fastapi import FastAPI, HTTPException, Request, Depends, Form, status, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Body

import pymysql
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, StreamingResponse
from datetime import datetime, timedelta, time as dt_time
import time
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional, Dict, Tuple, List, Union
import secrets
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json
import os
import random
import numpy as np
import cv2
import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification, SiglipForImageClassification
from PIL import Image
import requests
import pandas as pd
import io

# Import food detection routes
try:
    from routes.food_detect import router as food_detect_router
    FOOD_DETECT_AVAILABLE = True
except ImportError:
    FOOD_DETECT_AVAILABLE = False
    print("Warning: Food detection routes not available")
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# USDA Database Integration
USDA_API_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")

def get_usda_api_key() -> str:
    """Get USDA API key from environment or use demo key"""
    api_key = os.environ.get('USDA_API_KEY')
    if not api_key:
        print("Warning: No USDA API key found. Using DEMO_KEY with rate limits.")
        return 'DEMO_KEY'
    return api_key

def search_usda_foods(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search for foods in USDA database
    Returns list of food items with basic info
    """
    api_key = get_usda_api_key()
    url = f"{USDA_API_BASE_URL}/foods/search"
    
    params = {
        'api_key': api_key,
        'query': query,
        'pageSize': max_results,
        'dataType': ['Foundation', 'SR Legacy'],  # Most comprehensive data
        'sortBy': 'dataType.keyword',
        'sortOrder': 'asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        foods = []
        for food in data.get('foods', []):
            foods.append({
                'fdc_id': food.get('fdcId'),
                'name': food.get('description', ''),
                'brand': food.get('brandOwner', ''),
                'category': food.get('foodCategory', ''),
                'data_type': food.get('dataType', ''),
                'published_date': food.get('publishedDate', '')
            })
        
        return foods
    except Exception as e:
        print(f"Error searching USDA foods: {e}")
        return []

def get_usda_food_details(fdc_id: int) -> Optional[Dict]:
    """
    Get detailed nutrition information for a specific food
    Returns comprehensive nutrition data
    """
    api_key = get_usda_api_key()
    url = f"{USDA_API_BASE_URL}/food/{fdc_id}"
    
    params = {
        'api_key': api_key,
        'format': 'full',
        'nutrients': '203,204,205,208,269'  # Protein, Fat, Carbs, Calories, Sugar
    }
    
    print(f"🔍 Getting details for FDC ID: {fdc_id}")
    print(f"🌐 URL: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ USDA API response received")
        print(f"📊 Food name: {data.get('description', 'Unknown')}")
        print(f"📊 Nutrients found: {len(data.get('foodNutrients', []))}")
        
        # Extract nutrition data
        nutrition_data = {
            'fdc_id': fdc_id,
            'name': data.get('description', ''),
            'brand': data.get('brandOwner', ''),
            'category': data.get('foodCategory', ''),
            'serving_size': 100,  # Default to 100g
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'fiber': 0,
            'sugar': 0,
            'sodium': 0,
            'vitamin_c': 0,
            'calcium': 0,
            'iron': 0
        }
        
        # Process nutrients
        for nutrient in data.get('foodNutrients', []):
            nutrient_id = nutrient.get('nutrient', {}).get('id')
            value = nutrient.get('amount', 0)
            nutrient_name = nutrient.get('nutrient', {}).get('name', 'Unknown')
            
            print(f"📊 Processing nutrient: {nutrient_name} (ID: {nutrient_id}) = {value}")
            
            # Map nutrient IDs to our fields (updated based on actual USDA API response)
            if nutrient_id == 1003:  # Protein
                nutrition_data['protein'] = int(round(value))
                print(f"✅ Protein: {nutrition_data['protein']}")
            elif nutrient_id == 1004:  # Total lipid (fat)
                nutrition_data['fat'] = int(round(value))
                print(f"✅ Fat: {nutrition_data['fat']}")
            elif nutrient_id == 1005:  # Carbohydrate
                nutrition_data['carbs'] = int(round(value))
                print(f"✅ Carbs: {nutrition_data['carbs']}")
            elif nutrient_id == 2000:  # Total Sugars
                nutrition_data['sugar'] = int(round(value))
                print(f"✅ Sugar: {nutrition_data['sugar']}")
            # Also check for alternative IDs
            elif nutrient_id == 203:  # Protein (alternative)
                nutrition_data['protein'] = int(round(value))
                print(f"✅ Protein (alt): {nutrition_data['protein']}")
            elif nutrient_id == 204:  # Total lipid (fat) (alternative)
                nutrition_data['fat'] = int(round(value))
                print(f"✅ Fat (alt): {nutrition_data['fat']}")
            elif nutrient_id == 205:  # Carbohydrate (alternative)
                nutrition_data['carbs'] = int(round(value))
                print(f"✅ Carbs (alt): {nutrition_data['carbs']}")
            elif nutrient_id == 208:  # Energy (kcal) (alternative)
                nutrition_data['calories'] = int(round(value))
                print(f"✅ Calories: {nutrition_data['calories']}")
            elif nutrient_id == 291:  # Fiber
                nutrition_data['fiber'] = int(round(value))
            elif nutrient_id == 269:  # Sugars (alternative)
                nutrition_data['sugar'] = int(round(value))
            elif nutrient_id == 307:  # Sodium
                nutrition_data['sodium'] = int(round(value))
            elif nutrient_id == 401:  # Vitamin C
                nutrition_data['vitamin_c'] = int(round(value))
            elif nutrient_id == 301:  # Calcium
                nutrition_data['calcium'] = int(round(value))
            elif nutrient_id == 303:  # Iron
                nutrition_data['iron'] = int(round(value))
        
        # Calculate calories if not found (4 calories per gram of protein/carbs, 9 per gram of fat)
        if nutrition_data['calories'] == 0:
            calculated_calories = (nutrition_data['protein'] * 4) + (nutrition_data['carbs'] * 4) + (nutrition_data['fat'] * 9)
            nutrition_data['calories'] = int(round(calculated_calories))
            print(f"📊 Calculated calories: {nutrition_data['calories']} (protein: {nutrition_data['protein']}g, carbs: {nutrition_data['carbs']}g, fat: {nutrition_data['fat']}g)")
        
        print(f"📊 Final nutrition data: {nutrition_data}")
        return nutrition_data
        
    except Exception as e:
        print(f"Error getting USDA food details: {e}")
        return None

# Initialize food classification model
FOOD_MODEL_NAME = "Kaludi/food-category-classification-v2.0"
food_processor = None
food_model = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_food_classification_model():
    """Load the food classification model from Hugging Face"""
    global food_processor, food_model
    try:
        print(f"Loading food classification model: {FOOD_MODEL_NAME}")
        food_processor = AutoImageProcessor.from_pretrained(FOOD_MODEL_NAME)
        food_model = AutoModelForImageClassification.from_pretrained(FOOD_MODEL_NAME)
        food_model.to(device)
        food_model.eval()
        print("Food classification model loaded successfully")
    except Exception as e:
        print(f"Error loading food classification model: {e}")
        # Fallback to a simpler model
        try:
            fallback_model = "Shresthadev403/food-image-classification"
            print(f"Loading fallback model: {fallback_model}")
            food_processor = AutoImageProcessor.from_pretrained(fallback_model)
            food_model = AutoModelForImageClassification.from_pretrained(fallback_model)
            food_model.to(device)
            food_model.eval()
            print("Fallback food classification model loaded successfully")
        except Exception as e2:
            print(f"Error loading fallback model: {e2}")
            food_processor = None
            food_model = None

def classify_food_image(image_data: bytes) -> Dict:
    """
    Classify food in an image using Hugging Face model
    Returns the detected food type and confidence
    """
    if food_model is None or food_processor is None:
        return {"error": "Food classification model not loaded"}
    
    try:
        # Convert bytes to PIL Image
        from PIL import Image
        image = Image.open(io.BytesIO(image_data))
        
        # Preprocess image
        inputs = food_processor(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Get predictions
        with torch.no_grad():
            outputs = food_model(**inputs)
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1)
        
        # Get top predictions
        top_probs, top_indices = torch.topk(probabilities, 3)
        
        predictions = []
        for i in range(len(top_indices[0])):
            label_id = top_indices[0][i].item()
            confidence = top_probs[0][i].item()
            label = food_model.config.id2label.get(label_id, f"class_{label_id}")
            predictions.append({
                "food_type": label,
                "confidence": confidence,
                "label_id": label_id
            })
        
        return {
            "success": True,
            "predictions": predictions,
            "top_prediction": predictions[0] if predictions else None
        }
        
    except Exception as e:
        print(f"Error classifying food image: {e}")
        return {"error": f"Error classifying image: {str(e)}"}

def search_usda_foods_enhanced(query: str, max_results: int = 5) -> List[Dict]:
    """
    Enhanced search for foods in USDA database with better matching
    """
    api_key = get_usda_api_key()
    url = f"{USDA_API_BASE_URL}/foods/search"
    
    params = {
        'api_key': api_key,
        'query': query,
        'pageSize': max_results,
        'dataType': ['Foundation', 'SR Legacy'],
        'sortBy': 'dataType.keyword',
        'sortOrder': 'asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        foods = []
        for food in data.get('foods', []):
            # Extract nutrition info if available
            nutrition_info = {}
            for nutrient in food.get('foodNutrients', []):
                nutrient_id = nutrient.get('nutrientId')
                if nutrient_id == 203:  # Protein
                    nutrition_info['protein'] = nutrient.get('value', 0)
                elif nutrient_id == 204:  # Fat
                    nutrition_info['fat'] = nutrient.get('value', 0)
                elif nutrient_id == 205:  # Carbohydrates
                    nutrition_info['carbs'] = nutrient.get('value', 0)
                elif nutrient_id == 208:  # Calories
                    nutrition_info['calories'] = nutrient.get('value', 0)
            
            foods.append({
                'fdc_id': food.get('fdcId'),
                'name': food.get('description', ''),
                'brand': food.get('brandOwner', ''),
                'category': food.get('foodCategory', ''),
                'data_type': food.get('dataType', ''),
                'published_date': food.get('publishedDate', ''),
                'nutrition': nutrition_info
            })
        
        return foods
    except Exception as e:
        print(f"Error searching USDA foods: {e}")
        return []

def get_food_nutrition_from_usda(food_name: str) -> Optional[Dict]:
    """
    Get nutrition information for a food from USDA database
    Returns the first matching food with complete nutrition data
    """
    try:
        # Search for the food
        foods = search_usda_foods_enhanced(food_name, max_results=10)
        
        if not foods:
            return None
        
        # Find the first food with complete nutrition data
        for food in foods:
            nutrition = food.get('nutrition', {})
            if nutrition.get('calories') and nutrition.get('protein') is not None:
                return {
                    'fdc_id': food['fdc_id'],
                    'name': food['name'],
                    'brand': food['brand'],
                    'calories': nutrition.get('calories', 0),
                    'protein': nutrition.get('protein', 0),
                    'carbs': nutrition.get('carbs', 0),
                    'fat': nutrition.get('fat', 0),
                    'source': 'USDA'
                }
        
        # If no complete nutrition data, return the first result with partial data
        if foods:
            first_food = foods[0]
            nutrition = first_food.get('nutrition', {})
            return {
                'fdc_id': first_food['fdc_id'],
                'name': first_food['name'],
                'brand': first_food['brand'],
                'calories': nutrition.get('calories', 0),
                'protein': nutrition.get('protein', 0),
                'carbs': nutrition.get('carbs', 0),
                'fat': nutrition.get('fat', 0),
                'source': 'USDA (partial data)'
            }
        
        return None
        
    except Exception as e:
        print(f"Error getting nutrition from USDA: {e}")
        return None

def analyze_food_photo_enhanced(image_data: bytes) -> Dict:
    """
    Enhanced food photo analysis using Hugging Face model + USDA database
    """
    try:
        # Step 1: Classify the food using the Hugging Face model
        classification_result = classify_food_image(image_data)
        
        if "error" in classification_result:
            return classification_result
        
        # Step 2: Get the top prediction
        top_prediction = classification_result.get("top_prediction")
        if not top_prediction:
            return {"error": "No food detected in image"}
        
        detected_food_type = top_prediction["food_type"]
        confidence = top_prediction["confidence"]
        
        # Step 3: Search USDA database for the detected food
        nutrition_data = get_food_nutrition_from_usda(detected_food_type)
        
        if nutrition_data:
            return {
                "success": True,
                "detected_food": detected_food_type,
                "confidence": confidence,
                "nutrition": nutrition_data,
                "analysis_method": "AI + USDA Database"
            }
        else:
            # Fallback to estimated nutrition based on food type
            estimated_nutrition = get_estimated_nutrition(detected_food_type)
            return {
                "success": True,
                "detected_food": detected_food_type,
                "confidence": confidence,
                "nutrition": estimated_nutrition,
                "analysis_method": "AI + Estimated Nutrition"
            }
            
    except Exception as e:
        print(f"Error in enhanced food analysis: {e}")
        return {"error": f"Analysis failed: {str(e)}"}

def get_estimated_nutrition(food_type: str) -> Dict:
    """
    Get estimated nutrition for common food types
    """
    # Common food nutrition estimates (per 100g)
    food_nutrition = {
        "apple": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2},
        "banana": {"calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3},
        "orange": {"calories": 47, "protein": 0.9, "carbs": 12, "fat": 0.1},
        "bread": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3.2},
        "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
        "chicken": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
        "beef": {"calories": 250, "protein": 26, "carbs": 0, "fat": 15},
        "fish": {"calories": 100, "protein": 20, "carbs": 0, "fat": 2.5},
        "pasta": {"calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
        "pizza": {"calories": 266, "protein": 11, "carbs": 33, "fat": 10},
        "salad": {"calories": 20, "protein": 2, "carbs": 4, "fat": 0.2},
        "soup": {"calories": 50, "protein": 3, "carbs": 8, "fat": 1},
        "sandwich": {"calories": 300, "protein": 15, "carbs": 35, "fat": 12},
        "cake": {"calories": 257, "protein": 4, "carbs": 45, "fat": 8},
        "cookie": {"calories": 502, "protein": 6, "carbs": 65, "fat": 24},
        "ice cream": {"calories": 207, "protein": 3.5, "carbs": 24, "fat": 11},
        "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fat": 1},
        "cheese": {"calories": 113, "protein": 7, "carbs": 1, "fat": 9},
        "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11},
        "potato": {"calories": 77, "protein": 2, "carbs": 17, "fat": 0.1}
    }
    
    # Try to find a match (case insensitive)
    food_type_lower = food_type.lower()
    for food_name, nutrition in food_nutrition.items():
        if food_name in food_type_lower or food_type_lower in food_name:
            return {
                "name": food_type,
                "calories": nutrition["calories"],
                "protein": nutrition["protein"],
                "carbs": nutrition["carbs"],
                "fat": nutrition["fat"],
                "source": "Estimated"
            }
    
    # Default nutrition for unknown foods
    return {
        "name": food_type,
        "calories": 200,
        "protein": 8,
        "carbs": 25,
        "fat": 8,
        "source": "Estimated (default)"
    }

def search_and_get_nutrition(food_name: str) -> Optional[Dict]:
    """
    Search for food and get nutrition data in one call
    Returns nutrition data for the best match
    """
    print(f"🔍 Searching for nutrition data for: {food_name}")
    
    # Search for foods
    foods = search_usda_foods(food_name, max_results=3)
    print(f"📊 Found {len(foods)} foods in search")
    
    if not foods:
        print("❌ No foods found in search")
        return None
    
    # Get details for the first (best) match
    best_match = foods[0]
    print(f"🎯 Best match: {best_match['name']} (FDC ID: {best_match['fdc_id']})")
    
    nutrition_data = get_usda_food_details(best_match['fdc_id'])
    
    if nutrition_data:
        nutrition_data['search_name'] = food_name
        nutrition_data['matched_name'] = best_match['name']
        nutrition_data['confidence'] = 0.9  # High confidence for USDA data
        print(f"✅ Nutrition data retrieved: {nutrition_data['name']}")
        print(f"📊 Calories: {nutrition_data['calories']}, Protein: {nutrition_data['protein']}, Carbs: {nutrition_data['carbs']}, Fat: {nutrition_data['fat']}")
    else:
        print("❌ Could not get nutrition details")
    
    return nutrition_data

def get_fallback_nutrition(food_name: str) -> Dict:
    """
    Fallback nutrition data when USDA lookup fails
    Returns estimated nutrition based on food type
    """
    food_name_lower = food_name.lower()
    
    # Simple food type detection and estimation
    if any(word in food_name_lower for word in ['apple', 'banana', 'orange', 'fruit']):
        return {
            'name': food_name,
            'calories': 60,
            'protein': 1,
            'carbs': 15,
            'fat': 0,
            'fiber': 2,
            'confidence': 0.3
        }
    elif any(word in food_name_lower for word in ['chicken', 'beef', 'pork', 'meat', 'steak']):
        return {
            'name': food_name,
            'calories': 250,
            'protein': 25,
            'carbs': 0,
            'fat': 15,
            'fiber': 0,
            'confidence': 0.3
        }
    elif any(word in food_name_lower for word in ['bread', 'pasta', 'rice', 'grain']):
        return {
            'name': food_name,
            'calories': 250,
            'protein': 8,
            'carbs': 45,
            'fat': 2,
            'fiber': 3,
            'confidence': 0.3
        }
    elif any(word in food_name_lower for word in ['vegetable', 'broccoli', 'carrot', 'salad']):
        return {
            'name': food_name,
            'calories': 30,
            'protein': 2,
            'carbs': 6,
            'fat': 0,
            'fiber': 2,
            'confidence': 0.3
        }
    else:
        # Generic fallback
        return {
            'name': food_name,
            'calories': 200,
            'protein': 8,
            'carbs': 25,
            'fat': 8,
            'fiber': 2,
            'confidence': 0.2
        }

# Import AI meal planner
try:
    from ai_meal_planner import meal_planner
except ImportError:
    meal_planner = None
    print("Warning: AI meal planner not available. Install required dependencies.")

# Helper function to convert non-serializable objects to JSON-serializable format
def convert_for_json(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, timedelta):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(item) for item in obj]
    else:
        return obj

app = FastAPI(title="Gym Management Platform")

# Configure templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware with more specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include food detection routes if available
if FOOD_DETECT_AVAILABLE:
    app.include_router(food_detect_router)
    print("✅ Food detection routes included")
else:
    print("⚠️ Food detection routes not available")

security = HTTPBasic()

# Store active sessions
active_sessions = {}

# Add membership prices configuration
MEMBERSHIP_PRICES = {
    "Basic": 50.00,    # $50 per month
    "Premium": 100.00, # $100 per month
    "VIP": 200.00      # $200 per month
}

# Add exercise types configuration
EXERCISE_TYPES = [
    "Barbell Biceps Curl",
    "Bench Press",
    "Chest Fly Machine",
    "Deadlift",
    "Decline Bench Press",
    "Hammer Curl",
    "Hip Thrust",
    "Incline Bench Press",
    "Lat Pulldown",
    "Lateral Raises",
    "Leg Extension",
    "Leg Raises",
    "Plank",
    "Pull Up",
    "Push Up",
    "Romanian Deadlift",
    "Russian Twist",
    "Shoulder Press",
    "Squat",
    "T Bar Row",
    "Tricep Dips",
    "Tricep Pushdown"
]

# Add workout templates
WORKOUT_TEMPLATES = {
    "Upper Body": [
        "Bench Press",
        "Shoulder Press",
        "Lat Pulldown",
        "Tricep Pushdown",
        "Barbell Biceps Curl",
        "Lateral Raises"
    ],
    "Lower Body": [
        "Squat",
        "Deadlift",
        "Leg Extension",
        "Hip Thrust",
        "Romanian Deadlift",
        "Leg Raises"
    ],
    "Full Body": [
        "Bench Press",
        "Squat",
        "Pull Up",
        "Deadlift",
        "Shoulder Press",
        "Plank"
    ],
    "Core": [
        "Plank",
        "Russian Twist",
        "Leg Raises",
        "Push Up",
        "Pull Up",
        "T Bar Row"
    ],
    "Push": [
        "Bench Press",
        "Shoulder Press",
        "Incline Bench Press",
        "Tricep Dips",
        "Tricep Pushdown",
        "Push Up"
    ],
    "Pull": [
        "Lat Pulldown",
        "T Bar Row",
        "Pull Up",
        "Barbell Biceps Curl",
        "Hammer Curl",
        "Deadlift"
    ]
}

def get_current_user(request: Request) -> Optional[dict]:
    try:
        session_id = request.cookies.get("session_id")
        print(f"Session ID from cookie: {session_id}")  # Debug log
        if not session_id:
            print("No session ID found in cookies")  # Debug log
            return None
        
        user = active_sessions.get(session_id)
        print(f"User from session: {user}")  # Debug log
        print(f"Active sessions: {active_sessions}")  # Debug log
        return user
    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")  # Debug log
        return None

# FastAPI dependency version of get_current_user
def get_current_user_dependency(request: Request) -> dict:
    print(f"get_current_user_dependency called")  # Debug log
    user = get_current_user(request)
    print(f"User from get_current_user: {user}")  # Debug log
    if not user:
        print("No user found, raising 401")  # Debug log
        raise HTTPException(status_code=401, detail="Not authenticated")
    print(f"Returning user: {user}")  # Debug log
    return user

# Database connection
def get_db_connection():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "omaromar"),
        database=os.environ.get("DB_NAME", "trainer_app"),
        cursorclass=pymysql.cursors.DictCursor
    )



@app.get("/", response_class=HTMLResponse)
async def get_login_page():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PowerFit - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body class="bg-gray-100 h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-96">
        <div class="text-center mb-8">
            <div class="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <i class="fas fa-dumbbell text-white text-2xl"></i>
            </div>
            <h1 class="text-2xl font-bold text-gray-800">PowerFit</h1>
            <p class="text-gray-600">Sign in to your account</p>
        </div>
        
        <form id="loginForm" class="space-y-4">
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="email">
                    Email
                </label>
                <input class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-indigo-500"
                       type="email" id="email" name="email" required>
            </div>
            
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="password">
                    Password
                </label>
                <input class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-indigo-500"
                       type="password" id="password" name="password" required>
            </div>
            
            <div>
                <label class="block text-gray-700 text-sm font-bold mb-2" for="role">
                    Role
                </label>
                <select class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-indigo-500"
                        id="role" name="role" required>
                    <option value="">Select Role</option>
                    <option value="gym">Gym</option>
                    <option value="coach">Coach</option>
                    <option value="member">Member</option>
                </select>
            </div>
            
            <button type="submit"
                    class="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50">
                Sign In
            </button>
        </form>
        
        <div id="error-message" class="mt-4 text-red-500 text-center hidden"></div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const role = document.getElementById('role').value;
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password, role })
                });
                
                const data = await response.json();
                
                if (response.ok && data.status === 'success') {
                    // Redirect based on user type
                    switch(data.user.user_type) {
                        case 'coach':
                            window.location.href = '/coach/dashboard';
                            break;
                        case 'member':
                            window.location.href = '/member/dashboard';
                            break;
                        case 'gym':
                            window.location.href = '/gym/dashboard';
                            break;
                        default:
                            window.location.href = '/dashboard';
                    }
                } else {
                    const errorDiv = document.getElementById('error-message');
                    errorDiv.textContent = data.detail || 'Invalid credentials';
                    errorDiv.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Error:', error);
                const errorDiv = document.getElementById('error-message');
                errorDiv.textContent = 'An error occurred. Please try again.';
                errorDiv.classList.remove('hidden');
            }
        });
    </script>
</body>
</html>
    """

@app.post("/api/login")
async def login(request: Request):
    try:
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        
        print(f"Login attempt - Email: {email}, Role: {role}")  # Debug log
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:
            # Check in coaches table
            if role == "coach":
                print("Checking coach credentials...")  # Debug log
                cursor.execute("SELECT * FROM coaches WHERE email = %s", (email,))
                coach = cursor.fetchone()
                print(f"Found coach: {coach}")  # Debug log
                
                if coach and coach['password'] == password:
                    session_id = secrets.token_urlsafe(32)
                    user_data = {
                        "user_type": "coach",
                        "name": coach['name'],
                        "email": coach['email'],
                        "id": coach['id'],
                        "gym_id": coach.get('gym_id', None),
                        "specialization": coach.get('specialization', '')
                    }
                    active_sessions[session_id] = user_data
                    response = JSONResponse(content={"status": "success", "user": user_data})
                    response.set_cookie(key="session_id", value=session_id, httponly=True)
                    return response
                else:
                    print("Coach not found or password mismatch")  # Debug log
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid coach credentials"}
                    )
            
            # Check in members table
            if role == "member":
                cursor.execute("SELECT * FROM members WHERE email = %s AND password = %s", (email, password))
                member = cursor.fetchone()
                if member:
                    session_id = secrets.token_urlsafe(32)
                    user_data = {
                        "user_type": "member",
                        "name": member['name'],
                        "email": member['email'],
                        "id": member['id'],
                        "gym_id": member['gym_id'],
                        "membership_type": member.get('membership_type', 'Basic')
                    }
                    active_sessions[session_id] = user_data
                    response = JSONResponse(content={"status": "success", "user": user_data})
                    response.set_cookie(key="session_id", value=session_id, httponly=True)
                    return response
            
            # Check in gyms table
            if role == "gym":
                cursor.execute("SELECT * FROM gyms WHERE email = %s AND password = %s", (email, password))
                gym = cursor.fetchone()
                if gym:
                    session_id = secrets.token_urlsafe(32)
                    user_data = {
                        "user_type": "gym",
                        "name": gym['name'],
                        "email": gym['email'],
                        "id": gym['id']
                    }
                    active_sessions[session_id] = user_data
                    response = JSONResponse(content={"status": "success", "user": user_data})
                    response.set_cookie(key="session_id", value=session_id, httponly=True)
                    return response
            
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid credentials"}
            )
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Login error: {str(e)}")  # Debug log
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

# Member endpoints
@app.get("/api/member/{member_id}/sessions")
async def get_member_sessions(member_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT s.*, c.name as coach_name, g.name as gym_name
            FROM sessions s 
            JOIN coaches c ON s.coach_id = c.id 
            JOIN gyms g ON s.gym_id = g.id
            WHERE s.member_id = %s 
            ORDER BY s.session_date DESC, s.session_time DESC
        """, (member_id,))
        
        sessions = cursor.fetchall()
        return JSONResponse(content=sessions)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/member/{member_id}/coach")
async def get_member_coach(member_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT c.* 
            FROM coaches c 
            JOIN member_coach mc ON c.id = mc.coach_id 
            WHERE mc.member_id = %s
        """, (member_id,))
        
        coach = cursor.fetchone()
        return JSONResponse(content=coach if coach else {"detail": "No coach assigned"})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

# Coach endpoints
@app.get("/api/coach/{coach_id}/schedule")
async def get_coach_schedule(coach_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT s.*, m.name as member_name, g.name as gym_name
            FROM sessions s 
            JOIN members m ON s.member_id = m.id 
            JOIN gyms g ON s.gym_id = g.id
            WHERE s.coach_id = %s 
            ORDER BY s.session_date, s.session_time
        """, (coach_id,))
        
        schedule = cursor.fetchall()
        return JSONResponse(content=schedule)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/coach/members")
async def get_coach_members(
    search: str = "",
    membership_type: str = "all",
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query
        query = """
            SELECT m.*, 
                   COUNT(s.id) as total_sessions,
                   SUM(CASE WHEN s.status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                   MAX(CASE WHEN s.status = 'Completed' THEN s.session_date ELSE NULL END) as last_session
            FROM members m 
            JOIN member_coach mc ON m.id = mc.member_id 
            LEFT JOIN sessions s ON m.id = s.member_id
            WHERE mc.coach_id = %s
        """
        params = [current_user["id"]]
        
        # Add search condition
        if search:
            query += " AND (m.name LIKE %s OR m.email LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        # Add membership type filter
        if membership_type != "all":
            query += " AND m.membership_type = %s"
            params.append(membership_type)
        
        # Group by member
        query += " GROUP BY m.id ORDER BY m.name"
        
        cursor.execute(query, params)
        members = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return members
    except Exception as e:
        print(f"Error in get_coach_members: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving members")

@app.get("/api/coach/sessions")
async def get_coach_sessions(
    dateRange: str = "all",
    status: str = "all",
    member: str = "all",
    search: str = "",
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query
        query = """
            SELECT s.*, 
                   m.name as member_name, m.email as member_email,
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.coach_id = %s
        """
        params = [current_user["id"]]
        
        # Add date range filter
        if dateRange != "all":
            if dateRange == "today":
                query += " AND s.session_date = CURDATE()"
            elif dateRange == "week":
                query += " AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
            elif dateRange == "month":
                query += " AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        
        # Add status filter
        if status != "all":
            query += " AND s.status = %s"
            params.append(status)
        
        # Add member filter
        if member != "all":
            query += " AND s.member_id = %s"
            params.append(member)
        
        # Add search condition
        if search:
            query += " AND (m.name LIKE %s OR m.email LIKE %s OR s.notes LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
        # Order by date and time
        query += " ORDER BY s.session_date DESC, s.session_time DESC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Format session data
        formatted_sessions = []
        for session in sessions:
            # Parse workout notes
            workout_type = "Custom"
            exercises = []
            if session["notes"]:
                try:
                    # Extract workout type and exercises from notes
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except:
                    pass
            
            formatted_sessions.append({
                "id": session["id"],
                "member": {
                    "name": session["member_name"],
                    "email": session["member_email"]
                },
                "date": session["formatted_date"],
                "time": session["formatted_time"],
                "duration": session["duration"],
                "status": session["status"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "notes": session["notes"]
            })
        
        cursor.close()
        conn.close()
        
        return formatted_sessions
    except Exception as e:
        print(f"Error in get_coach_sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving sessions")

@app.put("/api/coach/sessions/{session_id}/status")
async def update_session_status(
    session_id: int,
    status: str,
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    if status not in ["scheduled", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if session exists and belongs to coach
        cursor.execute(
            "SELECT id FROM sessions WHERE id = %s AND coach_id = %s",
            [session_id, current_user["id"]]
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update session status
        cursor.execute(
            "UPDATE sessions SET status = %s WHERE id = %s",
            [status, session_id]
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Session status updated successfully"}
    except Exception as e:
        print(f"Error in update_session_status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating session status")

@app.get("/api/coach/progress")
async def get_coach_progress(
    time_range: str = "month",
    current_user: dict = Depends(get_current_user_dependency)
):
    # Redirect to the member-specific endpoint with member_id=0 (all members)
    return await get_member_progress(0, time_range, current_user)

@app.get("/api/coach/progress/{member_id}")
async def get_member_progress(
    member_id: int,
    time_range: str = "month",
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"Fetching progress for member {member_id} with coach {current_user['id']}")
        
        # Calculate date range
        date_condition = ""
        if time_range == "week":
            date_condition = "AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif time_range == "month":
            date_condition = "AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        elif time_range == "quarter":
            date_condition = "AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)"
        elif time_range == "year":
            date_condition = "AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
        
        # Base query conditions
        member_condition = "AND s.member_id = %s" if member_id != 0 else ""
        member_params = [current_user["id"]]
        if member_id != 0:
            member_params.append(member_id)
        
        # Get session statistics
        stats_query = """
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled_sessions
            FROM sessions s
            JOIN member_coach mc ON s.member_id = mc.member_id
            WHERE mc.coach_id = %s """ + member_condition + " " + date_condition
        
        print(f"Stats query: {stats_query}")  # Debug log
        print(f"Stats params: {member_params}")  # Debug log
        cursor.execute(stats_query, tuple(member_params))
        stats = cursor.fetchone()
        print(f"Stats result: {stats}")  # Debug log
        
        # Calculate attendance rate
        total_sessions = stats["total_sessions"] or 0
        completed_sessions = stats["completed_sessions"] or 0
        attendance_rate = round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0)
        
        # Get most common workout type
        workout_query = """
            SELECT 
                TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(notes, 'Workout Type:', -1), CHAR(10), 1)) as workout_type,
                COUNT(*) as count
            FROM sessions s
            JOIN member_coach mc ON s.member_id = mc.member_id
            WHERE mc.coach_id = %s """ + member_condition + """ AND notes LIKE '%%Workout Type:%%' """ + date_condition + """
            GROUP BY workout_type
            ORDER BY count DESC
            LIMIT 1
        """
        
        print(f"Workout query: {workout_query}")  # Debug log
        cursor.execute(workout_query, tuple(member_params))
        common_workout = cursor.fetchone()
        print(f"Common workout result: {common_workout}")  # Debug log
        
        # Get session history
        history_query = """
            SELECT 
                DATE_FORMAT(session_date, '%%Y-%%m-%%d') as date,
                COUNT(*) as count
            FROM sessions s
            JOIN member_coach mc ON s.member_id = mc.member_id
            WHERE mc.coach_id = %s """ + member_condition + " " + date_condition + """
            GROUP BY session_date
            ORDER BY session_date
        """
        
        print(f"History query: {history_query}")  # Debug log
        cursor.execute(history_query, tuple(member_params))
        session_history = cursor.fetchall()
        print(f"Session history result: {session_history}")  # Debug log
        
        # Get workout distribution
        distribution_query = """
            SELECT 
                TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(notes, 'Workout Type:', -1), CHAR(10), 1)) as workout_type,
                COUNT(*) as count
            FROM sessions s
            JOIN member_coach mc ON s.member_id = mc.member_id
            WHERE mc.coach_id = %s """ + member_condition + """ AND notes LIKE '%%Workout Type:%%' """ + date_condition + """
            GROUP BY workout_type
            ORDER BY count DESC
        """
        
        print(f"Distribution query: {distribution_query}")  # Debug log
        cursor.execute(distribution_query, tuple(member_params))
        workout_distribution = cursor.fetchall()
        print(f"Workout distribution result: {workout_distribution}")  # Debug log
        
        # Get recent sessions
        sessions_query = """
            SELECT 
                s.*,
                m.name as member_name,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN member_coach mc ON s.member_id = mc.member_id
            JOIN members m ON s.member_id = m.id
            WHERE mc.coach_id = %s """ + member_condition + " " + date_condition + """
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """
        
        print(f"Sessions query: {sessions_query}")  # Debug log
        cursor.execute(sessions_query, tuple(member_params))
        recent_sessions = cursor.fetchall()
        print(f"Recent sessions result: {recent_sessions}")  # Debug log
        
        # If no data found, create some test data
        if not session_history:
            print("No data found, creating test data")
            today = datetime.now().date()
            session_history = [
                {"date": (today - timedelta(days=i)).strftime("%Y-%m-%d"), "count": random.randint(1, 3)}
                for i in range(7)
            ]
            workout_distribution = [
                {"workout_type": "Upper Body", "count": 5},
                {"workout_type": "Lower Body", "count": 3},
                {"workout_type": "Full Body", "count": 2}
            ]
            recent_sessions = [
                {
                    "formatted_date": (today - timedelta(days=i)).strftime("%Y-%m-%d"),
                    "formatted_time": "10:00",
                    "status": "Completed",
                    "notes": f"Workout Type: {wt}\n1. Exercise 1\n2. Exercise 2",
                    "member_name": "Test Member"
                }
                for i, wt in enumerate(["Upper Body", "Lower Body", "Full Body"])
            ]
            completed_sessions = 8
            attendance_rate = 80
            common_workout = {"workout_type": "Upper Body"}
        
        # Format recent sessions
        formatted_recent_sessions = []
        for session in recent_sessions:
            workout_type = "Custom"
            exercises = []
            if session["notes"]:
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except Exception as e:
                    print(f"Error parsing notes: {str(e)}")
            
            formatted_recent_sessions.append({
                "date": session["formatted_date"],
                "member_name": session["member_name"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "status": session["status"],
                "notes": session["notes"]
            })
        
        cursor.close()
        conn.close()
        
        response_data = {
            "sessions_completed": completed_sessions,
            "attendance_rate": attendance_rate,
            "common_workout": common_workout["workout_type"] if common_workout else "No workouts",
            "session_history": {
                "labels": [entry["date"] for entry in session_history],
                "values": [entry["count"] for entry in session_history]
            },
            "workout_distribution": {
                "labels": [entry["workout_type"] for entry in workout_distribution],
                "values": [entry["count"] for entry in workout_distribution]
            },
            "recent_sessions": formatted_recent_sessions
        }
        
        print(f"Returning response data: {response_data}")
        return response_data
        
    except Exception as e:
        print(f"Error in get_member_progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving member progress: {str(e)}")

# Gym routes
@app.get("/gym/dashboard", response_class=HTMLResponse)
async def get_gym_dashboard_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    
    # Get gym details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym details
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym_details = cursor.fetchone()
        
        # Return the dashboard page template with gym details
        return templates.TemplateResponse(
            "gym/dashboard.html",
            {
                "request": request,
                "gym": gym_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting gym dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/gym/members", response_class=HTMLResponse)
async def get_gym_members_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    
    # Get gym details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym details
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym_details = cursor.fetchone()
        
        # Return the members page template with gym details
        return templates.TemplateResponse(
            "gym/members.html",
            {
                "request": request,
                "gym": gym_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting gym members page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/gym/coaches", response_class=HTMLResponse)
async def get_gym_coaches_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    
    # Get gym details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym details
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym_details = cursor.fetchone()
        
        # Return the coaches page template with gym details
        return templates.TemplateResponse(
            "gym/coaches.html",
            {
                "request": request,
                "gym": gym_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting gym coaches page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/gym/sessions", response_class=HTMLResponse)
async def get_gym_sessions_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    
    # Get gym details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym details
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym_details = cursor.fetchone()
        
        # Return the sessions page template with gym details
        return templates.TemplateResponse(
            "gym/sessions.html",
            {
                "request": request,
                "gym": gym_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting gym sessions page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Gym API endpoints
@app.get("/api/gym/dashboard")
async def get_gym_dashboard(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym info
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym = cursor.fetchone()
        
        # Get stats with proper revenue calculation (membership fees only)
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM members WHERE gym_id = %s) as total_members,
                (SELECT COUNT(*) FROM coaches WHERE gym_id = %s AND status = 'Active') as active_coaches,
                (SELECT COUNT(*) FROM sessions WHERE gym_id = %s AND DATE(session_date) = CURDATE()) as today_sessions,
                (
                    -- Calculate total monthly revenue from all active members
                    SELECT COALESCE(SUM(
                        CASE 
                            WHEN m.membership_type = 'Basic' THEN 50.00
                            WHEN m.membership_type = 'Premium' THEN 100.00
                            WHEN m.membership_type = 'VIP' THEN 150.00
                        END
                    ), 0)
                    FROM members m
                    WHERE m.gym_id = %s
                ) as monthly_revenue
        """, (user["id"], user["id"], user["id"], user["id"]))
        stats = cursor.fetchone()
        
        # Get recent members
        cursor.execute("""
            SELECT * FROM members 
            WHERE gym_id = %s 
            ORDER BY join_date DESC 
            LIMIT 5
        """, (user["id"],))
        recent_members = cursor.fetchall()
        
        # Get recent sessions
        cursor.execute("""
            SELECT s.*, m.name as member_name,
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.gym_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """, (user["id"],))
        recent_sessions = cursor.fetchall()
        
        return {
            "gym": gym,
            "stats": stats,
            "recent_members": recent_members,
            "recent_sessions": recent_sessions
        }
    except Exception as e:
        print(f"Error getting gym dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Member API Endpoints
@app.get("/member/dashboard", response_class=HTMLResponse)
async def get_member_dashboard_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    
    # Get member details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get member details
        cursor.execute("""
            SELECT m.*, c.name as coach_name, c.specialization, c.email as coach_email
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            WHERE m.id = %s
        """, (user["id"],))
        member_details = cursor.fetchone()
        
        # Return the dashboard page template with member details
        return templates.TemplateResponse(
            "member/dashboard.html",
            {
                "request": request,
                "member": member_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting member dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/member/nutrition", response_class=HTMLResponse)
async def get_member_nutrition_page(request: Request):
    """Serve the AI Calorie Tracker page for VIP and Premium members"""
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    
    # Check VIP or Premium membership
    membership_type = user.get('membership_type', 'Basic')
    print(f"DEBUG: User {user.get('name')} has membership type: {membership_type}")
    
    if membership_type not in ['VIP', 'Premium']:
        print(f"DEBUG: Access denied for membership type: {membership_type}")
        return RedirectResponse(url="/member/dashboard")
    
    print(f"DEBUG: Access granted for {membership_type} member")
    return templates.TemplateResponse(
        "member/nutrition.html",
        {
            "request": request,
            "user": user
        }
    )

@app.get("/api/member/dashboard")
async def get_member_dashboard(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get member info
        cursor.execute("""
            SELECT m.*, c.name as coach_name, c.specialization, c.email as coach_email
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            WHERE m.id = %s
        """, (user["id"],))
        member = cursor.fetchone()
        
        # Get comprehensive stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                SUM(CASE WHEN session_date >= CURDATE() THEN 1 ELSE 0 END) as upcoming_sessions,
                SUM(CASE WHEN session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as week_sessions,
                SUM(CASE WHEN status = 'Completed' AND session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as week_completed_sessions
            FROM sessions
            WHERE member_id = %s
        """, (user["id"],))
        stats = cursor.fetchone()
        
        # Calculate streak (consecutive days with completed sessions)
        cursor.execute("""
            SELECT COUNT(DISTINCT session_date) as streak_days
            FROM (
                SELECT session_date,
                       ROW_NUMBER() OVER (ORDER BY session_date DESC) as rn,
                       DATE_SUB(session_date, INTERVAL ROW_NUMBER() OVER (ORDER BY session_date DESC) DAY) as grp
                FROM sessions 
                WHERE member_id = %s AND status = 'Completed'
                ORDER BY session_date DESC
            ) t
            WHERE grp = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
        """, (user["id"],))
        streak_result = cursor.fetchone()
        streak_days = streak_result['streak_days'] if streak_result else 0
        
        # Calculate progress percentage (completed vs total sessions this week)
        week_progress = 0
        if stats['week_sessions'] and stats['week_sessions'] > 0:
            week_progress = round((stats['week_completed_sessions'] / stats['week_sessions']) * 100)
        
        # Get recent sessions
        cursor.execute("""
            SELECT s.*, 
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            WHERE s.member_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """, (user["id"],))
        recent_sessions = cursor.fetchall()
        
        return {
            "member": member,
            "stats": {
                **stats,
                "streak_days": streak_days,
                "week_progress": week_progress
            },
            "coach": {
                "name": member["coach_name"],
                "specialization": member["specialization"],
                "email": member["coach_email"]
            } if member["coach_name"] else None,
            "recent_sessions": recent_sessions
        }
    except Exception as e:
        print(f"Error getting member dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Gym API Endpoints
@app.get("/api/gym/sessions")
async def get_gym_sessions(
    request: Request,
    date: str = None,
    member: str = None,
    coach: str = None,
    status: str = None
):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Base query with explicit field selection
        query = """
            SELECT 
                s.id,
                s.member_id,
                s.coach_id,
                s.session_date,
                s.session_time,
                s.duration,
                s.status,
                s.notes,
                m.name as member_name,
                m.email as member_email,
                m.membership_type,
                c.name as coach_name,
                c.specialization as coach_specialization,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            INNER JOIN members m ON s.member_id = m.id
            INNER JOIN coaches c ON s.coach_id = c.id
            WHERE s.gym_id = %s
        """
        params = [user["id"]]
        
        # Add filters
        if date:
            query += " AND s.session_date = %s"
            params.append(date)
        
        if member:
            query += " AND m.name LIKE %s"
            params.append(f"%{member}%")
        
        if coach:
            query += " AND c.name LIKE %s"
            params.append(f"%{coach}%")
        
        if status and status != 'all':
            query += " AND s.status = %s"
            params.append(status)
        
        # Add order by
        query += " ORDER BY s.session_date DESC, s.session_time DESC"
        
        print(f"Executing query: {query}")  # Debug log
        print(f"With params: {params}")  # Debug log
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        print(f"Found {len(sessions)} sessions")  # Debug log
        
        # Format the response
        formatted_sessions = []
        for session in sessions:
            try:
                print(f"Processing session: {session}")  # Debug log
                
                # Ensure all required fields are present
                if not all(key in session for key in ['id', 'member_id', 'coach_id', 'session_date', 'session_time', 'duration', 'status', 'notes']):
                    print(f"Missing required fields in session: {session}")
                    continue
                
                # Parse the workout notes to get exercise list
                exercises = []
                workout_type = "Custom"
                if session["notes"]:
                    try:
                        lines = session["notes"].split('\n')
                        if lines and "Workout Type:" in lines[0]:
                            workout_type = lines[0].split("Workout Type:")[1].strip()
                        else:
                            workout_type = lines[0].replace(' Workout:', '') if lines else "Custom"
                        exercises = [line.strip() for line in lines[1:] if line.strip()]
                    except Exception as e:
                        print(f"Error parsing notes: {str(e)}")
                
                # Create formatted session with explicit type conversion
                formatted_session = {
                    "id": int(session["id"]),
                    "member": {
                        "id": int(session["member_id"]),
                        "name": str(session["member_name"]),
                        "email": str(session["member_email"]),
                        "membership_type": str(session["membership_type"])
                    },
                    "coach": {
                        "id": int(session["coach_id"]),
                        "name": str(session["coach_name"]),
                        "specialization": str(session["coach_specialization"])
                    },
                    "date": str(session["formatted_date"]),
                    "time": str(session["formatted_time"]),
                    "duration": int(session["duration"]),
                    "status": str(session["status"]),
                    "workout": {
                        "type": str(workout_type),
                        "exercises": [str(ex) for ex in exercises]
                    }
                }
                
                # Validate the formatted session
                if all(formatted_session.values()):
                    formatted_sessions.append(formatted_session)
                else:
                    print(f"Invalid formatted session: {formatted_session}")
                
            except Exception as e:
                print(f"Error formatting session: {str(e)}")
                continue
        
        print(f"Returning {len(formatted_sessions)} formatted sessions")  # Debug log
        return formatted_sessions
        
    except Exception as e:
        print(f"Error getting gym sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/gym/coaches")
async def get_gym_coaches(
    request: Request,
    search: str = None,
    specialization: str = None,
    status: str = None
):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Base query
        query = """
            SELECT 
                c.*,
                COUNT(DISTINCT mc.member_id) as total_members,
                COUNT(DISTINCT s.id) as total_sessions,
                COUNT(DISTINCT CASE WHEN s.status = 'Completed' THEN s.id END) as completed_sessions
            FROM coaches c
            LEFT JOIN member_coach mc ON c.id = mc.coach_id
            LEFT JOIN sessions s ON c.id = s.coach_id
            WHERE c.gym_id = %s
        """
        params = [user["id"]]
        
        # Add filters
        if search:
            query += " AND (c.name LIKE %s OR c.email LIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        if specialization and specialization != 'all':
            query += " AND c.specialization = %s"
            params.append(specialization)
        
        if status and status != 'all':
            query += " AND c.status = %s"
            params.append(status)
        
        # Add group by
        query += " GROUP BY c.id"
        
        # Add order by
        query += " ORDER BY c.name ASC"
        
        cursor.execute(query, params)
        coaches = cursor.fetchall()
        
        # Format the response
        formatted_coaches = []
        for coach in coaches:
            total_sessions = coach['total_sessions'] or 0
            completed_sessions = coach['completed_sessions'] or 0
            completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            formatted_coach = {
                "id": coach["id"],
                "name": coach["name"],
                "email": coach["email"],
                "specialization": coach["specialization"],
                "status": coach["status"],
                "stats": {
                    "total_members": coach["total_members"] or 0,
                    "total_sessions": total_sessions,
                    "completed_sessions": completed_sessions,
                    "completion_rate": round(completion_rate, 1)
                }
            }
            formatted_coaches.append(formatted_coach)
        
        return formatted_coaches
        
    except Exception as e:
        print(f"Error getting gym coaches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@app.get("/api/gym/members")
async def get_gym_members(request: Request, search: str = None, membership_type: str = None, status: str = None):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Base query
        query = """
            SELECT m.*, 
                   c.name as coach_name,
                   COUNT(s.id) as total_sessions,
                   COUNT(CASE WHEN s.status = 'Completed' THEN 1 END) as completed_sessions,
                   COUNT(CASE WHEN s.status = 'Cancelled' THEN 1 END) as cancelled_sessions,
                   MAX(s.session_date) as last_session_date
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            LEFT JOIN sessions s ON m.id = s.member_id
            WHERE m.gym_id = %s
        """
        params = [user["id"]]
        
        # Add search condition if search term is provided
        if search:
            query += """ AND (
                m.name LIKE %s 
                OR m.email LIKE %s
            )"""
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        # Add membership type filter if provided
        if membership_type and membership_type != 'all':
            query += " AND m.membership_type = %s"
            params.append(membership_type)
        
        # Add group by clause with all non-aggregated columns
        query += """ GROUP BY m.id, m.name, m.email, m.membership_type, m.join_date, 
                    m.created_at, m.gym_id, m.password, c.name"""
        
        # Add order by clause
        query += " ORDER BY m.join_date DESC"
        
        # Execute query
        cursor.execute(query, params)
        members = cursor.fetchall()
        
        # Format the response
        formatted_members = []
        for member in members:
            total_sessions = member['total_sessions'] or 0
            completed_sessions = member['completed_sessions'] or 0
            attendance_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            formatted_member = {
                "id": member["id"],
                "name": member["name"],
                "email": member["email"],
                "membership_type": member["membership_type"],
                "join_date": member["join_date"].strftime("%Y-%m-%d") if member["join_date"] else None,
                "coach_name": member["coach_name"],
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "cancelled_sessions": member["cancelled_sessions"] or 0,
                "attendance_rate": round(attendance_rate, 1),
                "last_session": member["last_session_date"].strftime("%Y-%m-%d") if member["last_session_date"] else None
            }
            formatted_members.append(formatted_member)
        
        return formatted_members
    except Exception as e:
        print(f"Error getting gym members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.post("/api/gym/members")
async def add_gym_member(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get member data from request
        data = await request.json()
        
        # Validate required fields (removed join_date since it's auto-generated)
        required_fields = ["name", "email", "password", "membership_type"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate email format
        if not "@" in data["email"] or not "." in data["email"]:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # Validate membership type
        valid_membership_types = ["Basic", "Premium", "VIP"]
        if data["membership_type"] not in valid_membership_types:
            raise HTTPException(status_code=400, detail=f"Invalid membership type. Must be one of: {', '.join(valid_membership_types)}")
        
        # Validate password length
        if len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT 1 FROM members WHERE email = %s", (data["email"],))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # If coach_id is provided, verify it exists and belongs to the gym
            if "coach_id" in data:
                cursor.execute("""
                    SELECT 1 FROM coaches 
                    WHERE id = %s AND gym_id = %s AND status = 'Active'
                """, (data["coach_id"], user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Invalid or inactive coach ID")
            
            # Insert new member
            cursor.execute("""
                INSERT INTO members (
                    gym_id, 
                    name, 
                    email, 
                    password, 
                    membership_type, 
                    join_date,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, CURDATE(), NOW())
            """, (
                user["id"],
                data["name"],
                data["email"],
                data["password"],
                data["membership_type"]
            ))
            
            member_id = cursor.lastrowid
            
            # If coach_id is provided, assign member to coach
            if "coach_id" in data:
                cursor.execute("""
                    INSERT INTO member_coach (member_id, coach_id, assigned_date)
                    VALUES (%s, %s, NOW())
                """, (member_id, data["coach_id"]))
            
            # Create initial payment record for membership
            cursor.execute("""
                INSERT INTO payments (
                    member_id,
                    gym_id,
                    amount,
                    payment_type,
                    status,
                    notes
                )
                VALUES (%s, %s, %s, 'Membership', 'Pending', %s)
            """, (
                member_id,
                user["id"],
                0.00,  # Initial amount, can be updated later
                f"Initial membership payment - {data['membership_type']}"
            ))
            
            conn.commit()
            
            # Get the newly created member with additional details
            cursor.execute("""
                SELECT 
                    m.*,
                    c.name as coach_name,
                    c.specialization as coach_specialization,
                    c.email as coach_email,
                    p.id as payment_id,
                    p.status as payment_status
                FROM members m
                LEFT JOIN member_coach mc ON m.id = mc.member_id
                LEFT JOIN coaches c ON mc.coach_id = c.id
                LEFT JOIN payments p ON m.id = p.member_id
                WHERE m.id = %s
            """, (member_id,))
            
            new_member = cursor.fetchone()
            
            return {
                "message": "Member added successfully",
                "member": {
                    "id": new_member["id"],
                    "name": new_member["name"],
                    "email": new_member["email"],
                    "membership_type": new_member["membership_type"],
                    "join_date": new_member["join_date"].strftime("%Y-%m-%d") if new_member["join_date"] else None,
                    "coach": {
                        "name": new_member["coach_name"],
                        "specialization": new_member["coach_specialization"],
                        "email": new_member["coach_email"]
                    } if new_member["coach_name"] else None,
                    "payment": {
                        "id": new_member["payment_id"],
                        "status": new_member["payment_status"]
                    } if new_member["payment_id"] else None
                }
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error adding member: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gym/sessions")
async def create_session(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get session data from request
        data = await request.json()
        required_fields = ["member_id", "coach_id", "session_date", "session_time", "duration"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Verify member and coach belong to the gym
            cursor.execute("""
                SELECT m.id, m.membership_type, c.id as coach_id
                FROM members m
                JOIN coaches c ON c.id = %s
                WHERE m.id = %s AND m.gym_id = %s AND c.gym_id = %s
            """, (data["coach_id"], data["member_id"], user["id"], user["id"]))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=400, detail="Invalid member or coach ID")
            
            # Check for session conflicts
            cursor.execute("""
                SELECT 1 FROM sessions 
                WHERE coach_id = %s 
                AND session_date = %s 
                AND session_time = %s
                AND status != 'Cancelled'
            """, (data["coach_id"], data["session_date"], data["session_time"]))
            
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Coach already has a session at this time")
            
            # Create session
            cursor.execute("""
                INSERT INTO sessions (
                    gym_id,
                    coach_id,
                    member_id,
                    session_date,
                    session_time,
                    duration,
                    status,
                    notes,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled', %s, NOW())
            """, (
                user["id"],
                data["coach_id"],
                data["member_id"],
                data["session_date"],
                data["session_time"],
                data["duration"],
                data.get("notes", "")
            ))
            
            session_id = cursor.lastrowid
            
            # Create payment record for the session
            session_price = 25.00  # Base price for a session
            if result["membership_type"] == "Premium":
                session_price = 20.00  # 20% discount for Premium members
            elif result["membership_type"] == "VIP":
                session_price = 15.00  # 40% discount for VIP members
            
            cursor.execute("""
                INSERT INTO payments (
                    member_id,
                    gym_id,
                    amount,
                    payment_type,
                    status,
                    notes
                )
                VALUES (%s, %s, %s, 'Session', 'Pending', %s)
            """, (
                data["member_id"],
                user["id"],
                session_price,
                f"Payment for session on {data['session_date']} at {data['session_time']}"
            ))
            
            conn.commit()
            
            # Get the created session with details
            cursor.execute("""
                SELECT 
                    s.*,
                    m.name as member_name,
                    m.membership_type,
                    c.name as coach_name,
                    p.id as payment_id,
                    p.amount as session_price,
                    p.status as payment_status
                FROM sessions s
                JOIN members m ON s.member_id = m.id
                JOIN coaches c ON s.coach_id = c.id
                LEFT JOIN payments p ON p.member_id = m.id AND p.payment_type = 'Session'
                WHERE s.id = %s
            """, (session_id,))
            
            new_session = cursor.fetchone()
            
            return {
                "message": "Session created successfully",
                "session": {
                    "id": new_session["id"],
                    "member": {
                        "id": new_session["member_id"],
                        "name": new_session["member_name"],
                        "membership_type": new_session["membership_type"]
                    },
                    "coach": {
                        "id": new_session["coach_id"],
                        "name": new_session["coach_name"]
                    },
                    "date": new_session["session_date"].strftime("%Y-%m-%d"),
                    "time": new_session["session_time"].strftime("%H:%M"),
                    "duration": new_session["duration"],
                    "status": new_session["status"],
                    "payment": {
                        "id": new_session["payment_id"],
                        "amount": float(new_session["session_price"]),
                        "status": new_session["payment_status"]
                    }
                }
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error creating session: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gym/members/{member_id}/renew-membership")
async def renew_membership(member_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get member details
        cursor.execute("""
            SELECT membership_type 
            FROM members 
            WHERE id = %s AND gym_id = %s
        """, (member_id, user["id"]))
        
        member = cursor.fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Calculate payment amount based on membership type
        amount = MEMBERSHIP_PRICES.get(member["membership_type"])
        if not amount:
            raise HTTPException(status_code=400, detail="Invalid membership type")
        
        # Create payment record
        cursor.execute("""
            INSERT INTO payments (
                member_id,
                gym_id,
                amount,
                payment_type,
                status,
                notes
            )
            VALUES (%s, %s, %s, 'Membership', 'Pending', %s)
        """, (
            member_id,
            user["id"],
            amount,
            f"Monthly membership renewal - {member['membership_type']}"
        ))
        
        payment_id = cursor.lastrowid
        conn.commit()
        
        return {
            "message": "Membership renewal payment created",
            "payment": {
                "id": payment_id,
                "amount": amount,
                "type": "Membership",
                "status": "Pending",
                "membership_type": member["membership_type"]
            }
        }
        
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        print(f"Error renewing membership: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/dashboard", response_class=HTMLResponse)
async def get_coach_dashboard_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach_details = cursor.fetchone()
        
        # Return the dashboard page template with coach details
        return templates.TemplateResponse(
            "coach/dashboard.html",
            {
                "request": request,
                "coach": coach_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting coach dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
@app.get("/api/coach/dashboard")
async def get_coach_dashboard(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach info
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach = cursor.fetchone()
        
        # Get comprehensive stats
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT mc.member_id) as total_members,
                COUNT(DISTINCT s.id) as total_sessions,
                COUNT(DISTINCT CASE WHEN s.status = 'Completed' THEN s.id END) as completed_sessions,
                COUNT(DISTINCT CASE WHEN s.session_date >= CURDATE() THEN s.id END) as upcoming_sessions,
                COUNT(DISTINCT CASE WHEN s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN s.id END) as week_sessions,
                COUNT(DISTINCT CASE WHEN s.status = 'Completed' AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN s.id END) as week_completed_sessions
            FROM coaches c
            LEFT JOIN member_coach mc ON c.id = mc.coach_id
            LEFT JOIN sessions s ON c.id = s.coach_id
            WHERE c.id = %s
        """, (user["id"],))
        stats = cursor.fetchone()
        
        # Calculate performance rating (based on completed sessions vs total sessions)
        performance_rating = 85  # Default rating
        if stats['total_sessions'] and stats['total_sessions'] > 0:
            completion_rate = (stats['completed_sessions'] / stats['total_sessions']) * 100
            performance_rating = min(100, max(60, completion_rate + 20))  # Rating between 60-100
        
        # Get recent sessions
        cursor.execute("""
            SELECT 
                s.*,
                m.name as member_name,
                m.membership_type,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.coach_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """, (user["id"],))
        recent_sessions = cursor.fetchall()
        
        # Format recent sessions
        formatted_sessions = []
        for session in recent_sessions:
            # Parse the workout notes to get exercise list
            exercises = []
            workout_type = "Custom"
            if session["notes"]:
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except Exception as e:
                    print(f"Error parsing notes: {str(e)}")
            
            formatted_session = {
                "id": session["id"],
                "member": {
                    "name": session["member_name"],
                    "membership_type": session["membership_type"]
                },
                "date": session["formatted_date"],
                "time": session["formatted_time"],
                "duration": session["duration"],
                "status": session["status"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "notes": session["notes"]
            }
            formatted_sessions.append(formatted_session)
        
        return {
            "coach": {
                "id": coach["id"],
                "name": coach["name"],
                "email": coach["email"],
                "specialization": coach["specialization"],
                "gym_name": coach["gym_name"]
            },
            "stats": {
                "total_members": stats["total_members"] or 0,
                "total_sessions": stats["total_sessions"] or 0,
                "completed_sessions": stats["completed_sessions"] or 0,
                "upcoming_sessions": stats["upcoming_sessions"] or 0,
                "week_sessions": stats["week_sessions"] or 0,
                "performance_rating": performance_rating
            },
            "recent_sessions": formatted_sessions
        }
    except Exception as e:
        print(f"Error getting coach dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/schedule", response_class=HTMLResponse)
async def get_coach_schedule_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach_details = cursor.fetchone()
        
        # Return the schedule page template with coach details
        return templates.TemplateResponse(
            "coach/schedule.html",
            {
                "request": request,
                "coach": coach_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting coach schedule page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/members", response_class=HTMLResponse)
async def get_coach_members_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach_details = cursor.fetchone()
        
        # Return the members page template with coach details
        return templates.TemplateResponse(
            "coach/members.html",
            {
                "request": request,
                "coach": coach_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting coach members page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/sessions", response_class=HTMLResponse)
async def get_coach_sessions_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach_details = cursor.fetchone()
        
        # Return the sessions page template with coach details
        return templates.TemplateResponse(
            "coach/sessions.html",
            {
                "request": request,
                "coach": coach_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting coach sessions page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/progress", response_class=HTMLResponse)
async def get_coach_progress_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach_details = cursor.fetchone()
        
        # Return the progress page template with coach details
        return templates.TemplateResponse(
            "coach/progress.html",
            {
                "request": request,
                "coach": coach_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting coach progress page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/members/{member_id}", response_class=HTMLResponse)
async def get_coach_member_details_page(request: Request, member_id: int):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach and member details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify member belongs to coach
        cursor.execute("""
            SELECT m.*, mc.assigned_date
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """, (member_id, user["id"]))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach = cursor.fetchone()
        
        # Return the member details page template
        return templates.TemplateResponse(
            "coach/member_details.html",
            {
                "request": request,
                "member": member,
                "coach": coach,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting member details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/coach/members/{member_id}")
async def get_coach_member_details(member_id: int, current_user: dict = Depends(get_current_user_dependency)):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get member details with verification that they belong to the coach
        cursor.execute("""
            SELECT 
                m.*,
                mc.assigned_date,
                COUNT(s.id) as total_sessions,
                SUM(CASE WHEN s.status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                MAX(CASE WHEN s.status = 'Completed' THEN s.session_date ELSE NULL END) as last_session
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN sessions s ON m.id = s.member_id
            WHERE m.id = %s AND mc.coach_id = %s
            GROUP BY m.id
        """, (member_id, current_user["id"]))
        
        member = cursor.fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Get recent sessions
        cursor.execute("""
            SELECT 
                s.*,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            WHERE s.member_id = %s AND s.coach_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 10
        """, (member_id, current_user["id"]))
        recent_sessions = cursor.fetchall()
        
        # Format recent sessions
        formatted_sessions = []
        for session in recent_sessions:
            workout_type = "Custom"
            exercises = []
            if session.get("notes"):
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except:
                    pass
            
            formatted_sessions.append({
                "id": session["id"],
                "date": session["formatted_date"],
                "time": session["formatted_time"],
                "duration": session["duration"],
                "status": session["status"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "notes": session.get("notes", "")
            })
        
        return {
            "member": {
                "id": member["id"],
                "name": member["name"],
                "email": member["email"],
                "membership_type": member["membership_type"],
                "join_date": member["join_date"].strftime("%Y-%m-%d") if member.get("join_date") else None,
                "assigned_date": member["assigned_date"].strftime("%Y-%m-%d") if member.get("assigned_date") else None,
                "total_sessions": member["total_sessions"] or 0,
                "completed_sessions": member["completed_sessions"] or 0,
                "last_session": member["last_session"].strftime("%Y-%m-%d") if member.get("last_session") else None
            },
            "recent_sessions": formatted_sessions
        }
    except Exception as e:
        print(f"Error in get_coach_member_details: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error retrieving member details")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/api/user")
async def get_current_user_info(current_user: dict = Depends(get_current_user_dependency)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session_id")
    return response

@app.get("/api/coach/members/")
async def get_coach_members_root(current_user: dict = Depends(get_current_user_dependency)):
    # Redirect to the main members endpoint
    return RedirectResponse(url="/api/coach/members")

@app.post("/api/coach/sessions")
async def create_coach_session(
    request: Request,
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        # Get session data from request
        data = await request.json()
        required_fields = ["member_id", "session_date", "session_time", "duration"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Verify member belongs to coach
            cursor.execute("""
                SELECT m.id, m.membership_type
                FROM members m
                JOIN member_coach mc ON m.id = mc.member_id
                WHERE m.id = %s AND mc.coach_id = %s
            """, (data["member_id"], current_user["id"]))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=400, detail="Member not assigned to this coach")
            
            # Check for session conflicts
            cursor.execute("""
                SELECT 1 FROM sessions 
                WHERE coach_id = %s 
                AND session_date = %s 
                AND session_time = %s
                AND status != 'Cancelled'
            """, (current_user["id"], data["session_date"], data["session_time"]))
            
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Coach already has a session at this time")
            
            # Create session
            cursor.execute("""
                INSERT INTO sessions (
                    gym_id,
                    coach_id,
                    member_id,
                    session_date,
                    session_time,
                    duration,
                    status,
                    notes,
                    created_at
                )
                VALUES (
                    (SELECT gym_id FROM coaches WHERE id = %s),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Scheduled',
                    %s,
                    NOW()
                )
            """, (
                current_user["id"],
                current_user["id"],
                data["member_id"],
                data["session_date"],
                data["session_time"],
                data["duration"],
                data.get("notes", "")
            ))
            
            session_id = cursor.lastrowid
            
            # Get the created session with details
            cursor.execute("""
                SELECT 
                    s.*,
                    m.name as member_name,
                    m.membership_type,
                    DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                    TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
                FROM sessions s
                JOIN members m ON s.member_id = m.id
                WHERE s.id = %s
            """, (session_id,))
            
            new_session = cursor.fetchone()
            
            conn.commit()
            
            return {
                "message": "Session created successfully",
                "session": {
                    "id": new_session["id"],
                    "member": {
                        "id": new_session["member_id"],
                        "name": new_session["member_name"],
                        "membership_type": new_session["membership_type"]
                    },
                    "date": new_session["formatted_date"],
                    "time": new_session["formatted_time"],
                    "duration": new_session["duration"],
                    "status": new_session["status"],
                    "notes": new_session["notes"]
                }
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error creating session: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/coach/schedule")
async def get_coach_schedule(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    member: str = None,
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query for sessions
        query = """
            SELECT 
                s.*,
                m.name as member_name,
                m.email as member_email,
                m.membership_type,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.coach_id = %s
        """
        params = [current_user["id"]]
        
        # Add date range filter
        if start_date and end_date:
            query += " AND s.session_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        # Add member filter
        if member:
            query += " AND s.member_id = %s"
            params.append(member)
        
        # Add order by
        query += " ORDER BY s.session_date ASC, s.session_time ASC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Format sessions
        formatted_sessions = []
        for session in sessions:
            # Parse workout notes
            workout_type = "Custom"
            exercises = []
            if session["notes"]:
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except:
                    pass
            
            formatted_sessions.append({
                "id": session["id"],
                "member": {
                    "id": session["member_id"],
                    "name": session["member_name"],
                    "email": session["member_email"],
                    "membership_type": session["membership_type"]
                },
                "date": session["formatted_date"],
                "time": session["formatted_time"],
                "duration": session["duration"],
                "status": session["status"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "notes": session["notes"]
            })
        
        # Get coach's weekly availability
        cursor.execute("""
            SELECT * FROM free_days
            WHERE user_id = %s AND user_type = 'coach'
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (current_user["id"],))
        free_days = cursor.fetchall()
        
        # Convert all objects to JSON-serializable format
        formatted_free_days = convert_for_json(free_days)
        
        # If no free days exist, create default ones
        if not formatted_free_days:
            formatted_free_days = []
            days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day in days_of_week:
                formatted_free_days.append({
                    'day_of_week': day,
                    'is_available': True,
                    'start_time': '08:00:00',
                    'end_time': '20:00:00'
                })
        
        cursor.close()
        conn.close()
        
        return JSONResponse(content={
            "sessions": formatted_sessions,
            "weekly_availability": formatted_free_days
        })
    except Exception as e:
        print(f"Error in get_coach_schedule: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving schedule")

@app.get("/coach/members/{member_id}/add-session", response_class=HTMLResponse)
async def get_add_session_page(request: Request, member_id: int):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Get coach and member details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify member belongs to coach
        cursor.execute("""
            SELECT m.*, mc.assigned_date
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """, (member_id, user["id"]))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Get coach details
        cursor.execute("""
            SELECT c.*, g.name as gym_name
            FROM coaches c
            JOIN gyms g ON c.gym_id = g.id
            WHERE c.id = %s
        """, (user["id"],))
        coach = cursor.fetchone()
        
        # Return the add session page template
        return templates.TemplateResponse(
            "coach/add_session.html",
            {
                "request": request,
                "member": member,
                "coach": coach,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting add session page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/member/schedule", response_class=HTMLResponse)
async def get_member_schedule_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    
    # Get member details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get member details with coach info
        cursor.execute("""
            SELECT m.*, c.name as coach_name, c.specialization, c.email as coach_email
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            WHERE m.id = %s
        """, (user["id"],))
        member_details = cursor.fetchone()
        
        # Return the schedule page template with member details
        return templates.TemplateResponse(
            "member/schedule.html",
            {
                "request": request,
                "member": member_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting member schedule page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/member/schedule")
async def get_member_schedule(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    current_user: dict = Depends(get_current_user_dependency)
):
    if current_user["user_type"] != "member":
        raise HTTPException(status_code=403, detail="Only members can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query for sessions
        query = """
            SELECT 
                s.*,
                c.name as coach_name,
                c.specialization as coach_specialization,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN coaches c ON s.coach_id = c.id
            WHERE s.member_id = %s
        """
        params = [current_user["id"]]
        
        # Add date range filter
        if start_date and end_date:
            query += " AND s.session_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        # Add order by
        query += " ORDER BY s.session_date ASC, s.session_time ASC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Format sessions
        formatted_sessions = []
        for session in sessions:
            # Parse workout notes
            workout_type = "Custom"
            exercises = []
            if session["notes"]:
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except:
                    pass
            
            formatted_sessions.append({
                "id": session["id"],
                "coach": {
                    "name": session["coach_name"],
                    "specialization": session["coach_specialization"]
                },
                "date": session["formatted_date"],
                "time": session["formatted_time"],
                "duration": session["duration"],
                "status": session["status"],
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "notes": session["notes"]
            })
        
        # Get member's weekly availability
        cursor.execute("""
            SELECT * FROM free_days
            WHERE user_id = %s AND user_type = 'member'
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (current_user["id"],))
        member_free_days = cursor.fetchall()
        
        # Convert all objects to JSON-serializable format
        formatted_member_free_days = convert_for_json(member_free_days)
        
        # If no free days exist, create default ones
        if not formatted_member_free_days:
            formatted_member_free_days = []
            days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day in days_of_week:
                formatted_member_free_days.append({
                    'day_of_week': day,
                    'is_available': True,
                    'start_time': '08:00:00',
                    'end_time': '20:00:00'
                })
        
        # Get member's coach and coach's availability
        cursor.execute("""
            SELECT c.id, c.name, c.specialization
            FROM coaches c
            JOIN member_coach mc ON c.id = mc.coach_id
            WHERE mc.member_id = %s
        """, (current_user["id"],))
        coach_data = cursor.fetchone()
        
        coach_availability = []
        if coach_data:
            cursor.execute("""
                SELECT * FROM free_days
                WHERE user_id = %s AND user_type = 'coach'
                ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
            """, (coach_data["id"],))
            coach_availability = cursor.fetchall()
            
            # Convert all objects to JSON-serializable format
            coach_availability = convert_for_json(coach_availability)
            
            # If coach has no free days, create default ones
            if not coach_availability:
                days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                for day in days_of_week:
                    coach_availability.append({
                        'day_of_week': day,
                        'is_available': True,
                        'start_time': '08:00:00',
                        'end_time': '20:00:00'
                    })
        
        cursor.close()
        conn.close()
        
        return JSONResponse(content={
            "sessions": formatted_sessions,
            "member_availability": formatted_member_free_days,
            "coach_availability": coach_availability,
            "coach": coach_data
        })
    except Exception as e:
        print(f"Error in get_member_schedule: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving schedule")

@app.get("/member/progress", response_class=HTMLResponse)
async def get_member_progress_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    
    # Get member details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get member details with coach info
        cursor.execute("""
            SELECT m.*, c.name as coach_name, c.specialization, c.email as coach_email
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            WHERE m.id = %s
        """, (user["id"],))
        member_details = cursor.fetchone()
        
        # Return the progress page template with member details
        return templates.TemplateResponse(
            "member/progress.html",
            {
                "request": request,
                "member": member_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting member progress page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/preferences", response_class=HTMLResponse)
async def get_coach_preferences_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("coach/preferences.html", {"request": request, "user": user})

@app.get("/member/preferences", response_class=HTMLResponse)
async def get_member_preferences_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("member/preferences.html", {"request": request, "user": user})

@app.get("/api/member/progress")
async def get_member_progress_data(current_user: dict = Depends(get_current_user_dependency)):
    if current_user["user_type"] != "member":
        raise HTTPException(status_code=403, detail="Only members can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get session statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled_sessions
            FROM sessions
            WHERE member_id = %s
        """, (current_user["id"],))
        stats = cursor.fetchone()
        

        
        # Calculate attendance rate
        total_sessions = stats["total_sessions"] or 0
        completed_sessions = stats["completed_sessions"] or 0
        attendance_rate = round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0)
        
        # Get most common workout type
        cursor.execute("""
            SELECT 
                TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(notes, 'Workout Type:', -1), CHAR(10), 1)) as workout_type,
                COUNT(*) as count
            FROM sessions
            WHERE member_id = %s AND notes LIKE '%%Workout Type:%%'
            GROUP BY workout_type
            ORDER BY count DESC
            LIMIT 1
        """, (current_user["id"],))
        common_workout = cursor.fetchone()
        
        # Get session history (last 30 days)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(session_date, '%%Y-%%m-%%d') as date,
                COUNT(*) as count
            FROM sessions
            WHERE member_id = %s 
            AND session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY session_date
            ORDER BY session_date
        """, (current_user["id"],))
        session_history = cursor.fetchall()
        
        # Get workout distribution
        cursor.execute("""
            SELECT 
                TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(notes, 'Workout Type:', -1), CHAR(10), 1)) as workout_type,
                COUNT(*) as count
            FROM sessions
            WHERE member_id = %s AND notes LIKE '%%Workout Type:%%'
            GROUP BY workout_type
            ORDER BY count DESC
        """, (current_user["id"],))
        workout_distribution = cursor.fetchall()
        

        
        # Get recent sessions
        cursor.execute("""
            SELECT 
                s.*,
                c.name as coach_name,
                DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN coaches c ON s.coach_id = c.id
            WHERE s.member_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """, (current_user["id"],))
        recent_sessions = cursor.fetchall()
        
        # Format recent sessions
        formatted_recent_sessions = []
        for session in recent_sessions:
            workout_type = "Custom"
            exercises = []
            if session["notes"]:
                try:
                    lines = session["notes"].split("\n")
                    if lines and "Workout Type:" in lines[0]:
                        workout_type = lines[0].split("Workout Type:")[1].strip()
                    exercises = [line.strip() for line in lines[1:] if line.strip() and line.strip()[0].isdigit()]
                except:
                    pass
            
            formatted_recent_sessions.append({
                "date": session["formatted_date"],
                "coach": {
                    "name": session["coach_name"]
                },
                "workout": {
                    "type": workout_type,
                    "exercises": exercises
                },
                "status": session["status"]
            })
        
        cursor.close()
        conn.close()
        
        return {
            "sessions_completed": completed_sessions,
            "attendance_rate": attendance_rate,
            "common_workout": common_workout["workout_type"] if common_workout else "No workouts",
            "session_history": {
                "labels": [entry["date"] for entry in session_history],
                "values": [entry["count"] for entry in session_history]
            },
            "workout_distribution": {
                "labels": [entry["workout_type"] for entry in workout_distribution],
                "values": [entry["count"] for entry in workout_distribution]
            },
            "recent_sessions": formatted_recent_sessions
        }
        
    except Exception as e:
        print(f"Error in get_member_progress_data: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving progress data")

@app.get("/gym/reports", response_class=HTMLResponse)
async def get_gym_reports_page(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    
    # Get gym details from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get gym details
        cursor.execute("SELECT * FROM gyms WHERE id = %s", (user["id"],))
        gym_details = cursor.fetchone()
        
        # Return the reports page template with gym details
        return templates.TemplateResponse(
            "gym/reports.html",
            {
                "request": request,
                "gym": gym_details,
                "user": user
            }
        )
    except Exception as e:
        print(f"Error getting gym reports page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/gym/reports")
async def get_gym_reports(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get membership statistics
        cursor.execute("""
            SELECT 
                membership_type,
                COUNT(*) as count,
                SUM(CASE WHEN join_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as new_members
            FROM members 
            WHERE gym_id = %s
            GROUP BY membership_type
        """, (user["id"],))
        membership_stats = cursor.fetchall()
        
        # Get session statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled_sessions,
                COUNT(DISTINCT member_id) as active_members,
                COUNT(DISTINCT coach_id) as active_coaches
            FROM sessions 
            WHERE gym_id = %s
            AND session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """, (user["id"],))
        session_stats = cursor.fetchone()
        
        # Get revenue statistics - total monthly revenue from all active members
        cursor.execute("""
            SELECT 
                SUM(CASE 
                    WHEN membership_type = 'Basic' THEN 50.00
                    WHEN membership_type = 'Premium' THEN 100.00
                    WHEN membership_type = 'VIP' THEN 150.00
                END) as monthly_revenue,
                COUNT(CASE WHEN membership_type = 'Basic' THEN 1 END) as basic_members,
                COUNT(CASE WHEN membership_type = 'Premium' THEN 1 END) as premium_members,
                COUNT(CASE WHEN membership_type = 'VIP' THEN 1 END) as vip_members
            FROM members 
            WHERE gym_id = %s
        """, (user["id"],))
        revenue_stats = cursor.fetchone()
        
        # Get coach performance
        cursor.execute("""
            SELECT 
                c.name as coach_name,
                COUNT(s.id) as total_sessions,
                SUM(CASE WHEN s.status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                COUNT(DISTINCT s.member_id) as unique_members
            FROM coaches c
            LEFT JOIN sessions s ON c.id = s.coach_id
            WHERE c.gym_id = %s
            AND (s.session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) OR s.session_date IS NULL)
            GROUP BY c.id, c.name
        """, (user["id"],))
        coach_stats = cursor.fetchall()
        
        return {
            "membership_stats": membership_stats,
            "session_stats": session_stats,
            "revenue_stats": revenue_stats,
            "coach_stats": coach_stats
        }
    except Exception as e:
        print(f"Error getting gym reports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Helper to get contacts for messaging

def get_message_contacts(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    contacts = []
    try:
        if user["user_type"] == "coach":
            # Coach can message their gym and their members
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type FROM gyms g
                JOIN coaches c ON c.gym_id = g.id WHERE c.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                contacts.append(gym)
            cursor.execute("""
                SELECT m.id, m.name, 'member' as type FROM members m
                JOIN member_coach mc ON mc.member_id = m.id WHERE mc.coach_id = %s
            """, (user["id"],))
            contacts.extend(cursor.fetchall())
        elif user["user_type"] == "gym":
            # Gym can message all coaches and members
            cursor.execute("SELECT id, name, 'coach' as type FROM coaches WHERE gym_id = %s", (user["id"],))
            contacts.extend(cursor.fetchall())
            cursor.execute("SELECT id, name, 'member' as type FROM members WHERE gym_id = %s", (user["id"],))
            contacts.extend(cursor.fetchall())
        elif user["user_type"] == "member":
            # Member can message their gym and their coach
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type FROM gyms g
                JOIN members m ON m.gym_id = g.id WHERE m.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                contacts.append(gym)
            cursor.execute("""
                SELECT c.id, c.name, 'coach' as type FROM coaches c
                JOIN member_coach mc ON mc.coach_id = c.id WHERE mc.member_id = %s
            """, (user["id"],))
            coach = cursor.fetchone()
            if coach:
                contacts.append(coach)
    except Exception as e:
        print(f"Error getting message contacts: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()
    return contacts

# Helper to get messages between two users

def get_conversation(user, contact_id, contact_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT m.*, 
                   CASE 
                       WHEN m.sender_type = 'gym' THEN g.name
                       WHEN m.sender_type = 'coach' THEN c.name
                       WHEN m.sender_type = 'member' THEN mem.name
                   END as sender_name
            FROM messages m
            LEFT JOIN gyms g ON m.sender_id = g.id AND m.sender_type = 'gym'
            LEFT JOIN coaches c ON m.sender_id = c.id AND m.sender_type = 'coach'
            LEFT JOIN members mem ON m.sender_id = mem.id AND m.sender_type = 'member'
            WHERE ((m.sender_id = %s AND m.sender_type = %s AND m.receiver_id = %s AND m.receiver_type = %s)
                OR (m.sender_id = %s AND m.sender_type = %s AND m.receiver_id = %s AND m.receiver_type = %s))
            ORDER BY m.created_at ASC
        """, (
            user["id"], user["user_type"], contact_id, contact_type,
            contact_id, contact_type, user["id"], user["user_type"]
        ))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting conversation: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

# COACH MESSAGES
@app.get("/coach/messages", response_class=HTMLResponse)
async def coach_messages_page(request: Request, contact_id: int = None, contact_type: str = None, search: str = None):
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    contacts = get_message_contacts(user)
    # Filter contacts by search if present
    if search:
        search_lower = search.lower()
        contacts = [c for c in contacts if search_lower in c["name"].lower()]
    messages = []
    selected_contact = None
    if contact_id and contact_type:
        messages = get_conversation(user, contact_id, contact_type)
        selected_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
    return templates.TemplateResponse("coach/messages.html", {"request": request, "user": user, "contacts": contacts, "messages": messages, "selected_contact": selected_contact, "contact_id": contact_id, "contact_type": contact_type})

@app.post("/coach/messages", response_class=HTMLResponse)
async def coach_send_message(request: Request, contact_id: int = Form(...), contact_type: str = Form(...), message: str = Form(...)):
    try:
        user = get_current_user(request)
        if not user or user["user_type"] != "coach":
            return RedirectResponse(url="/")
        
        # Validate input
        if not message or not message.strip():
            return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=empty_message", status_code=303)
        
        if len(message.strip()) > 1000:  # Limit message length
            return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_too_long", status_code=303)
        
        # Validate contact exists and coach can message them
        contacts = get_message_contacts(user)
        valid_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
        if not valid_contact:
            return RedirectResponse(url=f"/coach/messages?error=invalid_contact", status_code=303)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO messages (sender_id, sender_type, receiver_id, receiver_type, message)
                VALUES (%s, %s, %s, %s, %s)
            """, (user["id"], user["user_type"], contact_id, contact_type, message.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=send_failed", status_code=303)
        finally:
            cursor.close()
            conn.close()
        
        return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_sent", status_code=303)
    except Exception as e:
        print(f"Unexpected error in coach_send_message: {str(e)}")
        return RedirectResponse(url=f"/coach/messages?error=unexpected_error", status_code=303)

# GYM MESSAGES
@app.get("/gym/messages", response_class=HTMLResponse)
async def gym_messages_page(request: Request, contact_id: int = None, contact_type: str = None, search: str = None):
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/")
    contacts = get_message_contacts(user)
    if search:
        search_lower = search.lower()
        contacts = [c for c in contacts if search_lower in c["name"].lower()]
    messages = []
    selected_contact = None
    if contact_id and contact_type:
        messages = get_conversation(user, contact_id, contact_type)
        selected_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
    return templates.TemplateResponse("gym/messages.html", {"request": request, "user": user, "contacts": contacts, "messages": messages, "selected_contact": selected_contact, "contact_id": contact_id, "contact_type": contact_type})

@app.post("/gym/messages", response_class=HTMLResponse)
async def gym_send_message(request: Request, contact_id: int = Form(...), contact_type: str = Form(...), message: str = Form(...)):
    try:
        user = get_current_user(request)
        if not user or user["user_type"] != "gym":
            return RedirectResponse(url="/")
        
        # Validate input
        if not message or not message.strip():
            return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=empty_message", status_code=303)
        
        if len(message.strip()) > 1000:  # Limit message length
            return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_too_long", status_code=303)
        
        # Validate contact exists and gym can message them
        contacts = get_message_contacts(user)
        valid_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
        if not valid_contact:
            return RedirectResponse(url=f"/gym/messages?error=invalid_contact", status_code=303)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO messages (sender_id, sender_type, receiver_id, receiver_type, message)
                VALUES (%s, %s, %s, %s, %s)
            """, (user["id"], user["user_type"], contact_id, contact_type, message.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=send_failed", status_code=303)
        finally:
            cursor.close()
            conn.close()
        
        return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_sent", status_code=303)
    except Exception as e:
        print(f"Unexpected error in gym_send_message: {str(e)}")
        return RedirectResponse(url=f"/gym/messages?error=unexpected_error", status_code=303)

# MEMBER MESSAGES
@app.get("/member/messages", response_class=HTMLResponse)
async def member_messages_page(request: Request, contact_id: int = None, contact_type: str = None, search: str = None):
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/")
    contacts = get_message_contacts(user)
    if search:
        search_lower = search.lower()
        contacts = [c for c in contacts if search_lower in c["name"].lower()]
    messages = []
    selected_contact = None
    if contact_id and contact_type:
        messages = get_conversation(user, contact_id, contact_type)
        selected_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
    return templates.TemplateResponse("member/messages.html", {"request": request, "user": user, "contacts": contacts, "messages": messages, "selected_contact": selected_contact, "contact_id": contact_id, "contact_type": contact_type})

@app.post("/member/messages", response_class=HTMLResponse)
async def member_send_message(request: Request, contact_id: int = Form(...), contact_type: str = Form(...), message: str = Form(...)):
    try:
        user = get_current_user(request)
        if not user or user["user_type"] != "member":
            return RedirectResponse(url="/")
        
        # Validate input
        if not message or not message.strip():
            return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=empty_message", status_code=303)
        
        if len(message.strip()) > 1000:  # Limit message length
            return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_too_long", status_code=303)
        
        # Validate contact exists and member can message them
        contacts = get_message_contacts(user)
        valid_contact = next((c for c in contacts if c["id"] == contact_id and c["type"] == contact_type), None)
        if not valid_contact:
            return RedirectResponse(url=f"/member/messages?error=invalid_contact", status_code=303)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO messages (sender_id, sender_type, receiver_id, receiver_type, message)
                VALUES (%s, %s, %s, %s, %s)
            """, (user["id"], user["user_type"], contact_id, contact_type, message.strip()))
            conn.commit()
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=send_failed", status_code=303)
        finally:
            cursor.close()
            conn.close()
        
        return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_sent", status_code=303)
    except Exception as e:
        print(f"Unexpected error in member_send_message: {str(e)}")
        return RedirectResponse(url=f"/member/messages?error=unexpected_error", status_code=303)

# DELETE MESSAGE ENDPOINTS
@app.post("/coach/messages/delete/{message_id}", response_class=HTMLResponse)
async def coach_delete_message(request: Request, message_id: int, contact_id: int = Form(...), contact_type: str = Form(...)):
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Only allow sender to delete their own message
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        msg = cursor.fetchone()
        if not msg:
            return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_not_found", status_code=status.HTTP_303_SEE_OTHER)
        
        if msg["sender_id"] != user["id"] or msg["sender_type"] != user["user_type"]:
            return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=unauthorized_delete", status_code=status.HTTP_303_SEE_OTHER)
        
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting message: {str(e)}")
        return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&error=delete_failed", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        cursor.close()
        conn.close()
    
    return RedirectResponse(url=f"/coach/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_deleted", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/gym/messages/delete/{message_id}", response_class=HTMLResponse)
async def gym_delete_message(request: Request, message_id: int, contact_id: int = Form(...), contact_type: str = Form(...)):
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        msg = cursor.fetchone()
        if not msg:
            return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_not_found", status_code=status.HTTP_303_SEE_OTHER)
        
        if msg["sender_id"] != user["id"] or msg["sender_type"] != user["user_type"]:
            return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=unauthorized_delete", status_code=status.HTTP_303_SEE_OTHER)
        
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting message: {str(e)}")
        return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&error=delete_failed", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        cursor.close()
        conn.close()
    
    return RedirectResponse(url=f"/gym/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_deleted", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/member/messages/delete/{message_id}", response_class=HTMLResponse)
async def member_delete_message(request: Request, message_id: int, contact_id: int = Form(...), contact_type: str = Form(...)):
    user = get_current_user(request)
    if not user or user["user_type"] != "member":
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        msg = cursor.fetchone()
        if not msg:
            return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=message_not_found", status_code=status.HTTP_303_SEE_OTHER)
        
        if msg["sender_id"] != user["id"] or msg["sender_type"] != user["user_type"]:
            return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=unauthorized_delete", status_code=status.HTTP_303_SEE_OTHER)
        
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting message: {str(e)}")
        return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&error=delete_failed", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        cursor.close()
        conn.close()
    
    return RedirectResponse(url=f"/member/messages?contact_id={contact_id}&contact_type={contact_type}&success=message_deleted", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon.ico to prevent 404 errors"""
    from fastapi.responses import Response
    # Return a simple 1x1 transparent PNG as favicon
    import base64
    favicon_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    return Response(content=favicon_data, media_type="image/x-icon")
# Test endpoint to check messages table
@app.get("/api/test-messages-table")
async def test_messages_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SHOW TABLES LIKE 'messages'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            message_count = cursor.fetchone()["count"]
            
            # Get table structure
            cursor.execute("DESCRIBE messages")
            table_structure = cursor.fetchall()
            
            # Get a sample message
            cursor.execute("SELECT * FROM messages LIMIT 1")
            sample_message = cursor.fetchone()
            
            return {
                "success": True, 
                "table_exists": True, 
                "message_count": message_count,
                "table_structure": table_structure,
                "sample_message": sample_message
            }
        else:
            return {"success": False, "table_exists": False, "error": "Messages table not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# Preferences and Free Days API Endpoints

@app.get("/api/preferences")
async def get_user_preferences(current_user: dict = Depends(get_current_user_dependency)):
    """Get user preferences and free days"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        user_type = 'coach' if current_user.get('user_type') == 'coach' else 'member'
        user_id = current_user.get('id')
        
        # Get preferences
        cursor.execute("""
            SELECT * FROM user_preferences 
            WHERE user_id = %s AND user_type = %s
        """, (user_id, user_type))
        preferences = cursor.fetchone()
        
        # Get free days
        cursor.execute("""
            SELECT * FROM free_days 
            WHERE user_id = %s AND user_type = %s
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (user_id, user_type))
        free_days = cursor.fetchall()
        
        # Convert start_time and end_time to strings for frontend compatibility
        for day in free_days:
            if day.get('start_time') is not None:
                day['start_time'] = str(day['start_time'])
            else:
                day['start_time'] = '08:00:00'
            if day.get('end_time') is not None:
                day['end_time'] = str(day['end_time'])
            else:
                day['end_time'] = '20:00:00'
        
        # Initialize default preferences if none exist
        if not preferences:
            preferences = {
                'preferred_workout_types': [],
                'preferred_duration': 60,
                'preferred_time_slots': ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00'],
                'notes': ''
            }
        else:
            # Parse JSON fields
            if preferences.get('preferred_workout_types'):
                preferences['preferred_workout_types'] = json.loads(preferences['preferred_workout_types'])
            else:
                preferences['preferred_workout_types'] = []
            
            if preferences.get('preferred_time_slots'):
                preferences['preferred_time_slots'] = json.loads(preferences['preferred_time_slots'])
            else:
                preferences['preferred_time_slots'] = ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00']
        
        # Initialize default free days if none exist
        if not free_days:
            days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            free_days = []
            for day in days_of_week:
                free_days.append({
                    'day_of_week': day,
                    'is_available': True,
                    'start_time': '08:00:00',
                    'end_time': '20:00:00'
                })
        
        return {
            'preferences': preferences,
            'free_days': free_days
        }
        
    except Exception as e:
        print(f"Error getting preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get preferences")
    finally:
        if connection:
            connection.close()

@app.post("/api/preferences")
async def update_user_preferences(request: Request, current_user: dict = Depends(get_current_user_dependency)):
    """Update user preferences and free days"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        user_type = 'coach' if current_user.get('user_type') == 'coach' else 'member'
        user_id = current_user.get('id')
        
        # Update preferences
        preferences = data.get('preferences', {})
        cursor.execute("""
            INSERT INTO user_preferences (user_id, user_type, preferred_workout_types, preferred_duration, preferred_time_slots, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            preferred_workout_types = VALUES(preferred_workout_types),
            preferred_duration = VALUES(preferred_duration),
            preferred_time_slots = VALUES(preferred_time_slots),
            notes = VALUES(notes),
            updated_at = CURRENT_TIMESTAMP
        """, (
            user_id, 
            user_type,
            json.dumps(preferences.get('preferred_workout_types', [])),
            preferences.get('preferred_duration', 60),
            json.dumps(preferences.get('preferred_time_slots', [])),
            preferences.get('notes', '')
        ))
        
        # Update free days
        free_days = data.get('free_days', [])
        for day_data in free_days:
            cursor.execute("""
                INSERT INTO free_days (user_id, user_type, day_of_week, is_available, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                is_available = VALUES(is_available),
                start_time = VALUES(start_time),
                end_time = VALUES(end_time),
                updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                user_type,
                day_data['day_of_week'],
                day_data['is_available'],
                day_data['start_time'],
                day_data['end_time']
            ))
        
        connection.commit()
        return {"message": "Preferences updated successfully"}
        
    except Exception as e:
        print(f"Error updating preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")
    finally:
        if connection:
            connection.close()

@app.get("/api/coach/members/{member_id}/preferences")
async def get_member_preferences(member_id: int, current_user: dict = Depends(get_current_user_dependency)):
    """Get member preferences for coach view"""
    if not current_user or current_user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify coach has access to this member
        cursor.execute("""
            SELECT * FROM member_coach 
            WHERE coach_id = %s AND member_id = %s
        """, (current_user.get('id'), member_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Not authorized to view this member")
        
        # Get member preferences
        cursor.execute("""
            SELECT * FROM user_preferences 
            WHERE user_id = %s AND user_type = 'member'
        """, (member_id,))
        preferences = cursor.fetchone()
        
        # Get member free days
        cursor.execute("""
            SELECT * FROM free_days 
            WHERE user_id = %s AND user_type = 'member'
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (member_id,))
        free_days = cursor.fetchall()
        
        # Parse JSON fields safely
        parsed_preferences = None
        if preferences:
            parsed_preferences = {
                'preferred_workout_types': [],
                'preferred_duration': preferences.get('preferred_duration', 60),
                'preferred_time_slots': [],
                'notes': preferences.get('notes', '')
            }
            
            # Parse JSON fields with error handling
            try:
                if preferences.get('preferred_workout_types'):
                    parsed_preferences['preferred_workout_types'] = json.loads(preferences['preferred_workout_types'])
            except (json.JSONDecodeError, TypeError):
                parsed_preferences['preferred_workout_types'] = []
                
            try:
                if preferences.get('preferred_time_slots'):
                    parsed_preferences['preferred_time_slots'] = json.loads(preferences['preferred_time_slots'])
            except (json.JSONDecodeError, TypeError):
                parsed_preferences['preferred_time_slots'] = []
        
        return {
            'preferences': parsed_preferences,
            'free_days': free_days or []
        }
        
    except Exception as e:
        print(f"Error getting member preferences: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get member preferences")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.get("/api/coach/members/{member_id}/sessions")
async def get_coach_member_sessions(
    member_id: int, 
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=1000),
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get all sessions for a member with pagination (coach access only)"""
    if not current_user or current_user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify the coach has access to this member
        cursor.execute("""
            SELECT 1 FROM member_coach 
            WHERE coach_id = %s AND member_id = %s
        """, (current_user.get('id'), member_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Access denied to this member")
        
                # Get total count
        cursor.execute("""
            SELECT COUNT(*) FROM sessions
            WHERE member_id = %s
        """, (member_id,))
        
        count_result = cursor.fetchone()
        print(f"Debug: count_result = {count_result}, type = {type(count_result)}")
        
        try:
            if count_result is None:
                total_sessions = 0
            elif isinstance(count_result, dict):
                # Handle dictionary result (like {'COUNT(*)': 21})
                total_sessions = int(count_result.get('COUNT(*)', 0))
            else:
                # Handle tuple/list result
                total_sessions = int(count_result[0]) if count_result[0] is not None else 0
        except (IndexError, TypeError, ValueError) as e:
            print(f"Error parsing count_result: {e}")
            total_sessions = 0
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Get sessions with pagination
        cursor.execute("""
            SELECT s.*, c.name as coach_name, g.name as gym_name,
                   CASE 
                       WHEN s.notes LIKE '%%Workout Type:%%' THEN 
                           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(s.notes, 'Workout Type:', -1), CHAR(10), 1))
                       ELSE 'General Training'
                   END as workout_type,
                   CASE 
                       WHEN s.notes LIKE '%%Exercises:%%' THEN 
                           TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(s.notes, 'Exercises:', -1), CHAR(10), 1))
                       ELSE 'No exercises specified'
                   END as exercises
            FROM sessions s 
            LEFT JOIN coaches c ON s.coach_id = c.id 
            LEFT JOIN gyms g ON s.gym_id = g.id
            WHERE s.member_id = %s 
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT %s OFFSET %s
        """, (member_id, limit, offset))
        
        sessions_data = cursor.fetchall()
        
        # Convert to list of dictionaries
        sessions = []
        for row in sessions_data:
            # Handle both dictionary and tuple results
            if isinstance(row, dict):
                session = {
                    "id": row.get('id'),
                    "member_id": row.get('member_id'),
                    "coach_id": row.get('coach_id'),
                    "gym_id": row.get('gym_id'),
                    "session_date": row.get('session_date').strftime('%Y-%m-%d') if row.get('session_date') else None,
                    "session_time": str(row.get('session_time')) if row.get('session_time') else None,
                    "duration": row.get('duration'),
                    "status": row.get('status'),
                    "notes": row.get('notes'),
                    "created_at": row.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if row.get('created_at') else None,
                    "coach_name": row.get('coach_name'),
                    "gym_name": row.get('gym_name'),
                    "workout": {
                        "type": row.get('workout_type'),
                        "exercises": row.get('exercises', '').split(',') if row.get('exercises') and row.get('exercises') != 'No exercises specified' else []
                    }
                }
            else:
                # Handle tuple results
                session = {
                    "id": row[0],
                    "member_id": row[1],
                    "coach_id": row[2],
                    "gym_id": row[3],
                    "session_date": row[4].strftime('%Y-%m-%d') if row[4] else None,
                    "session_time": str(row[5]) if row[5] else None,
                    "duration": row[6],
                    "status": row[7],
                    "notes": row[8],
                    "created_at": row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else None,
                    "coach_name": row[10],
                    "gym_name": row[11],
                    "workout": {
                        "type": row[12],
                        "exercises": row[13].split(',') if row[13] and row[13] != 'No exercises specified' else []
                    }
                }
            sessions.append(session)
        
        # Calculate if there are more pages
        has_more = (offset + limit) < total_sessions
        
        return {
            "sessions": sessions,
            "total": total_sessions,
            "page": page,
            "limit": limit,
            "has_more": has_more,
            "total_pages": (total_sessions + limit - 1) // limit
        }
        
    except Exception as e:
        print(f"Error getting member sessions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get member sessions")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.get("/api/member/coach")
async def get_member_coach_info(current_user: dict = Depends(get_current_user_dependency)):
    """Get current member's coach information"""
    if not current_user or current_user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get member's coach
        cursor.execute("""
            SELECT c.id, c.name, c.email, c.specialization
            FROM coaches c
            JOIN member_coach mc ON c.id = mc.coach_id
            WHERE mc.member_id = %s
        """, (current_user.get('id'),))
        
        coach = cursor.fetchone()
        
        return {
            'coach': coach
        }
        
    except Exception as e:
        print(f"Error getting member coach: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get coach information")
    finally:
        if connection:
            connection.close()

@app.get("/api/member/coach/{coach_id}/preferences")
async def get_coach_preferences(coach_id: int, current_user: dict = Depends(get_current_user_dependency)):
    """Get coach preferences for member view"""
    if not current_user or current_user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify member has access to this coach
        cursor.execute("""
            SELECT * FROM member_coach 
            WHERE member_id = %s AND coach_id = %s
        """, (current_user.get('id'), coach_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Not authorized to view this coach")
        
        # Get coach preferences
        cursor.execute("""
            SELECT * FROM user_preferences 
            WHERE user_id = %s AND user_type = 'coach'
        """, (coach_id,))
        preferences = cursor.fetchone()
        
        # Get coach free days
        cursor.execute("""
            SELECT * FROM free_days 
            WHERE user_id = %s AND user_type = 'coach'
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (coach_id,))
        free_days = cursor.fetchall()
        
        # Parse JSON fields
        if preferences and preferences.get('preferred_workout_types'):
            preferences['preferred_workout_types'] = json.loads(preferences['preferred_workout_types'])
        if preferences and preferences.get('preferred_time_slots'):
            preferences['preferred_time_slots'] = json.loads(preferences['preferred_time_slots'])
        
        return {
            'preferences': preferences,
            'free_days': free_days
        }
        
    except Exception as e:
        print(f"Error getting coach preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get coach preferences")
    finally:
        if connection:
            connection.close()

# New API endpoints for preferences page

@app.get("/api/coach/all-members")
async def get_all_members_for_coach(
    search: str = "",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get assigned members with their preferences for coach view"""
    if not current_user or current_user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get only assigned members with search filter
        query = """
            SELECT DISTINCT m.id, m.name, m.email, m.membership_type,
                   up.preferred_workout_types, up.preferred_duration, up.preferred_time_slots, up.notes
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN user_preferences up ON m.id = up.user_id AND up.user_type = 'member'
            WHERE mc.coach_id = %s AND (m.name LIKE %s OR m.email LIKE %s)
            ORDER BY m.name
        """
        search_term = f"%{search}%"
        cursor.execute(query, (current_user.get('id'), search_term, search_term))
        members = cursor.fetchall()
        
        # Get free days for each member
        for member in members:
            cursor.execute("""
                SELECT * FROM free_days 
                WHERE user_id = %s AND user_type = 'member'
                ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
            """, (member['id'],))
            member['free_days'] = cursor.fetchall()
            
            # Parse JSON fields
            if member.get('preferred_workout_types'):
                member['preferred_workout_types'] = json.loads(member['preferred_workout_types'])
            else:
                member['preferred_workout_types'] = []
                
            if member.get('preferred_time_slots'):
                member['preferred_time_slots'] = json.loads(member['preferred_time_slots'])
            else:
                member['preferred_time_slots'] = []
        
        return {
            'members': members
        }
        
    except Exception as e:
        print(f"Error getting all members: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get members")
    finally:
        if connection:
            connection.close()

@app.get("/api/member/all-coaches")
async def get_all_coaches_for_member(
    search: str = "",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get all coaches with their preferences for member view"""
    if not current_user or current_user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get all coaches with search filter
        query = """
            SELECT DISTINCT c.id, c.name, c.email, c.specialization, c.status,
                   up.preferred_workout_types, up.preferred_duration, up.preferred_time_slots, up.notes
            FROM coaches c
            LEFT JOIN user_preferences up ON c.id = up.user_id AND up.user_type = 'coach'
            WHERE c.name LIKE %s OR c.email LIKE %s OR c.specialization LIKE %s
            ORDER BY c.name
        """
        search_term = f"%{search}%"
        cursor.execute(query, (search_term, search_term, search_term))
        coaches = cursor.fetchall()
        
        # Get free days for each coach
        for coach in coaches:
            cursor.execute("""
                SELECT * FROM free_days 
                WHERE user_id = %s AND user_type = 'coach'
                ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
            """, (coach['id'],))
            coach['free_days'] = cursor.fetchall()
            
            # Parse JSON fields
            if coach.get('preferred_workout_types'):
                coach['preferred_workout_types'] = json.loads(coach['preferred_workout_types'])
            else:
                coach['preferred_workout_types'] = []
                
            if coach.get('preferred_time_slots'):
                coach['preferred_time_slots'] = json.loads(coach['preferred_time_slots'])
            else:
                coach['preferred_time_slots'] = []
        
        return {
            'coaches': coaches
        }
        
    except Exception as e:
        print(f"Error getting all coaches: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get coaches")
    finally:
        if connection:
            connection.close()

# New API endpoints for date-based availability system

@app.get("/api/availability/bulk")
async def get_bulk_availability(
    user_ids: str = Query(None, description="Comma-separated list of user IDs"),
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get availability for multiple users"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        if not user_ids:
            return {"availability": {}}
        
        user_id_list = [int(uid.strip()) for uid in user_ids.split(",") if uid.strip().isdigit()]
        if not user_id_list:
            return {"availability": {}}

        user_ids_str = ','.join(['%s'] * len(user_id_list))

        connection = get_db_connection()
        cursor = connection.cursor()

        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        query = f"""
            SELECT user_id, date, hour, is_available
            FROM availability_slots
            WHERE user_id IN ({user_ids_str}) AND user_type = %s AND date BETWEEN %s AND %s
            ORDER BY user_id, date, hour
        """
        params = user_id_list + [current_user.get('user_type'), start_date, end_date]
        cursor.execute(query, params)
        slots = cursor.fetchall()

        availability = {}
        for slot in slots:
            user_id = slot['user_id']
            date_str = slot['date'].strftime('%Y-%m-%d') if hasattr(slot['date'], 'strftime') else str(slot['date'])
            if user_id not in availability:
                availability[user_id] = {}
            if date_str not in availability[user_id]:
                availability[user_id][date_str] = {}
            availability[user_id][date_str][slot['hour']] = slot['is_available']

        for user_id in user_id_list:
            if user_id not in availability:
                availability[user_id] = {}

        return {
            'availability': availability,
            'start_date': start_date,
            'end_date': end_date
        }

    except Exception as e:
        print(f"Error getting bulk availability: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get bulk availability")
    finally:
        if connection:
            connection.close()

@app.get("/api/availability/{user_id}")
async def get_user_availability(
    user_id: int,
    start_date: str = None,
    end_date: str = None,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get user availability for a date range"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Set default date range if not provided (next 7 days)
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Get availability slots for the date range
        cursor.execute("""
            SELECT date, hour, is_available
            FROM availability_slots
            WHERE user_id = %s AND user_type = %s AND date BETWEEN %s AND %s
            ORDER BY date, hour
        """, (user_id, current_user.get('user_type'), start_date, end_date))
        
        slots = cursor.fetchall()
        
        # Convert to a more usable format
        availability = {}
        for slot in slots:
            date_str = slot['date'].strftime('%Y-%m-%d')
            if date_str not in availability:
                availability[date_str] = {}
            availability[date_str][slot['hour']] = slot['is_available']
        
        return {
            'availability': availability,
            'start_date': start_date,
            'end_date': end_date
        }
        
    except Exception as e:
        print(f"Error getting user availability: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get availability")
    finally:
        if connection:
            connection.close()

@app.post("/api/availability")
async def update_user_availability(
    request: Request,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Update user availability for specific dates and hours"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        data = await request.json()
        date = data.get('date')
        hour = data.get('hour')
        is_available = data.get('is_available', True)
        
        if not date or hour is None:
            raise HTTPException(status_code=400, detail="Date and hour are required")
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert or update availability slot
        cursor.execute("""
            INSERT INTO availability_slots (user_id, user_type, date, hour, is_available)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE is_available = VALUES(is_available)
        """, (current_user.get('id'), current_user.get('user_type'), date, hour, is_available))
        
        connection.commit()
        
        return {"status": "success", "message": "Availability updated successfully"}
        
    except Exception as e:
        print(f"Error updating user availability: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update availability")
    finally:
        if connection:
            connection.close()

@app.delete("/api/availability/{date}/{hour}")
async def delete_user_availability(
    date: str,
    hour: int,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Delete user availability for a specific date and hour (mark as available)"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Delete the availability slot (will default to available)
        cursor.execute("""
            DELETE FROM availability_slots
            WHERE user_id = %s AND user_type = %s AND date = %s AND hour = %s
        """, (current_user.get('id'), current_user.get('user_type'), date, hour))
        
        connection.commit()
        
        return {"status": "success", "message": "Availability slot deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting user availability: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete availability")
    finally:
        if connection:
            connection.close()

@app.get("/api/availability/calendar/{user_id}")
async def get_user_availability_calendar(
    user_id: int,
    year: int = Query(None, description="Year (YYYY)"),
    month: int = Query(None, description="Month (1-12)"),
    current_user: dict = Depends(get_current_user_dependency)
):
    """Get user availability for calendar view"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        print(f"Calendar request - user_id: {user_id}, current_user: {current_user}")
        
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
            
        # Get the first and last day of the month
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
        start_date = first_day.date()
        end_date = last_day.date()
        
        print(f"Date range: {start_date} to {end_date}")
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get availability slots for the month
        query = """
            SELECT date, hour, is_available
            FROM availability_slots
            WHERE user_id = %s AND user_type = %s AND date BETWEEN %s AND %s
            ORDER BY date, hour
        """
        params = (user_id, current_user.get('user_type'), start_date, end_date)
        print(f"Executing query: {query} with params: {params}")
        
        cursor.execute(query, params)
        slots = cursor.fetchall()
        print(f"Found {len(slots)} availability slots")
        
        # Organize data by date
        calendar_data = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            calendar_data[date_str] = {
                'date': date_str,
                'day_of_week': current_date.strftime('%A'),
                'day_number': current_date.day,
                'is_current_month': True,
                'slots': {}
            }
            current_date += timedelta(days=1)
        
        # Fill in availability data
        for slot in slots:
            date_str = slot['date'].strftime('%Y-%m-%d') if hasattr(slot['date'], 'strftime') else str(slot['date'])
            hour = slot['hour']
            if date_str in calendar_data:
                calendar_data[date_str]['slots'][hour] = slot['is_available']
        
        # Convert to list and sort by date
        calendar_list = list(calendar_data.values())
        calendar_list.sort(key=lambda x: x['date'])
        
        result = {
            'year': year,
            'month': month,
            'month_name': first_day.strftime('%B'),
            'calendar': calendar_list
        }
        
        print(f"Returning calendar data: {result}")
        return result
        
    except Exception as e:
        print(f"Error getting user availability calendar: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get availability calendar")
    finally:
        if connection:
            connection.close()

@app.post("/api/availability/bulk")
async def update_user_availability_bulk(
    request: Request,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Update user availability for a date range and time range"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authorized")
    
    try:
        data = await request.json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        start_hour = data.get('start_hour')
        end_hour = data.get('end_hour')
        is_available = data.get('is_available', False)  # Default to unavailable for bulk updates
        
        if not all([start_date, end_date, start_hour, end_hour]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Convert dates to datetime objects for iteration
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Generate all date-hour combinations
        current_dt = start_dt
        while current_dt <= end_dt:
            current_date = current_dt.strftime('%Y-%m-%d')
            
            # Generate all hours in the range
            for hour in range(start_hour, end_hour + 1):
                cursor.execute("""
                    INSERT INTO availability_slots (user_id, user_type, date, hour, is_available)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE is_available = VALUES(is_available)
                """, (current_user.get('id'), current_user.get('user_type'), current_date, hour, is_available))
            
            current_dt += timedelta(days=1)
        
        connection.commit()
        
        return {"status": "success", "message": "Bulk availability updated successfully"}
        
    except Exception as e:
        print(f"Error updating bulk user availability: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update bulk availability")
    finally:
        if connection:
            connection.close()
# Load model once at startup for classifier endpoint
image_processor = AutoImageProcessor.from_pretrained("prithivMLmods/Gym-Workout-Classifier-SigLIP2")
model = SiglipForImageClassification.from_pretrained("prithivMLmods/Gym-Workout-Classifier-SigLIP2")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
@app.post("/api/classify-frame")
async def classify_frame(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_dependency)
):
    # Only allow premium members
    if not current_user or current_user.get("user_type") != "member":
        raise HTTPException(status_code=403, detail="Members only")
    if current_user.get("membership_type") != "Premium":
        raise HTTPException(status_code=403, detail="Only premium members can use this feature")
    # Read image bytes
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    inputs = image_processor(images=rgb_frame, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_class_idx = logits.argmax(-1).item()
    label = model.config.id2label.get(predicted_class_idx, str(predicted_class_idx))
    score = torch.nn.functional.softmax(logits, dim=-1)[0, predicted_class_idx].item()
    return {"label": label, "score": score}

@app.post("/api/nutrition/classify-food")
async def classify_food(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_dependency)
):
    """Enhanced food classification using Hugging Face model"""
    try:
        # Check user permissions
        if not current_user or current_user.get("user_type") != "member":
            raise HTTPException(status_code=403, detail="Members only")
        if current_user.get("membership_type") not in ["Premium", "VIP"]:
            raise HTTPException(status_code=403, detail="Enhanced food classification requires Premium or VIP membership")
        
        # Read image data
        image_data = await file.read()
        
        # Load the food classification model if not already loaded
        if food_model is None:
            load_food_classification_model()
        
        # Classify the food
        classification_result = classify_food_image(image_data)
        
        if "error" in classification_result:
            raise HTTPException(status_code=500, detail=classification_result['error'])
        
        # Get nutrition data for the detected food
        if classification_result.get('top_prediction'):
            detected_food = classification_result['top_prediction']['food_type']
            confidence = classification_result['top_prediction']['confidence']
            
            # Search USDA database for nutrition
            nutrition_data = get_food_nutrition_from_usda(detected_food)
            
            if nutrition_data:
                return {
                    "success": True,
                    "classification": classification_result,
                    "nutrition": nutrition_data,
                    "analysis_method": "AI + USDA Database"
                }
            else:
                # Fallback to estimated nutrition
                estimated_nutrition = get_estimated_nutrition(detected_food)
                return {
                    "success": True,
                    "classification": classification_result,
                    "nutrition": estimated_nutrition,
                    "analysis_method": "AI + Estimated Nutrition"
                }
        else:
            raise HTTPException(status_code=500, detail="No food detected in image")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in food classification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Add this constant at the top of your file with your actual API key

@app.post("/api/nutrition/detect-food-type")
async def detect_food_type(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_dependency)
):
    """Detect food type in image using AI model"""
    try:
        # Check user permissions
        if not current_user or current_user.get("user_type") != "member":
            raise HTTPException(status_code=403, detail="Members only")
        if current_user.get("membership_type") not in ["Premium", "VIP"]:
            raise HTTPException(status_code=403, detail="Food detection requires Premium or VIP membership")
        
        # Read image data
        image_data = await file.read()
        
        # Load the food classification model if not already loaded
        if food_model is None:
            load_food_classification_model()
        
        # Classify the food
        classification_result = classify_food_image(image_data)
        
        if "error" in classification_result:
            raise HTTPException(status_code=500, detail=classification_result['error'])
        
        # Return only the detection results without nutrition data
        if classification_result.get('top_prediction'):
            detected_food = classification_result['top_prediction']['food_type']
            confidence = classification_result['top_prediction']['confidence']
            
            return {
                "success": True,
                "detected_food": detected_food,
                "confidence": confidence,
                "all_predictions": classification_result.get('predictions', []),
                "analysis_method": "AI Food Detection Model"
            }
        else:
            raise HTTPException(status_code=500, detail="No food detected in image")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in food type detection: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/nutrition/detect-food-simple")
async def detect_food_simple(
    file: UploadFile = File(...)
):
    """Simple food detection endpoint for testing (no authentication required)"""
    try:
        # Read image data
        image_data = await file.read()
        
        # Load the food classification model if not already loaded
        if food_model is None:
            load_food_classification_model()
        
        # Classify the food
        classification_result = classify_food_image(image_data)
        
        if "error" in classification_result:
            raise HTTPException(status_code=500, detail=classification_result['error'])
        
        # Return detection results
        if classification_result.get('top_prediction'):
            detected_food = classification_result['top_prediction']['food_type']
            confidence = classification_result['top_prediction']['confidence']
            
            return {
                "success": True,
                "detected_food": detected_food,
                "confidence": confidence,
                "all_predictions": classification_result.get('predictions', []),
                "message": f"Detected food: {detected_food} (confidence: {confidence:.2f})"
            }
        else:
            return {
                "success": False,
                "message": "No food detected in image"
            }
            
    except Exception as e:
        print(f"Error in simple food detection: {e}")
        raise HTTPException(status_code=500, detail=f"Detection error: {str(e)}")

@app.post("/api/chat")
async def chat(request: Request):
    try:
        # Get JSON data from request
        data = await request.json()
        
        # Validate request data
        if not data or 'message' not in data:
            raise HTTPException(status_code=400, detail="Missing message field")
        
        user_message = data['message']
        
        # Validate message is not empty
        if not user_message or not user_message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        headers = {
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': 'openai/gpt-3.5-turbo',
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        "You are a helpful AI assistant for PowerFit, a comprehensive gym management platform.\n\n"
                        "POWERFIT PLATFORM OVERVIEW:\n"
                        "PowerFit is a modern web-based gym management system that connects gyms, coaches, and members with advanced AI-powered features.\n\n"
                        "CORE FEATURES BY USER TYPE:\n\n"
                        "🏢 GYMS:\n"
                        "• Manage staff (coaches) and clients (members)\n"
                        "• Monitor member progress and attendance\n"
                        "• Set up membership tiers (Basic, Premium, VIP)\n"
                        "• Track training sessions and payments\n"
                        "• Generate reports and analytics\n"
                        "• Export data to Excel\n"
                        "• Manage coach assignments and performance\n"
                        "• View revenue and membership statistics\n\n"
                        "🏋️ COACHES:\n"
                        "• View and manage training schedules\n"
                        "• Assign personalized workout sessions\n"
                        "• Track member progress and attendance\n"
                        "• Set workout preferences and availability\n"
                        "• Create custom workout plans with exercises\n"
                        "• Monitor session completion rates\n"
                        "• Communicate with members and gym staff\n"
                        "• Access nutrition coaching tools (for Premium/VIP members)\n\n"
                        "👤 MEMBERS:\n"
                        "• View assigned coach and training schedule\n"
                        "• Track workout progress and history\n"
                        "• Set personal preferences and availability\n"
                        "• Access nutrition tracking (Premium/VIP)\n"
                        "• Use AI-powered features based on membership\n"
                        "• Communicate with coaches and gym staff\n\n"
                        "MEMBERSHIP TIERS:\n"
                        "• Basic: Core gym access, session tracking, basic communication\n"
                        "• Premium: All Basic features + AI nutrition analysis, food detection, meal planning\n"
                        "• VIP: All Premium features + real-time workout classifier, advanced AI features\n\n"
                        "AI-POWERED FEATURES:\n"
                        "• AI Meal Planning: Personalized nutrition plans using Google Gemini\n"
                        "• Food Detection: Analyze food photos for nutrition information\n"
                        "• Real-time Workout Classifier: Identify exercises from photos (VIP/Premium)\n"
                        "• Nutrition Analysis: USDA database integration for food nutrition\n"
                        "• AI Chatbot: Intelligent assistance for all users\n\n"
                        "COMMON QUESTIONS AND ANSWERS:\n\n"
                        "🔐 LOGIN & ACCESS:\n"
                        "• 'How do I log in?' → Use the email and password provided by your gym. Contact your gym if you forgot your credentials.\n\n"
                        "📅 SCHEDULING & PREFERENCES:\n"
                        "• 'How do I change my workout preferences?' → Go to your schedule page to update exercise preferences and availability times. Your coach uses this to create better plans.\n"
                        "• 'How do I see my training schedule?' → Check your dashboard for upcoming sessions. Contact your coach or gym if sessions are missing.\n"
                        "• 'Can I change my coach?' → Coaches are assigned by the gym. Contact gym staff to request a change.\n\n"
                        "📊 PROGRESS & TRACKING:\n"
                        "• 'How do I see my progress?' → Visit your progress page for workout history, attendance rates, and performance metrics.\n"
                        "• 'How do I track my nutrition?' → Premium and VIP members can access the nutrition page for AI-powered meal planning and food analysis.\n\n"
                        "💳 MEMBERSHIP & PAYMENTS:\n"
                        "• 'What membership do I have?' → Check your profile for membership details (Basic/Premium/VIP). Contact your gym to upgrade.\n"
                        "• 'How do payments work?' → Payments are handled directly by your gym. View payment history in your account.\n\n"
                        "🤖 AI FEATURES:\n"
                        "• 'How do I use the AI meal planner?' → Premium/VIP members can access AI meal planning on the nutrition page.\n"
                        "• 'Can I analyze my food photos?' → Premium/VIP members can upload food photos for nutrition analysis.\n"
                        "• 'What's the workout classifier?' → VIP/Premium members can use real-time exercise identification from photos.\n\n"
                        "💬 COMMUNICATION:\n"
                        "• 'How do I message my coach?' → Use the messages page to communicate with your coach or gym staff.\n"
                        "• 'I need help!' → Message your coach or gym staff directly through the platform, or use this AI chatbot.\n\n"
                        "📱 EXPORT & REPORTS:\n"
                        "• 'Can I export my data?' → Yes, you can export your schedule, progress, and nutrition data to Excel files.\n"
                        "• 'How do I get reports?' → Gyms can generate comprehensive reports on members, coaches, and revenue.\n\n"
                        "TECHNICAL SUPPORT:\n"
                        "• 'The app isn't working' → Try refreshing the page or contact your gym's technical support.\n"
                        "• 'I can't access AI features' → AI features require Premium or VIP membership. Contact your gym to upgrade.\n\n"
                        "Provide friendly, clear answers without technical jargon. Always encourage users to contact their gym staff for account-specific issues."
                    )
                },
                {'role': 'user', 'content': user_message}
            ],
            'max_tokens': 500
        }


        
        # Make request to OpenRouter API
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30  # 30 second timeout
        )
        
        # Check if OpenRouter request was successful
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"OpenRouter API error: {response.text}")
        
        # Parse OpenRouter response
        openrouter_data = response.json()
        
        # Extract the assistant's reply
        if 'choices' in openrouter_data and len(openrouter_data['choices']) > 0:
            assistant_reply = openrouter_data['choices'][0]['message']['content']
            return {"reply": assistant_reply}
        else:
            raise HTTPException(status_code=500, detail="Invalid response from OpenRouter API")
            
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        # Handle network/connection errors
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        raise HTTPException(status_code=500, detail="Invalid JSON response from OpenRouter")
    except Exception as e:
        # Handle any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chatbot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chat-container {
            height: calc(100vh - 140px);
        }
        .message-bubble {
            max-width: 80%;
            word-wrap: break-word;
        }
        .typing-indicator {
            display: none;
        }
        .typing-indicator.show {
            display: flex;
        }
        .typing-dot {
            animation: typing 1.4s infinite ease-in-out;
        }
        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes typing {
            0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
            40% { transform: scale(1); opacity: 1; }
        }
    </style>
</head>
<body class="bg-gray-100 h-screen">
    <div class="max-w-4xl mx-auto h-full flex flex-col">
        <!-- Header -->
        <div class="bg-white shadow-sm border-b px-6 py-4">
            <h1 class="text-xl font-semibold text-gray-800">AI Assistant</h1>
            <p class="text-sm text-gray-600">Ask me anything!</p>
        </div>

        <!-- Chat Messages Container -->
        <div id="chatMessages" class="chat-container bg-white overflow-y-auto p-4 space-y-4">
            <!-- Welcome message -->
            <div class="flex justify-start">
                <div class="message-bubble bg-blue-500 text-white rounded-lg px-4 py-2">
                    <p class="text-sm">Hello! I'm your AI assistant. How can I help you today?</p>
                </div>
            </div>
        </div>

        <!-- Typing Indicator -->
        <div id="typingIndicator" class="typing-indicator bg-white px-4 py-2">
            <div class="flex items-center space-x-2">
                <div class="bg-gray-300 rounded-full p-2">
                    <div class="w-2 h-2 bg-gray-600 rounded-full"></div>
                </div>
                <div class="flex space-x-1">
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                </div>
                <span class="text-sm text-gray-500">AI is typing...</span>
            </div>
        </div>

        <!-- Input Area -->
        <div class="bg-white border-t px-4 py-4">
            <div class="flex space-x-3">
                <input 
                    type="text" 
                    id="messageInput" 
                    placeholder="Type your message here..."
                    class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    onkeypress="handleKeyPress(event)"
                >
                <button 
                    id="sendButton"
                    onclick="sendMessage()"
                    class="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                >
                    Send
                </button>
            </div>
        </div>
    </div>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const typingIndicator = document.getElementById('typingIndicator');

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        function addMessage(content, isUser = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;
            
            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = `message-bubble ${isUser ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'} rounded-lg px-4 py-2`;
            
            const messageText = document.createElement('p');
            messageText.className = 'text-sm';
            messageText.textContent = content;
            
            bubbleDiv.appendChild(messageText);
            messageDiv.appendChild(bubbleDiv);
            chatMessages.appendChild(messageDiv);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function showTypingIndicator() {
            typingIndicator.classList.add('show');
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function hideTypingIndicator() {
            typingIndicator.classList.remove('show');
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            // Disable input and button
            messageInput.disabled = true;
            sendButton.disabled = true;

            // Add user message
            addMessage(message, true);
            messageInput.value = '';

            // Show typing indicator
            showTypingIndicator();

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                
                // Hide typing indicator
                hideTypingIndicator();
                
                // Add bot response
                addMessage(data.reply, false);

            } catch (error) {
                console.error('Error:', error);
                hideTypingIndicator();
                addMessage('Sorry, I encountered an error. Please try again.', false);
            } finally {
                // Re-enable input and button
                messageInput.disabled = false;
                sendButton.disabled = false;
                messageInput.focus();
            }
        }

        // Focus input on page load
        document.addEventListener('DOMContentLoaded', function() {
            messageInput.focus();
        });
    </script>
</body>
</html>
"""

def expand_weekly_availability(free_days):
    slots = set()
    for day in free_days:
        if not day['is_available']:
            continue
        # Parse start and end hour
        start = day['start_time']
        end = day['end_time']
        # Handle both string and int (seconds)
        if isinstance(start, int):
            start_hour = start // 3600
        else:
            start_hour = int(str(start).split(':')[0])
        if isinstance(end, int):
            end_hour = end // 3600
        else:
            end_hour = int(str(end).split(':')[0])
        for hour in range(start_hour, end_hour):
            slots.add((day['day_of_week'], f"{hour:02d}:00"))
    return slots

def next_occurrence(day_name, hour_str):
    days_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    today = datetime.now()
    today_idx = today.weekday()
    target_idx = days_order.index(day_name)
    hour, minute = map(int, hour_str.split(':'))
    # Compute the next date for this day/hour
    days_ahead = (target_idx - today_idx + 7) % 7
    candidate_date = today.date() + timedelta(days=days_ahead)
    candidate_dt = datetime.combine(candidate_date, dt_time(hour, minute))
    # If it's today and hour is in the past, skip to next week
    if candidate_dt <= today:
        candidate_date = candidate_date + timedelta(days=7)
        candidate_dt = datetime.combine(candidate_date, dt_time(hour, minute))
    return candidate_dt

@app.post("/api/coach/assign_best_workout")
async def assign_best_workout_api(
    coach_id: int = Body(...),
    member_id: int = Body(...),
    workout_type: str = Body(...),
    duration: int = Body(...),
    exercises: List[str] = Body([]),
    notes: str = Body("")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get coach weekly availability
        cursor.execute("SELECT * FROM free_days WHERE user_id = %s AND user_type = 'coach'", (coach_id,))
        coach_free_days = cursor.fetchall()
        coach_slots = expand_weekly_availability(coach_free_days)

        # Get member weekly availability
        cursor.execute("SELECT * FROM free_days WHERE user_id = %s AND user_type = 'member'", (member_id,))
        member_free_days = cursor.fetchall()
        member_slots = expand_weekly_availability(member_free_days)

        # Get coach preferred time slots
        cursor.execute("SELECT preferred_time_slots FROM user_preferences WHERE user_id = %s AND user_type = 'coach'", (coach_id,))
        coach_pref = cursor.fetchone()
        coach_preferred_times = []
        if coach_pref and coach_pref['preferred_time_slots']:
            coach_preferred_times = json.loads(coach_pref['preferred_time_slots'])

        # Get member preferred time slots
        cursor.execute("SELECT preferred_time_slots FROM user_preferences WHERE user_id = %s AND user_type = 'member'", (member_id,))
        member_pref = cursor.fetchone()
        member_preferred_times = []
        if member_pref and member_pref['preferred_time_slots']:
            member_preferred_times = json.loads(member_pref['preferred_time_slots'])

        # Get existing sessions for coach (to avoid conflicts)
        cursor.execute("""
            SELECT session_date, session_time, duration 
            FROM sessions 
            WHERE coach_id = %s 
            AND session_date >= CURDATE() 
            AND status != 'Cancelled'
        """, (coach_id,))
        coach_sessions = cursor.fetchall()

        # Get existing sessions for member (to avoid conflicts)
        cursor.execute("""
            SELECT session_date, session_time, duration 
            FROM sessions 
            WHERE member_id = %s 
            AND session_date >= CURDATE() 
            AND status != 'Cancelled'
        """, (member_id,))
        member_sessions = cursor.fetchall()

        # Create sets of unavailable slots for coach and member
        coach_unavailable = set()
        member_unavailable = set()

        # Add coach's existing sessions to unavailable slots
        for session in coach_sessions:
            # Convert timedelta to time object if needed
            session_time = session['session_time']
            if isinstance(session_time, timedelta):
                # Convert timedelta to time object
                total_seconds = int(session_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                session_time = dt_time(hours, minutes, seconds)
            
            session_datetime = datetime.combine(session['session_date'], session_time)
            session_duration = session['duration']
            
            # Block the session hour and adjacent hours based on duration
            hours_to_block = max(1, (session_duration + 59) // 60)  # Round up to nearest hour
            for i in range(hours_to_block):
                blocked_datetime = session_datetime + timedelta(hours=i)
                day_name = blocked_datetime.strftime('%A')
                hour = blocked_datetime.hour
                coach_unavailable.add((day_name, hour))

        # Add member's existing sessions to unavailable slots
        for session in member_sessions:
            # Convert timedelta to time object if needed
            session_time = session['session_time']
            if isinstance(session_time, timedelta):
                # Convert timedelta to time object
                total_seconds = int(session_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                session_time = dt_time(hours, minutes, seconds)
            
            session_datetime = datetime.combine(session['session_date'], session_time)
            session_duration = session['duration']
            
            # Block the session hour and adjacent hours based on duration
            hours_to_block = max(1, (session_duration + 59) // 60)  # Round up to nearest hour
            for i in range(hours_to_block):
                blocked_datetime = session_datetime + timedelta(hours=i)
                day_name = blocked_datetime.strftime('%A')
                hour = blocked_datetime.hour
                member_unavailable.add((day_name, hour))

        # Remove unavailable slots from available slots
        coach_available_slots = coach_slots - coach_unavailable
        member_available_slots = member_slots - member_unavailable

        # Find intersection of available slots
        overlap = coach_available_slots & member_available_slots

        if not overlap:
            return {"success": False, "message": "This workout cannot be assigned — no matching time slot found after considering existing sessions."}

        # Prioritize slots based on preferences
        # 1. Both coach and member prefer this time
        both_preferred = set()
        # 2. Only coach prefers this time
        coach_only_preferred = set()
        # 3. Only member prefers this time
        member_only_preferred = set()
        # 4. Neither prefers this time (but both are available)
        no_preference = set()

        for day, hour in overlap:
            coach_prefers = hour in coach_preferred_times if coach_preferred_times else False
            member_prefers = hour in member_preferred_times if member_preferred_times else False
            
            if coach_prefers and member_prefers:
                both_preferred.add((day, hour))
            elif coach_prefers:
                coach_only_preferred.add((day, hour))
            elif member_prefers:
                member_only_preferred.add((day, hour))
            else:
                no_preference.add((day, hour))

        # Combine slots in order of preference
        slots_to_consider = list(both_preferred) + list(coach_only_preferred) + list(member_only_preferred) + list(no_preference)

        if not slots_to_consider:
            return {"success": False, "message": "This workout cannot be assigned — no matching time slot found."}

        # For each slot, compute the next occurrence (date+time) in the future
        slot_datetimes = []
        for day, hour in slots_to_consider:
            dt = next_occurrence(day, hour)
            # Double-check that this specific datetime doesn't conflict with existing sessions
            is_available = True
            
            # Check coach availability for this specific datetime
            for session in coach_sessions:
                # Convert timedelta to time object if needed
                session_time = session['session_time']
                if isinstance(session_time, timedelta):
                    # Convert timedelta to time object
                    total_seconds = int(session_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    session_time = dt_time(hours, minutes, seconds)
                
                session_start = datetime.combine(session['session_date'], session_time)
                session_end = session_start + timedelta(minutes=session['duration'])
                proposed_start = dt
                proposed_end = dt + timedelta(minutes=duration)
                
                # Check for overlap
                if (proposed_start < session_end and proposed_end > session_start):
                    is_available = False
                    break
            
            # Check member availability for this specific datetime
            if is_available:
                for session in member_sessions:
                    # Convert timedelta to time object if needed
                    session_time = session['session_time']
                    if isinstance(session_time, timedelta):
                        # Convert timedelta to time object
                        total_seconds = int(session_time.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        session_time = dt_time(hours, minutes, seconds)
                    
                    session_start = datetime.combine(session['session_date'], session_time)
                    session_end = session_start + timedelta(minutes=session['duration'])
                    proposed_start = dt
                    proposed_end = dt + timedelta(minutes=duration)
                    
                    # Check for overlap
                    if (proposed_start < session_end and proposed_end > session_start):
                        is_available = False
                        break
            
            if is_available:
                # Determine preference level for scoring
                coach_prefers = hour in coach_preferred_times if coach_preferred_times else False
                member_prefers = hour in member_preferred_times if member_preferred_times else False
                
                if coach_prefers and member_prefers:
                    preference_score = 4
                elif coach_prefers:
                    preference_score = 3
                elif member_prefers:
                    preference_score = 2
                else:
                    preference_score = 1
                
                slot_datetimes.append((dt, day, hour, preference_score))
        
        # Only keep future slots
        slot_datetimes = [s for s in slot_datetimes if s[0] > datetime.now()]
        
        # Sort by preference score (descending) then by datetime (ascending)
        slot_datetimes.sort(key=lambda x: (-x[3], x[0]))
        
        # Take the best 10
        best_matches = slot_datetimes[:10]
        if not best_matches:
            return {"success": False, "message": "This workout cannot be assigned — no matching time slot found."}

        return {
            "success": True,
            "matches": [
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "day": day,
                    "hour": hour,
                    "preference_score": preference_score
                }
                for dt, day, hour, preference_score in best_matches
            ]
        }
    finally:
        cursor.close()
        conn.close()

@app.post("/api/coach/create_session")
async def create_session_api(
    coach_id: int = Body(...),
    member_id: int = Body(...),
    day: str = Body(...),
    hour: str = Body(...),
    date: str = Body(...),
    workout_type: str = Body(...),
    duration: int = Body(...),
    exercises: List[str] = Body([]),
    notes: str = Body("")
):
    # Use the provided date directly
    session_date = date
    session_time = hour

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch gym_id for the coach
        cursor.execute("SELECT gym_id FROM coaches WHERE id = %s", (coach_id,))
        row = cursor.fetchone()
        if not row or not row['gym_id']:
            raise HTTPException(status_code=400, detail="Coach does not have a gym_id")
        gym_id = row['gym_id']

        # Format notes with workout type and exercises
        notes_content = f"Workout Type: {workout_type}"
        
        # Add exercises if provided
        if exercises and len(exercises) > 0:
            notes_content += "\nExercises:\n"
            for i, exercise in enumerate(exercises, 1):
                notes_content += f"{i}. {exercise}\n"
        
        # Add additional notes if provided
        if notes:
            notes_content += f"\n{notes}"
        
        cursor.execute("""
            INSERT INTO sessions (gym_id, coach_id, member_id, session_date, session_time, duration, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled', %s)
        """, (gym_id, coach_id, member_id, session_date, session_time, duration, notes_content))
        conn.commit()
        return {"success": True, "session_id": cursor.lastrowid}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/coach/schedule_view/{coach_id}/{member_id}")
async def get_schedule_view(
    coach_id: int,
    member_id: int,
    week_start: str = Query(..., description="Week start date in YYYY-MM-DD format")
):
    """Get comprehensive schedule view including sessions, preferences, and availability"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        from datetime import datetime, timedelta
        import json
        
        # Parse week start date
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        week_end_date = week_start_date + timedelta(days=6)
        
        # Get coach information
        cursor.execute("SELECT name, specialization FROM coaches WHERE id = %s", (coach_id,))
        coach_info = cursor.fetchone()
        
        # Get member information
        cursor.execute("SELECT name, membership_type FROM members WHERE id = %s", (member_id,))
        member_info = cursor.fetchone()
        
        # Get coach sessions for the week
        cursor.execute("""
            SELECT s.*, m.name as member_name, m.membership_type,
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time,
                   DAYNAME(s.session_date) as day_name,
                   HOUR(s.session_time) as hour_slot
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.coach_id = %s 
            AND s.session_date BETWEEN %s AND %s
            AND s.status != 'Cancelled'
            ORDER BY s.session_date, s.session_time
        """, (coach_id, week_start_date, week_end_date))
        coach_sessions = cursor.fetchall()
        
        # Get member sessions for the week
        cursor.execute("""
            SELECT s.*, c.name as coach_name, c.specialization,
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time,
                   DAYNAME(s.session_date) as day_name,
                   HOUR(s.session_time) as hour_slot
            FROM sessions s
            JOIN coaches c ON s.coach_id = c.id
            WHERE s.member_id = %s 
            AND s.session_date BETWEEN %s AND %s
            AND s.status != 'Cancelled'
            ORDER BY s.session_date, s.session_time
        """, (member_id, week_start_date, week_end_date))
        member_sessions = cursor.fetchall()
        
        # Get coach preferences and availability
        cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s AND user_type = 'coach'", (coach_id,))
        coach_preferences = cursor.fetchone()
        
        cursor.execute("SELECT * FROM free_days WHERE user_id = %s AND user_type = 'coach'", (coach_id,))
        coach_availability = cursor.fetchall()
        
        # Get member preferences and availability
        cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s AND user_type = 'member'", (member_id,))
        member_preferences = cursor.fetchone()
        
        cursor.execute("SELECT * FROM free_days WHERE user_id = %s AND user_type = 'member'", (member_id,))
        member_availability = cursor.fetchall()
        
        # Parse preferred time slots
        coach_preferred_times = []
        if coach_preferences and coach_preferences.get('preferred_time_slots'):
            coach_preferred_times = json.loads(coach_preferences['preferred_time_slots'])
            
        member_preferred_times = []
        if member_preferences and member_preferences.get('preferred_time_slots'):
            member_preferred_times = json.loads(member_preferences['preferred_time_slots'])
        
        # Create a weekly schedule grid (7 days x 24 hours)
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        schedule_grid = {}
        
        for day in days:
            schedule_grid[day] = {}
            for hour in range(24):
                schedule_grid[day][hour] = {
                    'coach_available': False,
                    'member_available': False,
                    'coach_preferred': hour in coach_preferred_times,
                    'member_preferred': hour in member_preferred_times,
                    'coach_session': None,
                    'member_session': None,
                    'available_for_both': False,
                    'preference_score': 0
                }
        
        # Mark coach availability
        for avail in coach_availability:
            if avail['is_available']:
                day = avail['day_of_week']
                start_hour = avail['start_time'].seconds // 3600
                end_hour = avail['end_time'].seconds // 3600
                
                for hour in range(start_hour, min(end_hour, 24)):
                    if day in schedule_grid:
                        schedule_grid[day][hour]['coach_available'] = True
        
        # Mark member availability
        for avail in member_availability:
            if avail['is_available']:
                day = avail['day_of_week']
                start_hour = avail['start_time'].seconds // 3600
                end_hour = avail['end_time'].seconds // 3600
                
                for hour in range(start_hour, min(end_hour, 24)):
                    if day in schedule_grid:
                        schedule_grid[day][hour]['member_available'] = True
        
        # Group coach sessions by day and hour
        coach_sessions_by_slot = {}
        for session in coach_sessions:
            day = session['day_name']
            hour = session['hour_slot']
            slot_key = f"{day}_{hour}"
            
            if slot_key not in coach_sessions_by_slot:
                coach_sessions_by_slot[slot_key] = []
            
            coach_sessions_by_slot[slot_key].append({
                'id': session['id'],
                'member_name': session['member_name'],
                'time': session['formatted_time'],
                'duration': session['duration'],
                'status': session['status'],
                'notes': session['notes'],
                'session_type': session.get('session_type', 'General Training')
            })
        
        # Group member sessions by day and hour
        member_sessions_by_slot = {}
        for session in member_sessions:
            day = session['day_name']
            hour = session['hour_slot']
            slot_key = f"{day}_{hour}"
            
            if slot_key not in member_sessions_by_slot:
                member_sessions_by_slot[slot_key] = []
            
            member_sessions_by_slot[slot_key].append({
                'id': session['id'],
                'coach_name': session['coach_name'],
                'time': session['formatted_time'],
                'duration': session['duration'],
                'status': session['status'],
                'notes': session['notes'],
                'session_type': session.get('session_type', 'General Training')
            })
        
        # Mark coach sessions in schedule grid
        for slot_key, sessions in coach_sessions_by_slot.items():
            day, hour = slot_key.split('_')
            hour = int(hour)
            
            if day in schedule_grid and 0 <= hour < 24:
                if len(sessions) == 1:
                    # Single session - use backward compatibility
                    schedule_grid[day][hour]['coach_session'] = sessions[0]
                else:
                    # Multiple sessions - use new array format
                    schedule_grid[day][hour]['coach_sessions'] = sessions
                
                schedule_grid[day][hour]['coach_available'] = False
        
        # Mark member sessions in schedule grid
        for slot_key, sessions in member_sessions_by_slot.items():
            day, hour = slot_key.split('_')
            hour = int(hour)
            
            if day in schedule_grid and 0 <= hour < 24:
                if len(sessions) == 1:
                    # Single session - use backward compatibility
                    schedule_grid[day][hour]['member_session'] = sessions[0]
                else:
                    # Multiple sessions - use new array format
                    schedule_grid[day][hour]['member_sessions'] = sessions
                
                schedule_grid[day][hour]['member_available'] = False
        
        # Calculate availability for both and preference scores
        for day in days:
            for hour in range(24):
                slot = schedule_grid[day][hour]
                
                # Check if there are any sessions (single or multiple)
                has_coach_session = slot.get('coach_session') is not None or slot.get('coach_sessions') is not None
                has_member_session = slot.get('member_session') is not None or slot.get('member_sessions') is not None
                
                slot['available_for_both'] = (
                    slot['coach_available'] and 
                    slot['member_available'] and
                    not has_coach_session and 
                    not has_member_session
                )
                
                # Calculate preference score
                if slot['available_for_both']:
                    if slot['coach_preferred'] and slot['member_preferred']:
                        slot['preference_score'] = 4
                    elif slot['coach_preferred']:
                        slot['preference_score'] = 3
                    elif slot['member_preferred']:
                        slot['preference_score'] = 2
                    else:
                        slot['preference_score'] = 1
        
        return {
            "success": True,
            "week_start": week_start,
            "week_end": week_end_date.strftime("%Y-%m-%d"),
            "coach": {
                "id": coach_id,
                "name": coach_info['name'] if coach_info else "Unknown",
                "specialization": coach_info['specialization'] if coach_info else "",
                "preferred_times": coach_preferred_times,
                "sessions": coach_sessions
            },
            "member": {
                "id": member_id,
                "name": member_info['name'] if member_info else "Unknown", 
                "membership_type": member_info['membership_type'] if member_info else "Basic",
                "preferred_times": member_preferred_times,
                "sessions": member_sessions
            },
            "schedule_grid": schedule_grid,
            "legend": {
                "preference_scores": {
                    "4": "Both prefer this time",
                    "3": "Coach prefers this time", 
                    "2": "Member prefers this time",
                    "1": "Available but no preference"
                }
            }
        }
        
    except Exception as e:
        print(f"Error getting schedule view: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.post("/api/coach/assign_workout_from_schedule")
async def assign_workout_from_schedule(
    coach_id: int = Body(...),
    member_id: int = Body(...),
    session_date: str = Body(...),
    session_time: str = Body(...),
    duration: int = Body(...),
    workout_type: str = Body(...),
    exercises: List[str] = Body([]),
    notes: str = Body("")
):
    """Assign a workout session from the schedule view"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate the coach and member exist and are associated
        cursor.execute("""
            SELECT 1 FROM member_coach 
            WHERE coach_id = %s AND member_id = %s
        """, (coach_id, member_id))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="Member not assigned to this coach")
        
        # Check for session conflicts
        cursor.execute("""
            SELECT 1 FROM sessions 
            WHERE coach_id = %s 
            AND session_date = %s 
            AND session_time = %s
            AND status != 'Cancelled'
        """, (coach_id, session_date, session_time))
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Coach already has a session at this time")
            
        cursor.execute("""
            SELECT 1 FROM sessions 
            WHERE member_id = %s 
            AND session_date = %s 
            AND session_time = %s
            AND status != 'Cancelled'
        """, (member_id, session_date, session_time))
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Member already has a session at this time")
        
        # Get gym_id for the coach
        cursor.execute("SELECT gym_id FROM coaches WHERE id = %s", (coach_id,))
        gym_data = cursor.fetchone()
        if not gym_data:
            raise HTTPException(status_code=400, detail="Coach not found")
        
        # Format notes with workout type and exercises
        notes_content = f"Workout Type: {workout_type}"
        
        # Add exercises if provided
        if exercises and len(exercises) > 0:
            notes_content += "\nExercises:\n"
            for i, exercise in enumerate(exercises, 1):
                notes_content += f"{i}. {exercise}\n"
        
        # Add additional notes if provided
        if notes:
            notes_content += f"\n{notes}"
        
        # Create the session
        cursor.execute("""
            INSERT INTO sessions (
                gym_id,
                coach_id,
                member_id,
                session_date,
                session_time,
                duration,
                status,
                notes,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled', %s, NOW())
        """, (
            gym_data['gym_id'],
            coach_id,
            member_id,
            session_date,
            session_time,
            duration,
            notes_content
        ))
        
        session_id = cursor.lastrowid
        conn.commit()
        
        # Get the created session details
        cursor.execute("""
            SELECT s.*, m.name as member_name, c.name as coach_name,
                   DATE_FORMAT(s.session_date, '%%Y-%%m-%%d') as formatted_date,
                   TIME_FORMAT(s.session_time, '%%H:%%i') as formatted_time
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            JOIN coaches c ON s.coach_id = c.id
            WHERE s.id = %s
        """, (session_id,))
        
        new_session = cursor.fetchone()
        
        return {
            "success": True,
            "message": "Session assigned successfully",
            "session": {
                "id": new_session['id'],
                "coach_name": new_session['coach_name'],
                "member_name": new_session['member_name'],
                "date": new_session['formatted_date'],
                "time": new_session['formatted_time'],
                "duration": new_session['duration'],
                "session_type": new_session.get('session_type', workout_type),
                "status": new_session['status'],
                "notes": new_session['notes']
            }
        }
        
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        print(f"Error assigning workout from schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/coach/preferences")
async def get_coach_preferences(request: Request):
    """Get coach preferences and availability"""
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated as coach")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get coach info including specialization
        cursor.execute("""
            SELECT name, specialization FROM coaches 
            WHERE id = %s
        """, (user["id"],))
        coach_info = cursor.fetchone()
        
        # Get coach preferences
        cursor.execute("""
            SELECT * FROM user_preferences 
            WHERE user_id = %s AND user_type = 'coach'
        """, (user["id"],))
        preferences = cursor.fetchone()
        
        # Get coach availability
        cursor.execute("""
            SELECT * FROM free_days 
            WHERE user_id = %s AND user_type = 'coach'
            ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (user["id"],))
        free_days = cursor.fetchall()
        
        # Parse preferences if they exist
        parsed_preferences = None
        if preferences:
            import json
            parsed_preferences = {
                'preferred_workout_types': json.loads(preferences['preferred_workout_types']) if preferences['preferred_workout_types'] else [],
                'preferred_duration': preferences['preferred_duration'],
                'preferred_time_slots': json.loads(preferences['preferred_time_slots']) if preferences['preferred_time_slots'] else [],
                'notes': preferences['notes']
            }
        
        return {
            "success": True,
            "coach_info": coach_info,
            "preferences": parsed_preferences,
            "free_days": free_days
        }
        
    except Exception as e:
        print(f"Error getting coach preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# ============================================
# AI CALORIE TRACKER ENDPOINTS
# ============================================

import base64
import io
from PIL import Image
# Free AI Calorie Tracker - No OpenAI API needed!

# AI Calorie Tracker - Photo Analysis (Free TensorFlow.js Version)
@app.post("/api/nutrition/analyze-photo")
async def analyze_food_photo(
    request: Request,
    file: UploadFile = File(...),
    meal_type: str = Form(...),
    detected_foods: str = Form("[]"),
    notes: str = Form("")
):
    """Process food photo analysis results from TensorFlow.js frontend"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check VIP or Premium membership
    if user.get('membership_type') not in ['VIP', 'Premium']:
        raise HTTPException(status_code=403, detail="VIP or Premium membership required for AI Calorie Tracker")
    
    try:
        # Parse detected foods from frontend TensorFlow.js analysis
        try:
            foods_data = json.loads(detected_foods)
        except json.JSONDecodeError:
            foods_data = []
        
        if not foods_data:
            # If no foods detected, create a default entry
            foods_data = [{
                "name": "Unknown Food Item",
                "quantity": 100,
                "calories": 200,
                "protein": 8,
                "carbs": 25,
                "fat": 8,
                "confidence": 0.3
            }]
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        # Save photo file (optional - for basic tracking)
        photo_filename = f"nutrition_{user['id']}_{int(time.time())}.jpg"
        
        for food in foods_data:
            # Save each food item to nutrition_logs
            cursor.execute("""
                INSERT INTO nutrition_logs 
                (member_id, log_date, meal_type, custom_food_name, quantity, unit,
                 total_calories, total_protein, total_carbs, total_fat, 
                 photo_url, ai_confidence, notes)
                VALUES (%s, CURDATE(), %s, %s, %s, 'grams', %s, %s, %s, %s, %s, %s, %s)
            """, (
                user['id'],
                meal_type,
                food['name'],
                food['quantity'],
                food['calories'],
                food['protein'],
                food['carbs'],
                food['fat'],
                photo_filename,
                food['confidence'],
                notes
            ))
            
            total_calories += float(food['calories'])
            total_protein += float(food['protein'])
            total_carbs += float(food['carbs'])
            total_fat += float(food['fat'])
        
        # Generate free AI feedback and save meal analysis
        ai_feedback = generate_free_nutrition_feedback(user['id'], total_calories, total_protein, total_carbs, total_fat)
        suggestions = "Great job tracking your nutrition! Keep logging your meals for better insights."
        
        cursor.execute("""
            INSERT INTO meal_analysis 
            (member_id, analysis_date, total_calories, total_protein, total_carbs, total_fat,
             ai_feedback, suggestions, health_score)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            total_calories = total_calories + VALUES(total_calories),
            total_protein = total_protein + VALUES(total_protein),
            total_carbs = total_carbs + VALUES(total_carbs),
            total_fat = total_fat + VALUES(total_fat),
            ai_feedback = VALUES(ai_feedback),
            suggestions = VALUES(suggestions),
            health_score = VALUES(health_score)
        """, (
            user['id'],
            total_calories,
            total_protein,
            total_carbs,
            total_fat,
            ai_feedback,
            suggestions,
            calculate_health_score(total_calories, total_protein, total_carbs, total_fat)
        ))
        
        conn.commit()
        
        return {
            "success": True,
            "detected_foods": foods_data,
            "total_nutrition": {
                "calories": total_calories,
                "protein": total_protein,
                "carbs": total_carbs,
                "fat": total_fat
            },
            "ai_feedback": ai_feedback,
            "suggestions": suggestions
        }
        
    except Exception as e:
        print(f"Error analyzing food photo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Food Search using Open Food Facts API
@app.get("/api/nutrition/search-food")
async def search_food(
    request: Request,
    query: str = Query(..., description="Food name or barcode"),
    limit: int = Query(10, description="Number of results to return")
):
    """Search for foods using USDA database"""
    try:
        # Search USDA database
        usda_foods = search_usda_foods(query, max_results=limit)
        
        if usda_foods:
            return {
                "success": True,
                "data": usda_foods,
                "source": "USDA",
                "message": f"Found {len(usda_foods)} foods in USDA database"
            }
        else:
            # Fallback to basic search
            return {
                "success": True,
                "data": [],
                "source": "fallback",
                "message": "No foods found in USDA database"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error searching USDA database"
        }

@app.get("/api/nutrition/get-food-nutrition")
async def get_food_nutrition(
    request: Request,
    food_name: str = Query(..., description="Food name to get nutrition for")
):
    """Get detailed nutrition information for a specific food from USDA database"""
    try:
        # Try USDA database first
        nutrition_data = search_and_get_nutrition(food_name)
        
        if nutrition_data:
            return {
                "success": True,
                "data": nutrition_data,
                "source": "USDA",
                "message": "Nutrition data retrieved from USDA database"
            }
        else:
            # Use fallback nutrition
            fallback_data = get_fallback_nutrition(food_name)
            return {
                "success": True,
                "data": fallback_data,
                "source": "fallback",
                "message": "Using estimated nutrition data"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error retrieving nutrition data"
        }

@app.get("/api/nutrition/get-food-nutrition-by-id")
async def get_food_nutrition_by_id(
    request: Request,
    fdc_id: int = Query(..., description="USDA FDC ID to get nutrition for")
):
    """Get detailed nutrition information for a specific food by USDA FDC ID"""
    try:
        # Get nutrition data directly by FDC ID
        nutrition_data = get_usda_food_details(fdc_id)
        
        if nutrition_data:
            return {
                "success": True,
                "data": nutrition_data,
                "source": "USDA",
                "message": "Nutrition data retrieved from USDA database"
            }
        else:
            return {
                "success": False,
                "error": "Food not found",
                "message": "Could not find nutrition data for this food"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error retrieving nutrition data"
        }
    """Search for food items using Open Food Facts API"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Check if query is a barcode (numeric)
        if query.isdigit():
            # Barcode lookup
            url = f"https://world.openfoodfacts.org/api/v2/product/{query}"
        else:
            # Text search
            url = f"https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": query,
                "page_size": limit,
                "json": 1,
                "fields": "product_name,nutriments,brands,categories,image_url"
            }
        
        # Make request to Open Food Facts API
        response = requests.get(url, params=params if not query.isdigit() else None, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if query.isdigit():
            # Single product response
            if data.get('status') == 1:
                product = data['product']
                foods = [{
                    "name": product.get('product_name', 'Unknown'),
                    "brand": product.get('brands', ''),
                    "calories_per_100g": product.get('nutriments', {}).get('energy-kcal_100g', 0),
                    "protein_per_100g": product.get('nutriments', {}).get('proteins_100g', 0),
                    "carbs_per_100g": product.get('nutriments', {}).get('carbohydrates_100g', 0),
                    "fat_per_100g": product.get('nutriments', {}).get('fat_100g', 0),
                    "image_url": product.get('image_url', ''),
                    "barcode": query,
                    "source": "OpenFoodFacts"
                }]
            else:
                foods = []
        else:
            # Search results
            foods = []
            for product in data.get('products', []):
                foods.append({
                    "name": product.get('product_name', 'Unknown'),
                    "brand": product.get('brands', ''),
                    "calories_per_100g": product.get('nutriments', {}).get('energy-kcal_100g', 0),
                    "protein_per_100g": product.get('nutriments', {}).get('proteins_100g', 0),
                    "carbs_per_100g": product.get('nutriments', {}).get('carbohydrates_100g', 0),
                    "fat_per_100g": product.get('nutriments', {}).get('fat_100g', 0),
                    "image_url": product.get('image_url', ''),
                    "barcode": product.get('code', ''),
                    "source": "OpenFoodFacts"
                })
        
        return {
            "success": True,
            "foods": foods,
            "count": len(foods)
        }
        
    except Exception as e:
        print(f"Error searching food: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add food manually
@app.post("/api/nutrition/add-food")
async def add_food_manually(
    request: Request,
    meal_type: str = Form(...),
    food_name: str = Form(...),
    quantity: float = Form(...),
    unit: str = Form("grams"),
    calories: float = Form(...),
    protein: float = Form(0),
    carbs: float = Form(0),
    fat: float = Form(0),
    notes: str = Form("")
):
    """Add food item manually"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check VIP or Premium membership
    if user.get('membership_type') not in ['VIP', 'Premium']:
        raise HTTPException(status_code=403, detail="VIP or Premium membership required for AI Calorie Tracker")
    
    # Validate unit field - must be one of the allowed ENUM values
    allowed_units = ['grams', 'ml', 'pieces', 'cups', 'tablespoons', 'serving']
    if unit not in allowed_units:
        raise HTTPException(status_code=400, detail=f"Invalid unit value. Must be one of: {', '.join(allowed_units)}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Save to nutrition_logs
        cursor.execute("""
            INSERT INTO nutrition_logs 
            (member_id, log_date, meal_type, custom_food_name, quantity, unit,
             total_calories, total_protein, total_carbs, total_fat, notes)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user['id'],
            meal_type,
            food_name,
            quantity,
            unit,
            calories,
            protein,
            carbs,
            fat,
            notes
        ))
        
        # Update daily meal analysis
        ai_feedback = generate_free_nutrition_feedback(user['id'], calories, protein, carbs, fat)
        
        cursor.execute("""
            INSERT INTO meal_analysis 
            (member_id, analysis_date, total_calories, total_protein, total_carbs, total_fat,
             ai_feedback, health_score)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            total_calories = total_calories + VALUES(total_calories),
            total_protein = total_protein + VALUES(total_protein),
            total_carbs = total_carbs + VALUES(total_carbs),
            total_fat = total_fat + VALUES(total_fat),
            ai_feedback = VALUES(ai_feedback),
            health_score = VALUES(health_score)
        """, (
            user['id'],
            calories,
            protein,
            carbs,
            fat,
            ai_feedback,
            calculate_health_score(calories, protein, carbs, fat)
        ))
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Food logged successfully",
            "nutrition": {
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat
            }
        }
        
    except Exception as e:
        print(f"Error adding food manually: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
# Get weekly nutrition progress data
@app.get("/api/nutrition/weekly-progress/{member_id}")
async def get_weekly_nutrition_progress(request: Request, member_id: int):
    """Get weekly nutrition progress data for member"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check access permissions
    if user['user_type'] == 'member' and user['id'] != member_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get nutrition data for the current week (Sunday to Saturday)
        cursor.execute("""
            SELECT 
                DATE(log_date) as date,
                DAYNAME(log_date) as day_name,
                SUM(total_calories) as calories,
                SUM(total_protein) as protein,
                SUM(total_carbs) as carbs,
                SUM(total_fat) as fat
            FROM nutrition_logs 
            WHERE member_id = %s 
            AND log_date >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
            AND log_date <= DATE_ADD(CURDATE(), INTERVAL 6 - WEEKDAY(CURDATE()) DAY)
            GROUP BY DATE(log_date), DAYNAME(log_date)
            ORDER BY date
        """, (member_id,))
        
        weekly_data = cursor.fetchall()
        
        # Create a complete week array (Sunday to Saturday)
        days_of_week = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        complete_week = []
        
        # Get the start of the current week (Sunday)
        cursor.execute("SELECT DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) as week_start")
        week_start_result = cursor.fetchone()
        week_start = week_start_result['week_start'] if week_start_result else datetime.now().date()
        
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            day_name = days_of_week[i]
            
            # Find if we have data for this day
            day_data = next((day for day in weekly_data if day['date'] == current_date), None)
            
            if day_data:
                complete_week.append({
                    'date': day_data['date'].strftime('%Y-%m-%d') if hasattr(day_data['date'], 'strftime') else str(day_data['date']),
                    'day_name': day_data['day_name'],
                    'calories': float(day_data['calories'] or 0),
                    'protein': float(day_data['protein'] or 0),
                    'carbs': float(day_data['carbs'] or 0),
                    'fat': float(day_data['fat'] or 0)
                })
            else:
                complete_week.append({
                    'date': current_date.strftime('%Y-%m-%d') if hasattr(current_date, 'strftime') else str(current_date),
                    'day_name': day_name,
                    'calories': 0,
                    'protein': 0,
                    'carbs': 0,
                    'fat': 0
                })
        
        return {
            "success": True,
            "weekly_data": complete_week
        }
        
    except Exception as e:
        print(f"Error getting weekly nutrition progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Get nutrition dashboard data
@app.get("/api/nutrition/dashboard/{member_id}")
async def get_nutrition_dashboard(request: Request, member_id: int):
    """Get nutrition dashboard data for member"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check access permissions
    if user['user_type'] == 'member' and user['id'] != member_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get today's nutrition
        cursor.execute("""
            SELECT meal_type, 
                   SUM(total_calories) as calories,
                   SUM(total_protein) as protein,
                   SUM(total_carbs) as carbs,
                   SUM(total_fat) as fat
            FROM nutrition_logs 
            WHERE member_id = %s AND log_date = CURDATE()
            GROUP BY meal_type
        """, (member_id,))
        today_meals = cursor.fetchall()
        
        # Get nutrition goals (handle case where table might not exist)
        try:
            cursor.execute("""
                SELECT daily_calorie_goal, daily_protein_goal, daily_carbs_goal, daily_fat_goal,
                       goal_type, dietary_restrictions, allergies
                FROM nutrition_goals 
                WHERE member_id = %s
            """, (member_id,))
            goals = cursor.fetchone() or {
                'daily_calorie_goal': 2000,
                'daily_protein_goal': 150,
                'daily_carbs_goal': 250,
                'daily_fat_goal': 70,
                'goal_type': 'Maintenance'
            }
        except Exception as e:
            print(f"Warning: nutrition_goals table not found or error: {e}")
            goals = {
                'daily_calorie_goal': 2000,
                'daily_protein_goal': 150,
                'daily_carbs_goal': 250,
                'daily_fat_goal': 70,
                'goal_type': 'Maintenance'
            }
        
        # Get recent meal analysis (handle case where table might not exist)
        try:
            cursor.execute("""
                SELECT * FROM meal_analysis 
                WHERE member_id = %s 
                ORDER BY analysis_date DESC 
                LIMIT 7
            """, (member_id,))
            weekly_analysis = cursor.fetchall()
        except Exception as e:
            print(f"Warning: meal_analysis table not found or error: {e}")
            weekly_analysis = []
        
        # Calculate totals for today
        total_calories = sum(meal['calories'] or 0 for meal in today_meals)
        total_protein = sum(meal['protein'] or 0 for meal in today_meals)
        total_carbs = sum(meal['carbs'] or 0 for meal in today_meals)
        total_fat = sum(meal['fat'] or 0 for meal in today_meals)
        
        return {
            "success": True,
            "today": {
                "meals": today_meals,
                "totals": {
                    "calories": total_calories,
                    "protein": total_protein,
                    "carbs": total_carbs,
                    "fat": total_fat
                },
                "goals": goals,
                "progress": {
                    "calories": (total_calories / goals['daily_calorie_goal']) * 100,
                    "protein": (total_protein / goals['daily_protein_goal']) * 100,
                    "carbs": (total_carbs / goals['daily_carbs_goal']) * 100,
                    "fat": (total_fat / goals['daily_fat_goal']) * 100
                }
            },
            "weekly_analysis": weekly_analysis
        }
        
    except Exception as e:
        print(f"Error getting nutrition dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Helper functions - FREE VERSION
def generate_free_nutrition_feedback(member_id: int, calories: float, protein: float, carbs: float, fat: float) -> str:
    """Generate free nutrition feedback using rule-based logic"""
    try:
        # Get member goals
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT daily_calorie_goal, daily_protein_goal, daily_carbs_goal, daily_fat_goal,
                   goal_type FROM nutrition_goals WHERE member_id = %s
        """, (member_id,))
        goals = cursor.fetchone()
        
        if not goals:
            goals = {
                'daily_calorie_goal': 2000,
                'daily_protein_goal': 150,
                'daily_carbs_goal': 250,
                'daily_fat_goal': 70,
                'goal_type': 'Maintenance'
            }
        
        # Calculate percentages
        calorie_percentage = (calories / goals['daily_calorie_goal']) * 100
        protein_percentage = (protein / goals['daily_protein_goal']) * 100
        
        # Generate rule-based feedback
        feedback_parts = []
        
        # Calorie feedback
        if calorie_percentage < 30:
            feedback_parts.append("You're off to a good start today!")
        elif calorie_percentage < 70:
            feedback_parts.append("You're making great progress toward your daily goals!")
        elif calorie_percentage < 100:
            feedback_parts.append("You're almost at your calorie target for today!")
        else:
            feedback_parts.append("You've reached your calorie goal - well done!")
        
        # Protein feedback
        if protein_percentage < 50:
            feedback_parts.append("Consider adding more protein-rich foods to your next meal.")
        elif protein_percentage > 80:
            feedback_parts.append("Excellent protein intake today!")
        
        # Goal-based advice
        goal_advice = {
            'Weight_Loss': "Stay hydrated and focus on whole foods for sustainable weight loss.",
            'Weight_Gain': "Don't forget to include healthy fats and complex carbs for quality weight gain.",
            'Muscle_Gain': "Your protein intake is key for muscle development - keep it consistent!",
            'Maintenance': "Maintaining a balanced approach to nutrition - you're doing great!"
        }
        
        if goals['goal_type'] in goal_advice:
            feedback_parts.append(goal_advice[goals['goal_type']])
        
        return " ".join(feedback_parts)
        
    except Exception as e:
        print(f"Error generating feedback: {str(e)}")
        return "Keep up the great work with your nutrition tracking!"
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def calculate_health_score(calories: float, protein: float, carbs: float, fat: float) -> float:
    """Calculate a simple health score based on macronutrient balance"""
    try:
        # Simple scoring based on balanced macronutrient ratios
        total_macros = protein + carbs + fat
        if total_macros == 0:
            return 5.0
        
        protein_percent = (protein * 4) / calories * 100  # 4 calories per gram protein
        carbs_percent = (carbs * 4) / calories * 100      # 4 calories per gram carbs  
        fat_percent = (fat * 9) / calories * 100          # 9 calories per gram fat
        
        # Ideal ranges: Protein 20-30%, Carbs 45-65%, Fat 20-35%
        protein_score = max(0, 10 - abs(25 - protein_percent) / 2.5)
        carbs_score = max(0, 10 - abs(55 - carbs_percent) / 5)
        fat_score = max(0, 10 - abs(27.5 - fat_percent) / 2.75)
        
        return round((protein_score + carbs_score + fat_score) / 3, 1)
        
    except:
        return 5.0

# Coach nutrition endpoints
@app.get("/api/coach/nutrition/members")
async def get_coach_nutrition_members(request: Request):
    """Get list of coach's members with nutrition data"""
    user = get_current_user(request)
    if not user or user['user_type'] != 'coach':
        raise HTTPException(status_code=403, detail="Coach access required")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach's members with nutrition data
        cursor.execute("""
            SELECT 
                m.id,
                m.name,
                m.email,
                m.membership_type,
                COUNT(n.id) as nutrition_entries,
                AVG(n.total_calories) as avg_calories,
                AVG(n.total_protein) as avg_protein,
                MAX(n.created_at) as last_nutrition_entry
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN nutrition_logs n ON m.id = n.member_id
            WHERE mc.coach_id = %s
            GROUP BY m.id, m.name, m.email, m.membership_type
            ORDER BY m.name
        """, (user['id'],))
        
        members = cursor.fetchall()
        
        # Convert datetime objects
        for member in members:
            if member['last_nutrition_entry']:
                member['last_nutrition_entry'] = member['last_nutrition_entry'].isoformat()
        
        return {
            "success": True,
            "members": members
        }
        
    except Exception as e:
        print(f"Error getting coach nutrition members: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Test endpoint to create sample nutrition data
@app.get("/api/create-sample-nutrition-data")
async def create_sample_nutrition_data():
    """Create sample nutrition data for testing weekly progress"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get a test member (or create one if needed)
        cursor.execute("SELECT id FROM members LIMIT 1")
        member_result = cursor.fetchone()
        
        if not member_result:
            return {"success": False, "detail": "No members found. Please create a member first."}
        
        member_id = member_result['id']
        
        # Create sample nutrition data for today
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        sample_data = [
            # Today's individual food items
            (member_id, 'breakfast', 'Apple', 150, 95, 0, 25, 0, today),
            (member_id, 'breakfast', 'Oatmeal', 100, 350, 12, 60, 8, today),
            (member_id, 'lunch', 'Chicken Breast', 200, 330, 62, 0, 6, today),
            (member_id, 'lunch', 'Brown Rice', 100, 110, 2, 23, 1, today),
            (member_id, 'snack', 'Greek Yogurt', 170, 130, 15, 8, 5, today),
            (member_id, 'dinner', 'Salmon', 150, 280, 34, 0, 12, today),
            (member_id, 'dinner', 'Broccoli', 100, 55, 4, 11, 0, today),
        ]
        
        # Insert sample data
        for data in sample_data:
            cursor.execute("""
                INSERT INTO nutrition_logs 
                (member_id, meal_type, custom_food_name, quantity, total_calories, total_protein, total_carbs, total_fat, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Created {len(sample_data)} sample nutrition entries for member {member_id}",
            "member_id": member_id
        }
        
    except Exception as e:
        print(f"Error creating sample nutrition data: {str(e)}")
        return {"success": False, "detail": str(e)}
    finally:
        cursor.close()
        conn.close()

# Get weekly nutrition progress data

# Comprehensive Coach Nutrition Management System

@app.get("/coach/nutrition", response_class=HTMLResponse)
async def get_coach_nutrition_page(request: Request):
    """Coach nutrition management page"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("coach/nutrition.html", {
        "request": request,
        "user": user
    })

@app.get("/api/coach/nutrition/dashboard")
async def get_coach_nutrition_dashboard(request: Request):
    """Get comprehensive nutrition dashboard for coach"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get overall nutrition statistics for coach's members
        query = """
            SELECT 
                COUNT(DISTINCT m.id) as total_members,
                COUNT(DISTINCT n.member_id) as members_with_nutrition,
                COUNT(n.id) as total_nutrition_entries,
                AVG(n.total_calories) as avg_calories,
                AVG(n.total_protein) as avg_protein,
                AVG(n.total_carbs) as avg_carbs,
                AVG(n.total_fat) as avg_fat,
                SUM(CASE WHEN n.total_calories > 0 THEN 1 ELSE 0 END) as days_with_entries
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN nutrition_logs n ON m.id = n.member_id
            WHERE mc.coach_id = %s
        """
        
        cursor.execute(query, (user['id'],))
        stats = cursor.fetchone()
        
        # Get recent nutrition entries
        recent_query = """
            SELECT 
                n.id,
                n.member_id,
                m.name,
                n.meal_type,
                COALESCE(n.custom_food_name, fi.name) as food_name,
                n.total_calories as calories,
                n.total_protein as protein,
                n.total_carbs as carbs,
                n.total_fat as fat,
                n.created_at
            FROM nutrition_logs n
            JOIN members m ON n.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN food_items fi ON n.food_item_id = fi.id
            WHERE mc.coach_id = %s
            ORDER BY n.created_at DESC
            LIMIT 5
        """
        
        cursor.execute(recent_query, (user['id'],))
        recent_entries = cursor.fetchall()
        
        # Convert datetime objects
        for entry in recent_entries:
            if entry['created_at']:
                entry['created_at'] = entry['created_at'].isoformat()
        
        # Get nutrition trends by member
        trends_query = """
            SELECT 
                m.id,
                m.name,
                DATE(n.created_at) as date,
                AVG(n.total_calories) as avg_calories,
                AVG(n.total_protein) as avg_protein,
                AVG(n.total_carbs) as avg_carbs,
                AVG(n.total_fat) as avg_fat,
                COUNT(n.id) as entries_count
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN nutrition_logs n ON m.id = n.member_id
            WHERE mc.coach_id = %s 
            AND n.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY m.id, DATE(n.created_at)
            ORDER BY m.name, date DESC
        """
        
        cursor.execute(trends_query, (user['id'],))
        trends = cursor.fetchall()
        
        # Convert datetime objects
        for trend in trends:
            if trend['date']:
                trend['date'] = trend['date'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "stats": stats,
            "recent_entries": recent_entries,
            "trends": trends
        }
        
    except Exception as e:
        print(f"Error getting coach nutrition dashboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/coach/nutrition/member/{member_id}")
async def get_coach_member_nutrition(request: Request, member_id: int):
    """Get detailed nutrition data for a specific member"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify member belongs to this coach
        member_query = """
            SELECT m.id, m.name as first_name, m.name as last_name, m.email, m.membership_type
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """
        cursor.execute(member_query, (member_id, user['id']))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Get member's nutrition data
        nutrition_query = """
            SELECT 
                n.id,
                n.meal_type,
                COALESCE(n.custom_food_name, fi.name) as food_name,
                n.quantity,
                n.unit,
                n.total_calories as calories,
                n.total_protein as protein,
                n.total_carbs as carbs,
                n.total_fat as fat,
                n.notes,
                n.created_at
            FROM nutrition_logs n
            LEFT JOIN food_items fi ON n.food_item_id = fi.id
            WHERE n.member_id = %s
            ORDER BY n.created_at DESC
            LIMIT 50
        """
        
        cursor.execute(nutrition_query, (member_id,))
        nutrition_entries = cursor.fetchall()
        
        # Convert datetime objects
        for entry in nutrition_entries:
            if entry['created_at']:
                entry['created_at'] = entry['created_at'].isoformat()
        
        # Get weekly summary
        weekly_query = """
            SELECT 
                DATE(created_at) as date,
                SUM(total_calories) as total_calories,
                SUM(total_protein) as total_protein,
                SUM(total_carbs) as total_carbs,
                SUM(total_fat) as total_fat,
                COUNT(*) as entries_count
            FROM nutrition_logs
            WHERE member_id = %s 
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """
        
        cursor.execute(weekly_query, (member_id,))
        weekly_summary = cursor.fetchall()
        
        # Convert datetime objects
        for summary in weekly_summary:
            if summary['date']:
                summary['date'] = summary['date'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "member": member,
            "nutrition_entries": nutrition_entries,
            "weekly_summary": weekly_summary
        }
        
    except Exception as e:
        print(f"Error getting member nutrition: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/coach/nutrition/feedback")
async def add_nutrition_feedback(
    request: Request,
    member_id: int = Form(...),
    feedback_type: str = Form(...),
    message: str = Form(...),
    rating: int = Form(5)
):
    """Add nutrition feedback for a member"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify member belongs to this coach
        member_query = """
            SELECT m.id FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """
        cursor.execute(member_query, (member_id, user['id']))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Insert nutrition feedback
        insert_query = """
            INSERT INTO nutrition_feedback 
            (coach_id, member_id, feedback_type, message, rating, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(insert_query, (
            user['id'], member_id, feedback_type, message, rating
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Nutrition feedback added successfully"
        }
        
    except Exception as e:
        print(f"Error adding nutrition feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/coach/nutrition/analytics")
async def get_coach_nutrition_analytics(
    request: Request,
    time_range: str = "week",
    member_id: int = None
):
    """Get nutrition analytics for coach's members"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Determine date range
        if time_range == "week":
            date_filter = "AND n.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif time_range == "month":
            date_filter = "AND n.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif time_range == "quarter":
            date_filter = "AND n.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)"
        else:
            date_filter = ""
        
        # Build member filter
        member_filter = ""
        if member_id:
            member_filter = f"AND m.id = {member_id}"
        
        # Get nutrition analytics
        analytics_query = f"""
            SELECT 
                m.id,
                m.name as first_name,
                m.name as last_name,
                AVG(n.total_calories) as avg_calories,
                AVG(n.total_protein) as avg_protein,
                AVG(n.total_carbs) as avg_carbs,
                AVG(n.total_fat) as avg_fat,
                COUNT(n.id) as total_entries,
                COUNT(DISTINCT DATE(n.created_at)) as active_days,
                SUM(CASE WHEN n.total_calories > 0 THEN 1 ELSE 0 END) as days_with_entries
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN nutrition_logs n ON m.id = n.member_id
            WHERE mc.coach_id = %s {member_filter} {date_filter}
            GROUP BY m.id
            ORDER BY avg_calories DESC
        """
        
        cursor.execute(analytics_query, (user['id'],))
        analytics = cursor.fetchall()
        
        # Split names for analytics data
        for member in analytics:
            name_parts = member['first_name'].split(' ', 1)
            member['first_name'] = name_parts[0]
            member['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        
        # Get meal type distribution
        meal_distribution_query = f"""
            SELECT 
                n.meal_type,
                COUNT(*) as count,
                AVG(n.total_calories) as avg_calories
            FROM nutrition_logs n
            JOIN members m ON n.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE mc.coach_id = %s {member_filter} {date_filter}
            GROUP BY n.meal_type
            ORDER BY count DESC
        """
        
        cursor.execute(meal_distribution_query, (user['id'],))
        meal_distribution = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "analytics": analytics,
            "meal_distribution": meal_distribution
        }
        
    except Exception as e:
        print(f"Error getting nutrition analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/coach/nutrition/plan")
async def create_nutrition_plan(
    request: Request,
    member_id: int = Form(...),
    plan_name: str = Form(...),
    daily_calories: int = Form(...),
    daily_protein: int = Form(...),
    daily_carbs: int = Form(...),
    daily_fat: int = Form(...),
    notes: str = Form("")
):
    """Create a nutrition plan for a member"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify member belongs to this coach
        member_query = """
            SELECT m.id FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """
        cursor.execute(member_query, (member_id, user['id']))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Insert nutrition plan
        insert_query = """
            INSERT INTO nutrition_plans 
            (coach_id, member_id, plan_name, daily_calories, daily_protein, daily_carbs, daily_fat, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(insert_query, (
            user['id'], member_id, plan_name, daily_calories, daily_protein, daily_carbs, daily_fat, notes
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Nutrition plan created successfully"
        }
        
    except Exception as e:
        print(f"Error creating nutrition plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
@app.get("/api/coach/nutrition/plans/{member_id}")
async def get_member_nutrition_plans(request: Request, member_id: int):
    """Get nutrition plans for a specific member"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        print(f"Debug: Checking member {member_id} for coach {user['id']}")
        
        # First check if the member exists at all
        member_exists_query = """
            SELECT id, name, email 
            FROM members 
            WHERE id = %s
        """
        cursor.execute(member_exists_query, (member_id,))
        member_exists = cursor.fetchone()
        
        if not member_exists:
            print(f"Debug: Member {member_id} does not exist in database")
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Then verify member belongs to this coach and get member details
        member_query = """
            SELECT m.id, m.name, m.email 
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE m.id = %s AND mc.coach_id = %s
        """
        cursor.execute(member_query, (member_id, user['id']))
        member = cursor.fetchone()
        
        if not member:
            print(f"Debug: Member {member_id} exists but not assigned to coach {user['id']}")
            raise HTTPException(status_code=403, detail="Member not assigned to this coach")
        
        print(f"Debug: Found member {member['name']}")
        
        # Get nutrition plans
        plans_query = """
            SELECT 
                id,
                plan_name,
                daily_calories,
                daily_protein,
                daily_carbs,
                daily_fat,
                notes,
                created_at,
                is_active,
                created_at as updated_at
            FROM nutrition_plans
            WHERE member_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(plans_query, (member_id,))
        plans = cursor.fetchall()
        
        print(f"Debug: Found {len(plans)} nutrition plans for member {member_id}")
        
        # Convert datetime objects and boolean status to string
        for plan in plans:
            if plan['created_at']:
                plan['created_at'] = plan['created_at'].isoformat()
            if plan['updated_at']:
                plan['updated_at'] = plan['updated_at'].isoformat()
            
            # Convert boolean is_active to string status
            plan['status'] = 'active' if plan['is_active'] else 'inactive'
            del plan['is_active']  # Remove the original boolean field
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "member": member,
            "plans": plans
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error getting nutrition plans: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Get single nutrition plan for editing
@app.get("/api/coach/nutrition/plan/{plan_id}")
async def get_nutrition_plan(plan_id: int, request: Request):
    """Get a single nutrition plan for editing"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get plan and verify coach has access
        plan_query = """
            SELECT np.*, m.name as member_name
            FROM nutrition_plans np
            JOIN members m ON np.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE np.id = %s AND mc.coach_id = %s
        """
        cursor.execute(plan_query, (plan_id, user['id']))
        plan = cursor.fetchone()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found or access denied")
        
        # Convert datetime objects
        if plan['created_at']:
            plan['created_at'] = plan['created_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plan": plan
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting nutrition plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Update nutrition plan
@app.put("/api/coach/nutrition/plan/{plan_id}")
async def update_nutrition_plan(plan_id: int, request: Request):
    """Update a nutrition plan"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
        plan_name = body.get('plan_name')
        daily_calories = body.get('daily_calories')
        daily_protein = body.get('daily_protein')
        daily_carbs = body.get('daily_carbs')
        daily_fat = body.get('daily_fat')
        notes = body.get('notes', '')
        
        if not all([plan_name, daily_calories, daily_protein, daily_carbs, daily_fat]):
            raise HTTPException(status_code=400, detail="All fields are required")
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify coach has access to this plan
        verify_query = """
            SELECT np.id FROM nutrition_plans np
            JOIN members m ON np.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE np.id = %s AND mc.coach_id = %s
        """
        cursor.execute(verify_query, (plan_id, user['id']))
        plan_exists = cursor.fetchone()
        
        if not plan_exists:
            raise HTTPException(status_code=404, detail="Plan not found or access denied")
        
        # Update the plan
        update_query = """
            UPDATE nutrition_plans 
            SET plan_name = %s, daily_calories = %s, daily_protein = %s, 
                daily_carbs = %s, daily_fat = %s, notes = %s
            WHERE id = %s
        """
        cursor.execute(update_query, (
            plan_name, daily_calories, daily_protein, daily_carbs, daily_fat, notes, plan_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Nutrition plan updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating nutrition plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Delete nutrition plan
@app.delete("/api/coach/nutrition/plan/{plan_id}")
async def delete_nutrition_plan(plan_id: int, request: Request):
    """Delete a nutrition plan"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify coach has access to this plan
        verify_query = """
            SELECT np.id FROM nutrition_plans np
            JOIN members m ON np.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE np.id = %s AND mc.coach_id = %s
        """
        cursor.execute(verify_query, (plan_id, user['id']))
        plan_exists = cursor.fetchone()
        
        if not plan_exists:
            raise HTTPException(status_code=404, detail="Plan not found or access denied")
        
        # Delete the plan
        delete_query = "DELETE FROM nutrition_plans WHERE id = %s"
        cursor.execute(delete_query, (plan_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Nutrition plan deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting nutrition plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Member nutrition plans endpoint
@app.get("/api/member/nutrition/plans")
async def get_member_nutrition_plans_for_current_user(request: Request):
    """Get nutrition plans for the current member user"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get nutrition plans for the current member
        plans_query = """
            SELECT 
                id,
                plan_name,
                daily_calories,
                daily_protein,
                daily_carbs,
                daily_fat,
                notes,
                created_at,
                is_active as status
            FROM nutrition_plans
            WHERE member_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(plans_query, (user['id'],))
        plans = cursor.fetchall()
        
        # Convert datetime objects
        for plan in plans:
            if plan['created_at']:
                plan['created_at'] = plan['created_at'].isoformat()
            # Use created_at as updated_at since there's no updated_at column
            plan['updated_at'] = plan['created_at']
            # Convert is_active to status string
            plan['status'] = 'active' if plan['status'] else 'inactive'
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plans": plans
        }
        
    except Exception as e:
        print(f"Error getting member nutrition plans: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Get detailed nutrition plan with meal data
@app.get("/api/member/nutrition/plans/{plan_id}/details")
async def get_member_nutrition_plan_details(plan_id: int, request: Request):
    """Get detailed nutrition plan with meal data for the current member user"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get detailed nutrition plan including plan_data
        plan_query = """
            SELECT 
                id,
                plan_name,
                daily_calories,
                daily_protein,
                daily_carbs,
                daily_fat,
                notes,
                plan_data,
                created_at,
                is_active as status
            FROM nutrition_plans
            WHERE id = %s AND member_id = %s
        """
        
        cursor.execute(plan_query, (plan_id, user['id']))
        plan = cursor.fetchone()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found or access denied")
        
        # Convert datetime objects
        if plan['created_at']:
            plan['created_at'] = plan['created_at'].isoformat()
        plan['updated_at'] = plan['created_at']
        plan['status'] = 'active' if plan['status'] else 'inactive'
        
        # Parse plan_data JSON if it exists
        if plan['plan_data']:
            try:
                import json
                plan['plan_data'] = json.loads(plan['plan_data'])
            except (json.JSONDecodeError, TypeError):
                plan['plan_data'] = None
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plan": plan
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting nutrition plan details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Get member's selected nutrition plan (for coaches)
@app.get("/api/coach/nutrition/member/{member_id}/selected-plan")
async def get_coach_member_selected_plan(member_id: int, request: Request):
    """Get the currently selected nutrition plan for a member (coach access)"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify the member belongs to this coach
        coach_member_query = """
            SELECT mc.member_id 
            FROM member_coach mc 
            WHERE mc.coach_id = %s AND mc.member_id = %s
        """
        cursor.execute(coach_member_query, (user['id'], member_id))
        coach_member = cursor.fetchone()
        
        if not coach_member:
            raise HTTPException(status_code=403, detail="Member not assigned to this coach")
        
        # Get member's selected plan
        selected_plan_query = """
            SELECT 
                np.id,
                np.plan_name,
                np.daily_calories,
                np.daily_protein,
                np.daily_carbs,
                np.daily_fat,
                np.notes,
                np.created_at,
                np.is_active as status,
                mps.is_default
            FROM member_plan_selections mps
            JOIN nutrition_plans np ON mps.selected_plan_id = np.id
            WHERE mps.member_id = %s
        """
        
        cursor.execute(selected_plan_query, (member_id,))
        selected_plan = cursor.fetchone()
        
        # If no selected plan, get the most recent plan
        if not selected_plan:
            recent_plan_query = """
                SELECT 
                    id,
                    plan_name,
                    daily_calories,
                    daily_protein,
                    daily_carbs,
                    daily_fat,
                    notes,
                    created_at,
                    is_active as status
                FROM nutrition_plans
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(recent_plan_query, (member_id,))
            selected_plan = cursor.fetchone()
            
            if selected_plan:
                selected_plan['is_default'] = True
                # Convert datetime objects
                if selected_plan['created_at']:
                    selected_plan['created_at'] = selected_plan['created_at'].isoformat()
                selected_plan['status'] = 'active' if selected_plan['status'] else 'inactive'
        
        # If still no plan, return default values
        if not selected_plan:
            selected_plan = {
                'id': None,
                'plan_name': 'Default Plan',
                'daily_calories': 2000,
                'daily_protein': 150,
                'daily_carbs': 250,
                'daily_fat': 70,
                'notes': 'Default nutrition goals',
                'created_at': None,
                'status': 'default',
                'is_default': True
            }
        else:
            # Convert datetime objects
            if selected_plan['created_at']:
                selected_plan['created_at'] = selected_plan['created_at'].isoformat()
            selected_plan['status'] = 'active' if selected_plan['status'] else 'inactive'
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plan": selected_plan
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting coach member selected plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Get member's selected nutrition plan
@app.get("/api/member/nutrition/selected-plan")
async def get_member_selected_plan(request: Request):
    """Get the currently selected nutrition plan for the member"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get member's selected plan
        selected_plan_query = """
            SELECT 
                np.id,
                np.plan_name,
                np.daily_calories,
                np.daily_protein,
                np.daily_carbs,
                np.daily_fat,
                np.notes,
                np.created_at,
                np.is_active as status,
                mps.is_default
            FROM member_plan_selections mps
            JOIN nutrition_plans np ON mps.selected_plan_id = np.id
            WHERE mps.member_id = %s
        """
        
        cursor.execute(selected_plan_query, (user['id'],))
        selected_plan = cursor.fetchone()
        
        # If no selected plan, get the most recent plan
        if not selected_plan:
            recent_plan_query = """
                SELECT 
                    id,
                    plan_name,
                    daily_calories,
                    daily_protein,
                    daily_carbs,
                    daily_fat,
                    notes,
                    created_at,
                    is_active as status
                FROM nutrition_plans
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(recent_plan_query, (user['id'],))
            selected_plan = cursor.fetchone()
            
            if selected_plan:
                selected_plan['is_default'] = True
                # Convert datetime objects
                if selected_plan['created_at']:
                    selected_plan['created_at'] = selected_plan['created_at'].isoformat()
                selected_plan['status'] = 'active' if selected_plan['status'] else 'inactive'
        
        # If still no plan, return default values
        if not selected_plan:
            selected_plan = {
                'id': None,
                'plan_name': 'Default Plan',
                'daily_calories': 2000,
                'daily_protein': 150,
                'daily_carbs': 250,
                'daily_fat': 70,
                'notes': 'Default nutrition goals',
                'created_at': None,
                'status': 'default',
                'is_default': True
            }
        else:
            # Convert datetime objects
            if selected_plan['created_at']:
                selected_plan['created_at'] = selected_plan['created_at'].isoformat()
            selected_plan['status'] = 'active' if selected_plan['status'] else 'inactive'
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plan": selected_plan
        }
        
    except Exception as e:
        print(f"Error getting member selected plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Set member's selected nutrition plan
@app.post("/api/member/nutrition/select-plan")
async def select_member_plan(request: Request):
    """Set a nutrition plan as the member's active plan"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
        plan_id = body.get('plan_id')
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify the plan belongs to this member
        if plan_id:
            verify_query = """
                SELECT id FROM nutrition_plans 
                WHERE id = %s AND member_id = %s
            """
            cursor.execute(verify_query, (plan_id, user['id']))
            plan_exists = cursor.fetchone()
            
            if not plan_exists:
                raise HTTPException(status_code=404, detail="Plan not found or access denied")
        
        # Check if member already has a selection
        check_query = """
            SELECT id FROM member_plan_selections 
            WHERE member_id = %s
        """
        cursor.execute(check_query, (user['id'],))
        existing_selection = cursor.fetchone()
        
        if existing_selection:
            # Update existing selection
            if plan_id:
                update_query = """
                    UPDATE member_plan_selections 
                    SET selected_plan_id = %s, is_default = FALSE, updated_at = NOW()
                    WHERE member_id = %s
                """
                cursor.execute(update_query, (plan_id, user['id']))
            else:
                # Set to default (no plan selected)
                update_query = """
                    UPDATE member_plan_selections 
                    SET selected_plan_id = NULL, is_default = TRUE, updated_at = NOW()
                    WHERE member_id = %s
                """
                cursor.execute(update_query, (user['id'],))
        else:
            # Create new selection
            insert_query = """
                INSERT INTO member_plan_selections 
                (member_id, selected_plan_id, is_default, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
            """
            is_default = not bool(plan_id)
            cursor.execute(insert_query, (user['id'], plan_id, is_default))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "message": "Plan selected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error selecting member plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Member today's nutrition data endpoint
@app.get("/api/member/nutrition/today")
async def get_member_today_nutrition(request: Request):
    """Get today's nutrition data for the current member user"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'member':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get today's nutrition entries for the member
        today_query = """
            SELECT 
                SUM(total_calories) as total_calories,
                SUM(total_protein) as total_protein,
                SUM(total_carbs) as total_carbs,
                SUM(total_fat) as total_fat,
                COUNT(*) as entries_count
            FROM nutrition_logs
            WHERE member_id = %s 
            AND DATE(created_at) = CURDATE()
        """
        
        cursor.execute(today_query, (user['id'],))
        today_data = cursor.fetchone()
        
        # Get today's individual food entries
        meals_query = """
            SELECT 
                id,
                meal_type,
                custom_food_name,
                quantity,
                unit,
                total_calories as calories,
                total_protein as protein,
                total_carbs as carbs,
                total_fat as fat,
                notes,
                created_at
            FROM nutrition_logs
            WHERE member_id = %s 
            AND DATE(created_at) = CURDATE()
            ORDER BY created_at DESC
        """
        
        cursor.execute(meals_query, (user['id'],))
        meals_data = cursor.fetchall()
        
        # Get member's selected nutrition plan
        selected_plan_query = """
            SELECT 
                np.id,
                np.plan_name,
                np.daily_calories,
                np.daily_protein,
                np.daily_carbs,
                np.daily_fat,
                np.notes,
                np.is_active,
                mps.is_default
            FROM member_plan_selections mps
            JOIN nutrition_plans np ON mps.selected_plan_id = np.id
            WHERE mps.member_id = %s
        """
        
        cursor.execute(selected_plan_query, (user['id'],))
        selected_plan = cursor.fetchone()
        
        # If no selected plan, get the most recent plan
        if not selected_plan:
            recent_plan_query = """
                SELECT 
                    id,
                    plan_name,
                    daily_calories,
                    daily_protein,
                    daily_carbs,
                    daily_fat,
                    notes,
                    is_active
                FROM nutrition_plans
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(recent_plan_query, (user['id'],))
            selected_plan = cursor.fetchone()
            
            if selected_plan:
                selected_plan['is_default'] = True
        
        # If still no plan, use default values
        if not selected_plan:
            selected_plan = {
                'id': None,
                'plan_name': 'Default Plan',
                'daily_calories': 2000,
                'daily_protein': 150,
                'daily_carbs': 250,
                'daily_fat': 70,
                'notes': 'Default nutrition goals',
                'is_active': 0,
                'is_default': True
            }
        
        # Calculate totals (handle None values)
        total_calories = float(today_data['total_calories'] or 0)
        total_protein = float(today_data['total_protein'] or 0)
        total_carbs = float(today_data['total_carbs'] or 0)
        total_fat = float(today_data['total_fat'] or 0)
        
        # Calculate progress percentages based on selected plan
        calories_progress = (total_calories / selected_plan['daily_calories']) * 100 if selected_plan['daily_calories'] > 0 else 0
        protein_progress = (total_protein / selected_plan['daily_protein']) * 100 if selected_plan['daily_protein'] > 0 else 0
        carbs_progress = (total_carbs / selected_plan['daily_carbs']) * 100 if selected_plan['daily_carbs'] > 0 else 0
        fat_progress = (total_fat / selected_plan['daily_fat']) * 100 if selected_plan['daily_fat'] > 0 else 0
        
        # Convert datetime objects for meals
        for meal in meals_data:
            if meal['created_at']:
                meal['created_at'] = meal['created_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "today": {
                "total_calories": total_calories,
                "total_protein": total_protein,
                "total_carbs": total_carbs,
                "total_fat": total_fat,
                "entries_count": int(today_data['entries_count'] or 0)
            },
            "goals": {
                "daily_calorie_goal": selected_plan['daily_calories'],
                "daily_protein_goal": selected_plan['daily_protein'],
                "daily_carbs_goal": selected_plan['daily_carbs'],
                "daily_fat_goal": selected_plan['daily_fat']
            },
            "progress": {
                "calories": calories_progress,
                "protein": protein_progress,
                "carbs": carbs_progress,
                "fat": fat_progress
            },
            "meals": meals_data,
            "selected_plan": selected_plan
        }
        
    except Exception as e:
        print(f"Error getting member today's nutrition: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Coach member today's nutrition data endpoint
@app.get("/api/coach/nutrition/member/{member_id}/today")
async def get_coach_member_today_nutrition(request: Request, member_id: int):
    """Get today's nutrition data for a specific member (coach access)"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verify coach has access to this member
        coach_member_query = """
            SELECT m.id, m.first_name, m.last_name, m.email
            FROM members m
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE mc.coach_id = %s AND m.id = %s
        """
        
        cursor.execute(coach_member_query, (user['id'], member_id))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=403, detail="Access denied to this member")
        
        # Get today's nutrition entries for the member
        today_query = """
            SELECT 
                SUM(total_calories) as total_calories,
                SUM(total_protein) as total_protein,
                SUM(total_carbs) as total_carbs,
                SUM(total_fat) as total_fat,
                COUNT(*) as entries_count
            FROM nutrition_logs
            WHERE member_id = %s 
            AND DATE(created_at) = CURDATE()
        """
        
        cursor.execute(today_query, (member_id,))
        today_data = cursor.fetchone()
        
        # Get today's individual food entries
        meals_query = """
            SELECT 
                id,
                meal_type,
                custom_food_name,
                quantity,
                unit,
                total_calories as calories,
                total_protein as protein,
                total_carbs as carbs,
                total_fat as fat,
                notes,
                created_at
            FROM nutrition_logs
            WHERE member_id = %s 
            AND DATE(created_at) = CURDATE()
            ORDER BY created_at DESC
        """
        
        cursor.execute(meals_query, (member_id,))
        meals_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "member": member,
            "today": {
                "total_calories": float(today_data['total_calories'] or 0),
                "total_protein": float(today_data['total_protein'] or 0),
                "total_carbs": float(today_data['total_carbs'] or 0),
                "total_fat": float(today_data['total_fat'] or 0),
                "entries_count": int(today_data['entries_count'] or 0)
            },
            "meals": meals_data
        }
        
    except Exception as e:
        print(f"Error getting coach member today's nutrition: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Coach nutrition plans for all members endpoint
@app.get("/api/coach/nutrition/all-plans")
async def get_all_member_nutrition_plans(request: Request):
    """Get nutrition plans for all coach's members"""
    user = get_current_user(request)
    if not user or user.get('user_type') != 'coach':
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get all nutrition plans for coach's members
        plans_query = """
            SELECT 
                np.id,
                np.plan_name,
                np.daily_calories,
                np.daily_protein,
                np.daily_carbs,
                np.daily_fat,
                np.notes,
                np.created_at,
                np.is_active,
                m.id as member_id,
                m.name,
                m.email
            FROM nutrition_plans np
            JOIN members m ON np.member_id = m.id
            JOIN member_coach mc ON m.id = mc.member_id
            WHERE mc.coach_id = %s
            ORDER BY np.created_at DESC
        """
        
        cursor.execute(plans_query, (user['id'],))
        plans = cursor.fetchall()
        
        # Convert datetime objects and organize by member
        members_plans = {}
        for plan in plans:
            if plan['created_at']:
                plan['created_at'] = plan['created_at'].isoformat()
            # Use created_at as updated_at since there's no updated_at column
            plan['updated_at'] = plan['created_at']
            # Convert boolean is_active to string status
            plan['status'] = 'active' if plan['is_active'] else 'inactive'
            del plan['is_active']  # Remove the original boolean field
            
            member_id = plan['member_id']
            if member_id not in members_plans:
                members_plans[member_id] = {
                    'member': {
                        'id': member_id,
                        'name': plan['name'],
                        'email': plan['email']
                    },
                    'plans': []
                }
            members_plans[member_id]['plans'].append(plan)
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "members_plans": list(members_plans.values())
        }
        
    except Exception as e:
        print(f"Error getting all member nutrition plans: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# AI Meal Planning Endpoints
@app.get("/api/nutrition/ai-status")
async def get_ai_meal_planner_status():
    """Check if AI meal planner is available"""
    try:
        if meal_planner and meal_planner.is_available():
            return {"status": "available", "message": "AI meal planner is ready"}
        else:
            return {"status": "unavailable", "message": "AI meal planner not available. Check GEMINI_API_KEY configuration."}
    except Exception as e:
        return {"status": "error", "message": f"Error checking AI status: {str(e)}"}

@app.post("/api/nutrition/generate-meal-plan")
async def generate_ai_meal_plan(request: Request):
    """Generate a personalized meal plan using AI"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Check if user has premium membership for AI features
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT membership_type FROM members WHERE id = %s", (user['id'],))
            member = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not member or member['membership_type'] not in ['Premium', 'VIP']:
                raise HTTPException(status_code=403, detail="AI meal planning requires Premium or VIP membership")
        
        # Get request data
        data = await request.json()
        user_profile = data.get('user_profile', {})
        plan_name = data.get('plan_name', f"AI Generated Plan - {datetime.now().strftime('%Y-%m-%d')}")
        
        if not meal_planner or not meal_planner.is_available():
            # Provide a fallback meal plan when AI is not available
            fallback_plan = {
                "meal_plan": {
                    "day_1": {
                        "breakfast": {"name": "Oatmeal with Berries", "ingredients": ["Oatmeal", "Mixed berries", "Honey"], "nutrition": {"calories": 300, "protein": 8, "carbs": 55, "fat": 5}},
                        "lunch": {"name": "Grilled Chicken Salad", "ingredients": ["Chicken breast", "Mixed greens", "Olive oil"], "nutrition": {"calories": 400, "protein": 35, "carbs": 10, "fat": 20}},
                        "dinner": {"name": "Salmon with Vegetables", "ingredients": ["Salmon fillet", "Broccoli", "Quinoa"], "nutrition": {"calories": 500, "protein": 40, "carbs": 30, "fat": 25}},
                        "snack_1": {"name": "Greek Yogurt", "ingredients": ["Greek yogurt", "Nuts"], "nutrition": {"calories": 200, "protein": 15, "carbs": 10, "fat": 10}},
                        "snack_2": {"name": "Apple with Peanut Butter", "ingredients": ["Apple", "Peanut butter"], "nutrition": {"calories": 150, "protein": 5, "carbs": 20, "fat": 8}}
                    },
                    "day_2": {
                        "breakfast": {"name": "Greek Yogurt Parfait", "ingredients": ["Greek yogurt", "Granola", "Banana"], "nutrition": {"calories": 350, "protein": 20, "carbs": 45, "fat": 8}},
                        "lunch": {"name": "Turkey Wrap", "ingredients": ["Turkey breast", "Whole wheat tortilla", "Avocado"], "nutrition": {"calories": 450, "protein": 30, "carbs": 35, "fat": 22}},
                        "dinner": {"name": "Lean Beef Stir Fry", "ingredients": ["Lean beef", "Brown rice", "Mixed vegetables"], "nutrition": {"calories": 550, "protein": 45, "carbs": 40, "fat": 20}},
                        "snack_1": {"name": "Protein Smoothie", "ingredients": ["Protein powder", "Almond milk", "Berries"], "nutrition": {"calories": 180, "protein": 25, "carbs": 15, "fat": 3}},
                        "snack_2": {"name": "Mixed Nuts", "ingredients": ["Almonds", "Walnuts", "Cashews"], "nutrition": {"calories": 170, "protein": 6, "carbs": 8, "fat": 15}}
                    },
                    "day_3": {
                        "breakfast": {"name": "Protein Pancakes", "ingredients": ["Protein powder", "Oats", "Eggs", "Banana"], "nutrition": {"calories": 400, "protein": 25, "carbs": 50, "fat": 12}},
                        "lunch": {"name": "Tuna Salad", "ingredients": ["Tuna", "Mixed greens", "Olive oil", "Cucumber"], "nutrition": {"calories": 380, "protein": 35, "carbs": 8, "fat": 18}},
                        "dinner": {"name": "Chicken Breast with Sweet Potato", "ingredients": ["Chicken breast", "Sweet potato", "Green beans"], "nutrition": {"calories": 520, "protein": 42, "carbs": 45, "fat": 18}},
                        "snack_1": {"name": "Cottage Cheese", "ingredients": ["Cottage cheese", "Pineapple"], "nutrition": {"calories": 160, "protein": 18, "carbs": 12, "fat": 4}},
                        "snack_2": {"name": "Dark Chocolate", "ingredients": ["Dark chocolate", "Almonds"], "nutrition": {"calories": 140, "protein": 4, "carbs": 12, "fat": 10}}
                    },
                    "day_4": {
                        "breakfast": {"name": "Egg White Omelette", "ingredients": ["Egg whites", "Spinach", "Mushrooms", "Cheese"], "nutrition": {"calories": 280, "protein": 22, "carbs": 6, "fat": 18}},
                        "lunch": {"name": "Quinoa Bowl", "ingredients": ["Quinoa", "Chickpeas", "Vegetables", "Tahini"], "nutrition": {"calories": 420, "protein": 18, "carbs": 55, "fat": 16}},
                        "dinner": {"name": "Cod with Rice", "ingredients": ["Cod fillet", "Brown rice", "Asparagus"], "nutrition": {"calories": 480, "protein": 38, "carbs": 42, "fat": 16}},
                        "snack_1": {"name": "Protein Bar", "ingredients": ["Protein bar"], "nutrition": {"calories": 200, "protein": 20, "carbs": 15, "fat": 8}},
                        "snack_2": {"name": "Orange", "ingredients": ["Orange"], "nutrition": {"calories": 80, "protein": 2, "carbs": 18, "fat": 0}}
                    },
                    "day_5": {
                        "breakfast": {"name": "Smoothie Bowl", "ingredients": ["Frozen berries", "Greek yogurt", "Granola", "Chia seeds"], "nutrition": {"calories": 320, "protein": 18, "carbs": 42, "fat": 10}},
                        "lunch": {"name": "Lentil Soup", "ingredients": ["Lentils", "Vegetables", "Chicken broth"], "nutrition": {"calories": 350, "protein": 20, "carbs": 45, "fat": 8}},
                        "dinner": {"name": "Pork Tenderloin", "ingredients": ["Pork tenderloin", "Mashed potatoes", "Carrots"], "nutrition": {"calories": 540, "protein": 44, "carbs": 38, "fat": 22}},
                        "snack_1": {"name": "Hummus with Carrots", "ingredients": ["Hummus", "Carrots"], "nutrition": {"calories": 150, "protein": 6, "carbs": 18, "fat": 8}},
                        "snack_2": {"name": "Trail Mix", "ingredients": ["Nuts", "Dried fruits", "Seeds"], "nutrition": {"calories": 180, "protein": 5, "carbs": 15, "fat": 12}}
                    },
                    "day_6": {
                        "breakfast": {"name": "Avocado Toast", "ingredients": ["Whole grain bread", "Avocado", "Eggs"], "nutrition": {"calories": 380, "protein": 16, "carbs": 32, "fat": 22}},
                        "lunch": {"name": "Chicken Caesar Salad", "ingredients": ["Chicken breast", "Romaine lettuce", "Parmesan", "Croutons"], "nutrition": {"calories": 420, "protein": 32, "carbs": 15, "fat": 24}},
                        "dinner": {"name": "Shrimp Scampi", "ingredients": ["Shrimp", "Whole wheat pasta", "Garlic", "Olive oil"], "nutrition": {"calories": 480, "protein": 36, "carbs": 45, "fat": 18}},
                        "snack_1": {"name": "Protein Shake", "ingredients": ["Protein powder", "Milk", "Banana"], "nutrition": {"calories": 220, "protein": 28, "carbs": 20, "fat": 4}},
                        "snack_2": {"name": "Grapes", "ingredients": ["Grapes"], "nutrition": {"calories": 90, "protein": 1, "carbs": 22, "fat": 0}}
                    },
                    "day_7": {
                        "breakfast": {"name": "Breakfast Burrito", "ingredients": ["Eggs", "Turkey", "Whole wheat tortilla", "Cheese"], "nutrition": {"calories": 360, "protein": 24, "carbs": 28, "fat": 18}},
                        "lunch": {"name": "Mediterranean Bowl", "ingredients": ["Falafel", "Couscous", "Cucumber", "Tzatziki"], "nutrition": {"calories": 440, "protein": 16, "carbs": 48, "fat": 20}},
                        "dinner": {"name": "Baked Chicken", "ingredients": ["Chicken breast", "Wild rice", "Broccoli"], "nutrition": {"calories": 500, "protein": 42, "carbs": 40, "fat": 18}},
                        "snack_1": {"name": "Yogurt with Berries", "ingredients": ["Greek yogurt", "Mixed berries", "Honey"], "nutrition": {"calories": 160, "protein": 16, "carbs": 18, "fat": 4}},
                        "snack_2": {"name": "Almond Butter Toast", "ingredients": ["Whole grain bread", "Almond butter"], "nutrition": {"calories": 200, "protein": 8, "carbs": 20, "fat": 10}}
                    }
                },
                "nutritional_needs": {
                    "daily_calories": 2000,
                    "daily_protein": 150,
                    "daily_carbs": 250,
                    "daily_fat": 70
                },
                "shopping_list": [
                    "Oatmeal", "Berries", "Honey", "Chicken breast", "Salmon", "Turkey breast", "Lean beef", "Cod", "Pork tenderloin", "Shrimp",
                    "Eggs", "Egg whites", "Greek yogurt", "Cottage cheese", "Milk", "Almond milk", "Cheese", "Parmesan",
                    "Mixed greens", "Spinach", "Romaine lettuce", "Broccoli", "Green beans", "Asparagus", "Carrots", "Cucumber", "Mushrooms",
                    "Sweet potato", "Brown rice", "Wild rice", "Quinoa", "Couscous", "Whole wheat tortilla", "Whole grain bread",
                    "Olive oil", "Avocado", "Almonds", "Walnuts", "Cashews", "Peanut butter", "Almond butter", "Tahini", "Hummus",
                    "Protein powder", "Granola", "Banana", "Apple", "Orange", "Grapes", "Pineapple", "Dark chocolate",
                    "Chia seeds", "Dried fruits", "Seeds", "Croutons", "Tzatziki", "Falafel", "Chickpeas", "Lentils", "Chicken broth"
                ],
                "meal_prep_tips": [
                    "Prepare oatmeal and smoothie ingredients the night before",
                    "Cook chicken and beef in bulk for the week",
                    "Wash and cut all vegetables ahead of time",
                    "Pre-cook quinoa and rice for easy meal assembly",
                    "Make protein shakes and smoothies in advance",
                    "Portion out snacks for the week",
                    "Prepare salad ingredients and store separately"
                ],
                "note": "This is a 7-day sample meal plan. For personalized AI-generated plans, please ensure GEMINI_API_KEY is configured."
            }
            meal_plan = fallback_plan
        else:
            # Generate meal plan using AI
            meal_plan = meal_planner.generate_meal_plan(user_profile)
            
            if 'error' in meal_plan:
                raise HTTPException(status_code=500, detail=meal_plan['error'])
        
        # Extract nutritional needs from the meal plan
        nutritional_needs = meal_plan.get('nutritional_needs', {})
        daily_calories = nutritional_needs.get('daily_calories', 2000)
        daily_protein = nutritional_needs.get('daily_protein', 150)
        daily_carbs = nutritional_needs.get('daily_carbs', 250)
        daily_fat = nutritional_needs.get('daily_fat', 70)
        
        # Save meal plan to database if user is a member
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO nutrition_plans 
                    (member_id, plan_name, daily_calories, daily_protein, daily_carbs, daily_fat, plan_data, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    user['id'],
                    plan_name,
                    daily_calories,
                    daily_protein,
                    daily_carbs,
                    daily_fat,
                    json.dumps(meal_plan)
                ))
                conn.commit()
            except Exception as e:
                print(f"Error saving meal plan: {e}")
            finally:
                cursor.close()
                conn.close()
        
        return meal_plan
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating meal plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/member/nutrition/plans/{plan_id}")
async def delete_member_nutrition_plan(plan_id: int, request: Request):
    """Delete a nutrition plan for the current member"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if user['user_type'] != 'member':
            raise HTTPException(status_code=403, detail="Only members can delete their own plans")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if plan exists and belongs to the current member
            cursor.execute("""
                SELECT id FROM nutrition_plans 
                WHERE id = %s AND member_id = %s
            """, (plan_id, user['id']))
            
            plan = cursor.fetchone()
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found or access denied")
            
            # Delete the plan
            cursor.execute("DELETE FROM nutrition_plans WHERE id = %s", (plan_id,))
            conn.commit()
            
            return {"success": True, "message": "Nutrition plan deleted successfully"}
            
        except Exception as e:
            print(f"Error deleting nutrition plan: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting nutrition plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
@app.put("/api/member/nutrition/meals/{meal_id}")
async def update_member_meal(meal_id: int, request: Request):
    """Update a meal for the current member"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if user['user_type'] != 'member':
            raise HTTPException(status_code=403, detail="Only members can update their own meals")
        
        # Get request data
        data = await request.json()
        
        # Validate required fields
        required_fields = ['food_name', 'meal_type', 'quantity', 'unit', 'calories', 'protein', 'carbs', 'fat']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate unit field - must be one of the allowed ENUM values
        allowed_units = ['grams', 'ml', 'pieces', 'cups', 'tablespoons', 'serving']
        if data['unit'] not in allowed_units:
            raise HTTPException(status_code=400, detail=f"Invalid unit value. Must be one of: {', '.join(allowed_units)}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if meal exists and belongs to the current member
            cursor.execute("""
                SELECT id, meal_type, custom_food_name, total_calories, total_protein, total_carbs, total_fat, quantity, unit, notes, created_at
                FROM nutrition_logs 
                WHERE id = %s AND member_id = %s
            """, (meal_id, user['id']))
            
            meal = cursor.fetchone()
            if not meal:
                raise HTTPException(status_code=404, detail="Meal not found or access denied")
            
            # Update the meal
            update_query = """
                UPDATE nutrition_logs 
                SET custom_food_name = %s, meal_type = %s, quantity = %s, unit = %s, 
                    total_calories = %s, total_protein = %s, total_carbs = %s, total_fat = %s, notes = %s
                WHERE id = %s AND member_id = %s
            """
            
            cursor.execute(update_query, (
                data['food_name'],
                data['meal_type'],
                data['quantity'],
                data['unit'],
                data['calories'],
                data['protein'],
                data['carbs'],
                data['fat'],
                data.get('notes', ''),
                meal_id,
                user['id']
            ))
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Meal not found or access denied")
            
            conn.commit()
            
            return {
                "success": True,
                "message": "Meal updated successfully",
                "updated_meal": {
                    "id": meal_id,
                    "food_name": data['food_name'],
                    "meal_type": data['meal_type'],
                    "quantity": data['quantity'],
                    "unit": data['unit'],
                    "calories": data['calories'],
                    "protein": data['protein'],
                    "carbs": data['carbs'],
                    "fat": data['fat'],
                    "notes": data.get('notes', '')
                }
            }
            
        except Exception as e:
            print(f"Error updating meal: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating meal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/member/nutrition/meals/{meal_id}")
async def delete_member_meal(meal_id: int, request: Request):
    """Delete a meal for the current member"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if user['user_type'] != 'member':
            raise HTTPException(status_code=403, detail="Only members can delete their own meals")
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # Check if meal exists and belongs to the current member
            cursor.execute("""
                SELECT id, meal_type, custom_food_name, total_calories, total_protein, total_carbs, total_fat, quantity, unit, notes, created_at
                FROM nutrition_logs 
                WHERE id = %s AND member_id = %s
            """, (meal_id, user['id']))
            
            meal = cursor.fetchone()
            if not meal:
                raise HTTPException(status_code=404, detail="Meal not found or access denied")
            
            # Delete the meal
            cursor.execute("DELETE FROM nutrition_logs WHERE id = %s", (meal_id,))
            conn.commit()
            
            return {
                "success": True,
                "message": "Meal deleted successfully",
                "deleted_meal": {
                    "id": meal["id"],
                    "meal_type": meal["meal_type"],
                    "food_name": meal["custom_food_name"],
                    "calories": meal["total_calories"],
                    "protein": meal["total_protein"],
                    "carbs": meal["total_carbs"],
                    "fat": meal["total_fat"],
                    "quantity": meal["quantity"],
                    "unit": meal["unit"],
                    "notes": meal["notes"],
                    "created_at": meal["created_at"]
                }
            }
            
        except Exception as e:
            print(f"Error deleting meal: {e}")
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Error deleting meal: {str(e)}")
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting meal: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting meal: {str(e)}")

@app.post("/api/nutrition/generate-custom-meal")
async def generate_custom_meal(request: Request):
    """Generate a custom meal using AI"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Check premium membership for members
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT membership_type FROM members WHERE id = %s", (user['id'],))
            member = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not member or member['membership_type'] not in ['Premium', 'VIP']:
                raise HTTPException(status_code=403, detail="AI meal generation requires Premium or VIP membership")
        
        # Get request data
        data = await request.json()
        meal_requirements = data.get('meal_requirements', {})
        
        if not meal_planner or not meal_planner.is_available():
            # Provide a fallback custom meal when AI is not available
            meal_type = meal_requirements.get('meal_type', 'lunch')
            dietary_restrictions = meal_requirements.get('dietary_restrictions', [])
            calorie_target = meal_requirements.get('calorie_target', 500)
            
            # Generate a fallback meal based on requirements
            fallback_meal = {
                "meal": {
                    "name": f"Healthy {meal_type.title()}",
                    "ingredients": [
                        "Lean protein (chicken, fish, or tofu)",
                        "Whole grains (brown rice, quinoa, or whole wheat pasta)",
                        "Fresh vegetables",
                        "Healthy fats (olive oil, avocado, or nuts)",
                        "Herbs and spices for flavor"
                    ],
                    "nutrition": {
                        "calories": calorie_target,
                        "protein": int(calorie_target * 0.3 / 4),  # 30% protein
                        "carbs": int(calorie_target * 0.45 / 4),   # 45% carbs
                        "fat": int(calorie_target * 0.25 / 9)      # 25% fat
                    },
                    "instructions": [
                        "Choose a lean protein source based on your preferences",
                        "Cook with minimal oil using healthy cooking methods",
                        "Include a variety of colorful vegetables",
                        "Season with herbs and spices instead of salt",
                        "Serve with a small portion of whole grains"
                    ]
                },
                "nutritional_info": {
                    "calories": calorie_target,
                    "protein": f"{int(calorie_target * 0.3 / 4)}g",
                    "carbs": f"{int(calorie_target * 0.45 / 4)}g",
                    "fat": f"{int(calorie_target * 0.25 / 9)}g",
                    "fiber": "8-12g",
                    "sodium": "<500mg"
                },
                "dietary_notes": f"This meal is designed to be {', '.join(dietary_restrictions) if dietary_restrictions else 'flexible'} and can be adapted to various dietary preferences.",
                "note": "This is a sample meal suggestion. For personalized AI-generated meals, please ensure GEMINI_API_KEY is configured."
            }
            return fallback_meal
        else:
            # Generate custom meal using AI
            meal = meal_planner.generate_custom_meal(meal_requirements)
            
            if 'error' in meal:
                raise HTTPException(status_code=500, detail=meal['error'])
            
            return meal
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating custom meal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/nutrition/analyze-photo-ai")
async def analyze_nutrition_photo_ai(
    request: Request,
    file: UploadFile = File(...),
    meal_type: str = Form(...),
    detected_foods: str = Form("[]")
):
    """Enhanced nutrition photo analysis using Hugging Face model + USDA database"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Check premium membership for members
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT membership_type FROM members WHERE id = %s", (user['id'],))
            member = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not member or member['membership_type'] not in ['Premium', 'VIP']:
                raise HTTPException(status_code=403, detail="AI photo analysis requires Premium or VIP membership")
        
        # Read photo data
        photo_data = await file.read()
        
        # Load the food classification model if not already loaded
        if food_model is None:
            load_food_classification_model()
        
        # Analyze photo with enhanced AI + USDA database
        analysis_result = analyze_food_photo_enhanced(photo_data)
        
        if "error" in analysis_result:
            raise HTTPException(status_code=500, detail=analysis_result['error'])
        
        # Save to nutrition logs if analysis is successful
        if analysis_result.get('success'):
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                # Save the photo
                photo_filename = f"nutrition_enhanced_{user['id']}_{int(time.time())}.jpg"
                photo_path = os.path.join("static", "images", photo_filename)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                
                with open(photo_path, "wb") as f:
                    f.write(photo_data)
                
                # Save nutrition data
                nutrition = analysis_result['nutrition']
                cursor.execute("""
                    INSERT INTO nutrition_logs
                    (member_id, meal_type, custom_food_name, quantity, unit, calories, protein, carbs, fat, photo_path, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    user['id'],
                    meal_type,
                    analysis_result['detected_food'],
                    1,
                    "serving",
                    nutrition.get('calories', 0),
                    nutrition.get('protein', 0),
                    nutrition.get('carbs', 0),
                    nutrition.get('fat', 0),
                    photo_filename,
                    f"Enhanced AI Analysis: {analysis_result['detected_food']} (Confidence: {analysis_result['confidence']:.2f}) - Source: {nutrition.get('source', 'Unknown')}"
                ))
                conn.commit()
                
                # Add insights
                analysis_result['insights'] = {
                    'detection_confidence': analysis_result['confidence'],
                    'data_source': nutrition.get('source', 'Unknown'),
                    'analysis_method': analysis_result['analysis_method'],
                    'recommendations': generate_nutrition_recommendations(nutrition)
                }
                
            except Exception as e:
                print(f"Error saving enhanced nutrition analysis: {e}")
            finally:
                cursor.close()
                conn.close()
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing nutrition photo with enhanced AI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

def generate_nutrition_recommendations(nutrition: Dict) -> List[str]:
    """Generate nutrition recommendations based on detected food"""
    recommendations = []
    
    calories = nutrition.get('calories', 0)
    protein = nutrition.get('protein', 0)
    carbs = nutrition.get('carbs', 0)
    fat = nutrition.get('fat', 0)
    
    if calories > 0:
        if calories < 100:
            recommendations.append("This appears to be a low-calorie food. Consider adding protein or healthy fats for better satiety.")
        elif calories > 500:
            recommendations.append("This is a high-calorie food. Consider portion control or balancing with lower-calorie options.")
    
    if protein > 0:
        if protein < 5:
            recommendations.append("Low in protein. Consider adding lean protein sources to your meal.")
        elif protein > 20:
            recommendations.append("Good protein content! This will help with muscle maintenance and satiety.")
    
    if carbs > 0:
        if carbs > 50:
            recommendations.append("High in carbohydrates. Consider pairing with protein and fiber for better blood sugar control.")
    
    if fat > 0:
        if fat > 15:
            recommendations.append("High in fat. Consider portion control or choosing lower-fat alternatives.")
    
    if not recommendations:
        recommendations.append("Keep tracking your meals for personalized nutrition insights!")
    
    return recommendations

@app.post("/api/nutrition/get-insights")
async def get_nutrition_insights(request: Request):
    """Get AI nutrition insights"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Check premium membership for members
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT membership_type FROM members WHERE id = %s", (user['id'],))
            member = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not member or member['membership_type'] not in ['Premium', 'VIP']:
                raise HTTPException(status_code=403, detail="AI insights require Premium or VIP membership")
        
        # Get request data
        data = await request.json()
        nutrition_data = data.get('nutrition_data', {})
        
        if not meal_planner:
            raise HTTPException(status_code=503, detail="AI meal planner not available")
        
        # Get insights
        insights = meal_planner.get_nutrition_insights(nutrition_data)
        
        if 'error' in insights:
            raise HTTPException(status_code=500, detail=insights['error'])
        
        return insights
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting nutrition insights: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/nutrition/calculate-needs")
async def calculate_nutritional_needs(
    request: Request,
    age: int = Query(...),
    gender: str = Query(...),
    weight: float = Query(...),
    height: float = Query(...),
    activity_level: str = Query(...),
    goal: str = Query(...)
):
    """Calculate nutritional needs using AI"""
    try:
        # Get user from session
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if not meal_planner:
            raise HTTPException(status_code=503, detail="AI meal planner not available")
        
        # Calculate nutritional needs
        needs = meal_planner.calculate_nutritional_needs(
            age=age,
            gender=gender,
            weight=weight,
            height=height,
            activity_level=activity_level,
            goal=goal
        )
        
        return needs
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating nutritional needs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Additional CRUD endpoints for Members
@app.put("/api/gym/members/{member_id}")
async def update_gym_member(member_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get member data from request
        data = await request.json()
        
        # Validate required fields (password and coach_id are optional for updates)
        required_fields = ["name", "email", "membership_type"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate password if provided
        if "password" in data and len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Validate email format
        if not "@" in data["email"] or not "." in data["email"]:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # Validate membership type
        valid_membership_types = ["Basic", "Premium", "VIP"]
        if data["membership_type"] not in valid_membership_types:
            raise HTTPException(status_code=400, detail=f"Invalid membership type. Must be one of: {', '.join(valid_membership_types)}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if member exists and belongs to this gym
            cursor.execute("SELECT id FROM members WHERE id = %s AND gym_id = %s", (member_id, user["id"]))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Member not found")
            
            # Check if email already exists for other members
            cursor.execute("SELECT id FROM members WHERE email = %s AND id != %s", (data["email"], member_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Update member (with optional password)
            if "password" in data:
                cursor.execute("""
                    UPDATE members 
                    SET name = %s, email = %s, membership_type = %s, password = %s
                    WHERE id = %s AND gym_id = %s
                """, (
                    data["name"],
                    data["email"],
                    data["membership_type"],
                    data["password"],
                    member_id,
                    user["id"]
                ))
            else:
                cursor.execute("""
                    UPDATE members 
                    SET name = %s, email = %s, membership_type = %s
                    WHERE id = %s AND gym_id = %s
                """, (
                    data["name"],
                    data["email"],
                    data["membership_type"],
                    member_id,
                    user["id"]
                ))
            
            # Handle coach assignment update
            if "coach_id" in data:
                # First, remove any existing coach assignment
                cursor.execute("DELETE FROM member_coach WHERE member_id = %s", (member_id,))
                
                # If a new coach is assigned, add the relationship
                if data["coach_id"]:
                    cursor.execute("""
                        INSERT INTO member_coach (member_id, coach_id, assigned_date)
                        VALUES (%s, %s, CURDATE())
                    """, (member_id, data["coach_id"]))
            
            conn.commit()
            
            return {"message": "Member updated successfully"}
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error updating member: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/gym/members/{member_id}")
async def delete_gym_member(member_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if member exists and belongs to this gym
        cursor.execute("SELECT id FROM members WHERE id = %s AND gym_id = %s", (member_id, user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Delete related records first
        cursor.execute("DELETE FROM member_coach WHERE member_id = %s", (member_id,))
        cursor.execute("DELETE FROM sessions WHERE member_id = %s", (member_id,))
        cursor.execute("DELETE FROM payments WHERE member_id = %s", (member_id,))
        
        # Delete member
        cursor.execute("DELETE FROM members WHERE id = %s AND gym_id = %s", (member_id, user["id"]))
        
        conn.commit()
        
        return {"message": "Member deleted successfully"}
        
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        print(f"Error deleting member: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# CRUD endpoints for Coaches
@app.post("/api/gym/coaches")
async def add_gym_coach(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get coach data from request
        data = await request.json()
        
        # Validate required fields
        required_fields = ["name", "email", "password", "specialization"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate password length
        if len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Validate email format
        if not "@" in data["email"] or not "." in data["email"]:
            raise HTTPException(status_code=400, detail="Invalid email format")
        

        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT id FROM coaches WHERE email = %s", (data["email"],))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Insert new coach
            cursor.execute("""
                INSERT INTO coaches (name, email, specialization, gym_id, password, status)
                VALUES (%s, %s, %s, %s, %s, 'Active')
            """, (
                data["name"],
                data["email"],
                data["specialization"],
                user["id"],
                data["password"]
            ))
            
            coach_id = cursor.lastrowid
            conn.commit()
            
            return {
                "message": "Coach added successfully",
                "coach_id": coach_id
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error adding coach: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/gym/coaches/{coach_id}")
async def update_gym_coach(coach_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get coach data from request
        data = await request.json()
        
        # Validate required fields (password is optional for updates)
        required_fields = ["name", "email", "specialization", "status"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate password if provided
        if "password" in data and len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Validate email format
        if not "@" in data["email"] or not "." in data["email"]:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # Validate status
        valid_statuses = ["Active", "Inactive"]
        if data["status"] not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if coach exists and belongs to this gym
            cursor.execute("SELECT id FROM coaches WHERE id = %s AND gym_id = %s", (coach_id, user["id"]))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Coach not found")
            
            # Check if email already exists for other coaches
            cursor.execute("SELECT id FROM coaches WHERE email = %s AND id != %s", (data["email"], coach_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Update coach (with optional password)
            if "password" in data:
                cursor.execute("""
                    UPDATE coaches 
                    SET name = %s, email = %s, specialization = %s, status = %s, password = %s
                    WHERE id = %s AND gym_id = %s
                """, (
                    data["name"],
                    data["email"],
                    data["specialization"],
                    data["status"],
                    data["password"],
                    coach_id,
                    user["id"]
                ))
            else:
                cursor.execute("""
                    UPDATE coaches 
                    SET name = %s, email = %s, specialization = %s, status = %s
                    WHERE id = %s AND gym_id = %s
                """, (
                    data["name"],
                    data["email"],
                    data["specialization"],
                    data["status"],
                    coach_id,
                    user["id"]
                ))
            
            conn.commit()
            
            return {"message": "Coach updated successfully"}
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error updating coach: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/gym/coaches/{coach_id}")
async def delete_gym_coach(coach_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if coach exists and belongs to this gym
        cursor.execute("SELECT id FROM coaches WHERE id = %s AND gym_id = %s", (coach_id, user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Coach not found")
        
        # Delete related records first
        cursor.execute("DELETE FROM member_coach WHERE coach_id = %s", (coach_id,))
        cursor.execute("DELETE FROM sessions WHERE coach_id = %s", (coach_id,))
        
        # Delete coach
        cursor.execute("DELETE FROM coaches WHERE id = %s AND gym_id = %s", (coach_id, user["id"]))
        
        conn.commit()
        
        return {"message": "Coach deleted successfully"}
        
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        print(f"Error deleting coach: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Excel Export Endpoints

@app.get("/api/export/schedule/coach")
async def export_coach_schedule(
    format: str = "xlsx",
    start_date: str = None,
    end_date: str = None,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export coach schedule data to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = current_user.get('id')
        
        # Build query with filters
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        WHERE s.coach_id = %s
        """
        params = [coach_id]
        
        if start_date and end_date:
            query += " AND s.session_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += " ORDER BY s.session_date, s.session_time"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration', 'notes'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Coach Schedule', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_schedule_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/schedule/member")
async def export_member_schedule(
    format: str = "xlsx",
    start_date: str = None,
    end_date: str = None,
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export member schedule data to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get member ID from current user
        member_id = current_user.get('id')  # Changed from 'user_id' to 'id'
        
        # Build query with filters
        query = """
        SELECT 
            c.name as coach_name,
            c.email as coach_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes
        FROM sessions s
        JOIN coaches c ON s.coach_id = c.id
        WHERE s.member_id = %s
        """
        params = [member_id]
        
        if start_date and end_date:
            query += " AND s.session_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += " ORDER BY s.session_date, s.session_time"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        if not sessions:
            raise HTTPException(status_code=404, detail="No sessions found")
        
        # Convert to DataFrame
        df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='My Schedule', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"member_schedule_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/sessions/coach")
async def export_coach_sessions(
    format: str = "xlsx",
    dateRange: str = "all",
    status: str = "all",
    member: str = "all",
    search: str = "",
    searchType: str = "all",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export coach sessions data to Excel with filters"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = current_user.get('id')
        
        # Base query
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes,
            s.created_at
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        WHERE s.coach_id = %s
        """
        params = [coach_id]
        
        # Add date range filter
        if dateRange != "all":
            if dateRange == "today":
                query += " AND s.session_date = CURDATE()"
            elif dateRange == "week":
                query += " AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
            elif dateRange == "month":
                query += " AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        
        # Add status filter
        if status != "all":
            query += " AND s.status = %s"
            params.append(status)
        
        # Add member filter
        if member != "all":
            query += " AND s.member_id = %s"
            params.append(member)
        
        # Add search condition
        if search:
            query += " AND (m.name LIKE %s OR m.email LIKE %s OR s.notes LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
        # Add order by
        query += " ORDER BY s.session_date DESC, s.session_time DESC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Convert to DataFrame
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration', 'notes', 'created_at'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Coach Sessions', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_sessions_filtered_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/sessions/gym")
async def export_gym_sessions(
    request: Request,
    format: str = "xlsx"
):
    """Export gym sessions data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            c.name as coach_name,
            c.email as coach_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes,
            s.created_at
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        JOIN coaches c ON s.coach_id = c.id
        WHERE s.gym_id = %s
        ORDER BY s.session_date DESC, s.session_time DESC
        """
        
        cursor.execute(query, [user["id"]])
        sessions = cursor.fetchall()
        
        # Convert to DataFrame
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'coach_name', 'coach_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration', 'notes', 'created_at'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Gym Sessions', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"gym_sessions_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/members/coach")
async def export_coach_members(
    request: Request,
    format: str = "xlsx"
):
    """Export coach members data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = user.get('id')
        
        query = """
        SELECT 
            m.name,
            m.email,
            m.membership_type,
            m.created_at,
            COUNT(s.id) as total_sessions,
            COUNT(CASE WHEN s.status = 'Completed' THEN 1 END) as completed_sessions,
            MAX(s.session_date) as last_session_date
        FROM members m
        JOIN member_coach mc ON m.id = mc.member_id
        LEFT JOIN sessions s ON m.id = s.member_id AND s.coach_id = %s
        WHERE mc.coach_id = %s
        GROUP BY m.id, m.name, m.email, m.membership_type, m.created_at
        ORDER BY m.name
        """
        
        cursor.execute(query, [coach_id, coach_id])
        members = cursor.fetchall()
        
        # Convert to DataFrame
        if not members:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['name', 'email', 'membership_type', 'created_at', 'total_sessions', 'completed_sessions', 'last_session_date'])
        else:
            df = pd.DataFrame(members)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Coach Members', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_members_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/members/gym")
async def export_gym_members(
    request: Request,
    format: str = "xlsx"
):
    """Export gym members data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT 
            m.name,
            m.email,
            m.membership_type,
            m.created_at,
            c.name as coach_name,
            c.email as coach_email,
            COUNT(s.id) as total_sessions,
            COUNT(CASE WHEN s.status = 'Completed' THEN 1 END) as completed_sessions,
            MAX(s.session_date) as last_session_date
        FROM members m
        LEFT JOIN member_coach mc ON m.id = mc.member_id
        LEFT JOIN coaches c ON mc.coach_id = c.id
        LEFT JOIN sessions s ON m.id = s.member_id
        WHERE m.gym_id = %s
        GROUP BY m.id, m.name, m.email, m.membership_type, m.created_at, c.name, c.email
        ORDER BY m.name
        """
        
        cursor.execute(query, [user["id"]])
        members = cursor.fetchall()
        
        # Convert to DataFrame
        if not members:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['name', 'email', 'membership_type', 'created_at', 'coach_name', 'coach_email', 'total_sessions', 'completed_sessions', 'last_session_date'])
        else:
            df = pd.DataFrame(members)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Gym Members', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"gym_members_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/coaches/gym")
async def export_gym_coaches(
    request: Request,
    format: str = "xlsx"
):
    """Export gym coaches data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        query = """
        SELECT 
            c.name,
            c.email,
            c.specialization,
            c.status,
            c.created_at,
            COUNT(DISTINCT m.id) as assigned_members,
            COUNT(s.id) as total_sessions,
            COUNT(CASE WHEN s.status = 'Completed' THEN 1 END) as completed_sessions
        FROM coaches c
        LEFT JOIN member_coach mc ON c.id = mc.coach_id
        LEFT JOIN members m ON mc.member_id = m.id
        LEFT JOIN sessions s ON c.id = s.coach_id
        WHERE c.gym_id = %s
        GROUP BY c.id, c.name, c.email, c.specialization, c.status, c.created_at
        ORDER BY c.name
        """
        
        cursor.execute(query, [user["id"]])
        coaches = cursor.fetchall()
        
        # Convert to DataFrame
        if not coaches:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['name', 'email', 'specialization', 'status', 'created_at', 'assigned_members', 'total_sessions', 'completed_sessions'])
        else:
            df = pd.DataFrame(coaches)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Gym Coaches', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"gym_coaches_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/progress/coach")
async def export_coach_progress(
    format: str = "xlsx",
    time_range: str = "month",
    member_id: str = "0",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export coach progress data to Excel with member filtering"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = current_user.get('id')
        
        # Calculate date range
        end_date = datetime.now()
        if time_range == "week":
            start_date = end_date - timedelta(days=7)
        elif time_range == "month":
            start_date = end_date - timedelta(days=30)
        elif time_range == "quarter":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=365)
        
        # Base query
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        WHERE s.coach_id = %s AND s.session_date >= %s
        """
        params = [coach_id, start_date.strftime('%Y-%m-%d')]
        
        # Add member filter if specific member is selected
        if member_id != "0":
            query += " AND s.member_id = %s"
            params.append(member_id)
        
        query += " ORDER BY s.session_date DESC, s.session_time DESC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration', 'notes'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Coach Progress', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_progress_filtered_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/progress/member")
async def export_member_progress(
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export member progress data to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get member ID from current user
        member_id = current_user.get('id')  # Changed from 'user_id' to 'id'
        
        query = """
        SELECT 
            c.name as coach_name,
            c.email as coach_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration,
            s.notes
        FROM sessions s
        JOIN coaches c ON s.coach_id = c.id
        WHERE s.member_id = %s
        ORDER BY s.session_date DESC, s.session_time DESC
        """
        
        cursor.execute(query, [member_id])
        sessions = cursor.fetchall()
        
        if not sessions:
            raise HTTPException(status_code=404, detail="No progress data found")
        
        # Convert to DataFrame
        df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='My Progress', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"member_progress_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/nutrition/coach")
async def export_coach_nutrition(
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export coach nutrition data to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = current_user.get('id')
        
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            nl.created_at as entry_date,
            nl.meal_type,
            COALESCE(nl.custom_food_name, fi.name) as food_name,
            nl.quantity,
            nl.unit,
            nl.total_calories as calories,
            nl.total_protein as protein,
            nl.total_carbs as carbs,
            nl.total_fat as fat,
            nl.notes
        FROM nutrition_logs nl
        JOIN members m ON nl.member_id = m.id
        JOIN member_coach mc ON m.id = mc.member_id
        LEFT JOIN food_items fi ON nl.food_item_id = fi.id
        WHERE mc.coach_id = %s
        ORDER BY nl.created_at DESC, nl.meal_type
        """
        
        cursor.execute(query, [coach_id])
        entries = cursor.fetchall()
        
        if not entries:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'entry_date', 'meal_type', 'food_name', 'quantity', 'unit', 'calories', 'protein', 'carbs', 'fat', 'notes'])
        else:
            df = pd.DataFrame(entries)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Coach Nutrition', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_nutrition_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/nutrition/member")
async def export_member_nutrition(
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export member nutrition data to Excel"""
    try:
        print(f"Export member nutrition called with current_user: {current_user}")  # Debug log
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get member ID from current user
        member_id = current_user.get('id')  # Changed from 'user_id' to 'id'
        print(f"Member ID: {member_id}")  # Debug log
        
        query = """
        SELECT 
            nl.created_at as entry_date,
            nl.meal_type,
            COALESCE(nl.custom_food_name, fi.name) as food_name,
            nl.quantity,
            nl.unit,
            nl.total_calories as calories,
            nl.total_protein as protein,
            nl.total_carbs as carbs,
            nl.total_fat as fat,
            nl.notes
        FROM nutrition_logs nl
        LEFT JOIN food_items fi ON nl.food_item_id = fi.id
        WHERE nl.member_id = %s
        ORDER BY nl.created_at DESC, nl.meal_type
        """
        
        print(f"Executing query with member_id: {member_id}")  # Debug log
        cursor.execute(query, [member_id])
        entries = cursor.fetchall()
        print(f"Found {len(entries)} nutrition entries")  # Debug log
        
        if not entries:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['entry_date', 'meal_type', 'food_name', 'quantity', 'unit', 'calories', 'protein', 'carbs', 'fat', 'notes'])
            print("Created empty DataFrame")  # Debug log
        else:
            df = pd.DataFrame(entries)
            print(f"Created DataFrame with {len(df)} rows")  # Debug log
        
        # Create Excel file in memory
        print("Creating Excel file...")  # Debug log
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='My Nutrition', index=False)
            print("Excel file created successfully")  # Debug log
        except Exception as e:
            print(f"Error creating Excel file: {str(e)}")  # Debug log
            raise
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"member_nutrition_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        print(f"Export failed with error: {str(e)}")  # Debug log
        print(f"Error type: {type(e)}")  # Debug log
        import traceback
        print(f"Traceback: {traceback.format_exc()}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/dashboard/coach")
async def export_coach_dashboard(
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export coach dashboard data to Excel"""
    try:
        print(f"Export dashboard called with current_user: {current_user}")  # Debug log
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach ID from current user
        coach_id = current_user.get('id')  # Changed from 'user_id' to 'id'
        print(f"Coach ID: {coach_id}")  # Debug log
        
        # Get recent sessions
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        WHERE s.coach_id = %s
        ORDER BY s.session_date DESC, s.session_time DESC
        LIMIT 50
        """
        
        print(f"Executing query with coach_id: {coach_id}")  # Debug log
        cursor.execute(query, [coach_id])
        sessions = cursor.fetchall()
        print(f"Found {len(sessions)} sessions")  # Debug log
        
        # Convert to DataFrame
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration'])
            print("Created empty DataFrame")  # Debug log
        else:
            df = pd.DataFrame(sessions)
            print(f"Created DataFrame with {len(df)} rows")  # Debug log
        
        # Create Excel file in memory
        print("Creating Excel file...")  # Debug log
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Coach Dashboard', index=False)
            print("Excel file created successfully")  # Debug log
        except Exception as e:
            print(f"Error creating Excel file: {str(e)}")  # Debug log
            raise
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"coach_dashboard_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        print(f"Export failed with error: {str(e)}")  # Debug log
        print(f"Error type: {type(e)}")  # Debug log
        import traceback
        print(f"Traceback: {traceback.format_exc()}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/dashboard/member")
async def export_member_dashboard(
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user_dependency)
):
    """Export member dashboard data to Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get member ID from current user
        member_id = current_user.get('id')  # Changed from 'user_id' to 'id'
        
        # Get recent sessions
        query = """
        SELECT 
            c.name as coach_name,
            c.email as coach_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration
        FROM sessions s
        JOIN coaches c ON s.coach_id = c.id
        WHERE s.member_id = %s
        ORDER BY s.session_date DESC, s.session_time DESC
        LIMIT 50
        """
        
        cursor.execute(query, [member_id])
        sessions = cursor.fetchall()
        
        # Convert to DataFrame
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['coach_name', 'coach_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='My Dashboard', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"member_dashboard_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/dashboard/gym")
async def export_gym_dashboard(
    request: Request,
    format: str = "xlsx"
):
    """Export gym dashboard data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get recent sessions
        query = """
        SELECT 
            m.name as member_name,
            m.email as member_email,
            c.name as coach_name,
            c.email as coach_email,
            s.session_date,
            s.session_time,
            s.notes as workout_type,
            s.status,
            s.duration
        FROM sessions s
        JOIN members m ON s.member_id = m.id
        JOIN coaches c ON s.coach_id = c.id
        WHERE s.gym_id = %s
        ORDER BY s.session_date DESC, s.session_time DESC
        LIMIT 50
        """
        
        cursor.execute(query, [user["id"]])
        sessions = cursor.fetchall()
        
        # Convert to DataFrame
        if not sessions:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['member_name', 'member_email', 'coach_name', 'coach_email', 'session_date', 'session_time', 'workout_type', 'status', 'duration'])
        else:
            df = pd.DataFrame(sessions)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Gym Dashboard', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"gym_dashboard_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/export/analytics/gym")
async def export_gym_analytics(
    request: Request,
    format: str = "xlsx"
):
    """Export gym analytics data to Excel"""
    # Get user from session
    user = get_current_user(request)
    if not user or user["user_type"] != "gym":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get coach performance data
        query = """
        SELECT 
            c.name as coach_name,
            c.email as coach_email,
            c.specialization,
            COUNT(s.id) as total_sessions,
            COUNT(CASE WHEN s.status = 'completed' THEN 1 END) as completed_sessions,
            COUNT(DISTINCT s.member_id) as unique_members,
            ROUND(COUNT(CASE WHEN s.status = 'completed' THEN 1 END) * 100.0 / COUNT(s.id), 2) as completion_rate
        FROM coaches c
        LEFT JOIN sessions s ON c.id = s.coach_id
        WHERE c.gym_id = %s
        GROUP BY c.id, c.name, c.email, c.specialization
        ORDER BY total_sessions DESC
        """
        
        cursor.execute(query, [user["id"]])
        analytics = cursor.fetchall()
        
        # Convert to DataFrame
        if not analytics:
            # Create empty DataFrame with the same columns
            df = pd.DataFrame(columns=['coach_name', 'coach_email', 'specialization', 'total_sessions', 'completed_sessions', 'unique_members', 'completion_rate'])
        else:
            df = pd.DataFrame(analytics)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Gym Analytics', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=\"gym_analytics_{datetime.now().strftime('%Y%m%d')}.xlsx\""}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/test-export")
async def test_export():
    """Test export functionality without authentication"""
    try:
        print("Test export called")  # Debug log
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Create a simple test DataFrame
        test_data = [
            {"name": "Test Member", "email": "test@example.com", "session_date": "2024-01-01", "session_time": "10:00", "workout_type": "Strength", "status": "completed", "duration": 60}
        ]
        
        df = pd.DataFrame(test_data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Test Export', index=False)
        
        output.seek(0)
        
        # Return Excel file
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=test_export_{datetime.now().strftime('%Y%m%d')}.xlsx"}
        )
        
    except Exception as e:
        print(f"Test export error: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Test export failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/test-nutrition-tables")
async def test_nutrition_tables():
    """Test nutrition tables existence and structure"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Check if nutrition_plans table exists
        cursor.execute("SHOW TABLES LIKE 'nutrition_plans'")
        nutrition_plans_exists = cursor.fetchone()
        
        # Check if member_coach table exists
        cursor.execute("SHOW TABLES LIKE 'member_coach'")
        member_coach_exists = cursor.fetchone()
        
        # Check if members table exists
        cursor.execute("SHOW TABLES LIKE 'members'")
        members_exists = cursor.fetchone()
        
        # Get table structure if they exist
        nutrition_plans_structure = None
        if nutrition_plans_exists:
            cursor.execute("DESCRIBE nutrition_plans")
            nutrition_plans_structure = cursor.fetchall()
        
        member_coach_structure = None
        if member_coach_exists:
            cursor.execute("DESCRIBE member_coach")
            member_coach_structure = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "tables": {
                "nutrition_plans": {
                    "exists": bool(nutrition_plans_exists),
                    "structure": nutrition_plans_structure
                },
                "member_coach": {
                    "exists": bool(member_coach_exists),
                    "structure": member_coach_structure
                },
                "members": {
                    "exists": bool(members_exists)
                }
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/debug/members")
async def debug_members():
    """Debug endpoint to see all members and their coaches"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get all members with their coaches
        query = """
            SELECT 
                m.id as member_id,
                m.first_name,
                m.last_name,
                m.email as member_email,
                c.id as coach_id,
                c.name as coach_name,
                c.email as coach_email
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            ORDER BY m.id
        """
        
        cursor.execute(query)
        members = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "members": members,
            "total_members": len(members)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/debug/nutrition-table")
async def debug_nutrition_table():
    """Debug endpoint to check nutrition_logs table structure"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get table structure
        cursor.execute("DESCRIBE nutrition_logs")
        structure = cursor.fetchall()
        
        # Get sample data
        cursor.execute("SELECT * FROM nutrition_logs LIMIT 3")
        sample_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "table_structure": structure,
            "sample_data": sample_data
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 