import os
import json
import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
import requests
from datetime import datetime, timedelta
import re

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class AIMealPlanner:
    def __init__(self):
        self.model = None
        if GEMINI_API_KEY:
            try:
                # Try different model names
                model_names = ['gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
                for model_name in model_names:
                    try:
                        self.model = genai.GenerativeModel(model_name)
                        print(f"Successfully initialized Gemini model: {model_name}")
                        break
                    except Exception as e:
                        print(f"Failed to initialize {model_name}: {e}")
                        continue
                else:
                    print("Could not initialize any Gemini model")
                    self.model = None
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
                self.model = None
        
        # Nutrition calculation constants
        self.MACRO_RATIOS = {
            'weight_loss': {'protein': 0.3, 'carbs': 0.4, 'fat': 0.3},
            'muscle_gain': {'protein': 0.35, 'carbs': 0.45, 'fat': 0.2},
            'maintenance': {'protein': 0.25, 'carbs': 0.5, 'fat': 0.25}
        }
        
        # Load meal planning prompts
        self.meal_plan_prompt = self._load_meal_plan_prompt()
        self.custom_meal_prompt = self._load_custom_meal_prompt()
    
    def is_available(self) -> bool:
        """Check if the AI meal planner is available and ready to use"""
        return self.model is not None and GEMINI_API_KEY is not None
    
    def _load_meal_plan_prompt(self) -> str:
        """Load the meal planning prompt template"""
        return """You are a professional nutritionist and meal planner. Create a personalized meal plan based on the following information:

User Profile:
- Age: {age}
- Gender: {gender}
- Weight: {weight} kg
- Height: {height} cm
- Activity Level: {activity_level}
- Goal: {goal}
- Dietary Restrictions: {dietary_restrictions}
- Allergies: {allergies}
- Preferences: {preferences}

Nutritional Requirements:
- Daily Calories: {daily_calories} kcal
- Daily Protein: {daily_protein}g
- Daily Carbs: {daily_carbs}g
- Daily Fat: {daily_fat}g

Create a detailed 7-day meal plan that includes:
1. Breakfast, Lunch, Dinner, and 2 snacks per day
2. Exact portion sizes and ingredients
3. Nutritional breakdown per meal
4. Shopping list for the week
5. Meal prep tips
6. Substitution options for dietary restrictions

Format the response as a JSON object with the following structure:
{{
    "meal_plan": {{
        "day_1": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_2": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_3": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_4": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_5": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_6": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }},
        "day_7": {{
            "breakfast": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "lunch": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "dinner": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_1": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}},
            "snack_2": {{"name": "", "ingredients": [], "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}}}
        }}
    }},
    "shopping_list": [],
    "meal_prep_tips": [],
    "substitutions": {{}}
}}"""
    
    def _load_custom_meal_prompt(self) -> str:
        """Load the custom meal prompt template"""
        return """You are a professional nutritionist. Create a custom meal based on the following requirements:

User Requirements:
- Meal Type: {meal_type}
- Available Ingredients: {available_ingredients}
- Dietary Restrictions: {dietary_restrictions}
- Allergies: {allergies}
- Target Calories: {target_calories} kcal
- Target Protein: {target_protein}g
- Target Carbs: {target_carbs}g
- Target Fat: {target_fat}g

Create a detailed meal that includes:
1. Recipe name and description
2. Complete ingredient list with exact measurements
3. Step-by-step cooking instructions
4. Nutritional breakdown
5. Cooking time and difficulty level
6. Substitution options

Format the response as a JSON object:
{{
    "meal": {{
        "name": "",
        "description": "",
        "ingredients": [],
        "instructions": [],
        "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}},
        "cooking_time": "",
        "difficulty": "",
        "substitutions": []
    }}
}}"""
    
    def calculate_nutritional_needs(self, age: int, gender: str, weight: float, height: float, 
                                  activity_level: str, goal: str) -> Dict[str, float]:
        """Calculate daily nutritional requirements using the Mifflin-St Jeor equation"""
        
        # Calculate BMR using Mifflin-St Jeor equation
        if gender.lower() == 'male':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Apply activity multiplier
        activity_multipliers = {
            'sedentary': 1.2,
            'lightly_active': 1.375,
            'moderately_active': 1.55,
            'very_active': 1.725,
            'extremely_active': 1.9
        }
        
        tdee = bmr * activity_multipliers.get(activity_level.lower(), 1.2)
        
        # Apply goal adjustments
        goal_adjustments = {
            'weight_loss': 0.85,  # 15% deficit
            'muscle_gain': 1.1,   # 10% surplus
            'maintenance': 1.0
        }
        
        daily_calories = tdee * goal_adjustments.get(goal.lower(), 1.0)
        
        # Calculate macronutrients based on goal
        macro_ratios = self.MACRO_RATIOS.get(goal.lower(), self.MACRO_RATIOS['maintenance'])
        
        daily_protein = (daily_calories * macro_ratios['protein']) / 4  # 4 calories per gram
        daily_carbs = (daily_calories * macro_ratios['carbs']) / 4      # 4 calories per gram
        daily_fat = (daily_calories * macro_ratios['fat']) / 9           # 9 calories per gram
        
        return {
            'daily_calories': round(daily_calories),
            'daily_protein': round(daily_protein),
            'daily_carbs': round(daily_carbs),
            'daily_fat': round(daily_fat),
            'bmr': round(bmr),
            'tdee': round(tdee)
        }
    
    def generate_meal_plan(self, user_profile: Dict) -> Dict:
        """Generate a personalized 7-day meal plan using AI"""
        
        if not self.model:
            # Return a sample meal plan for testing when AI is not available
            nutrition_needs = self.calculate_nutritional_needs(
                age=user_profile.get('age', 30),
                gender=user_profile.get('gender', 'male'),
                weight=user_profile.get('weight', 70),
                height=user_profile.get('height', 170),
                activity_level=user_profile.get('activity_level', 'moderately_active'),
                goal=user_profile.get('goal', 'maintenance')
            )
            
            return {
                "nutritional_needs": nutrition_needs,
                "meal_plan": {
                    "day_1": {
                        "breakfast": {
                            "name": "Oatmeal with Berries and Nuts",
                            "ingredients": ["oats", "berries", "honey", "almonds"],
                            "nutrition": {"calories": 350, "protein": 12, "carbs": 55, "fat": 8}
                        },
                        "lunch": {
                            "name": "Grilled Chicken Salad",
                            "ingredients": ["chicken breast", "mixed greens", "cherry tomatoes", "olive oil"],
                            "nutrition": {"calories": 420, "protein": 38, "carbs": 18, "fat": 22}
                        },
                        "dinner": {
                            "name": "Salmon with Roasted Vegetables",
                            "ingredients": ["salmon fillet", "broccoli", "carrots", "quinoa"],
                            "nutrition": {"calories": 480, "protein": 42, "carbs": 38, "fat": 28}
                        },
                        "snack_1": {
                            "name": "Greek Yogurt with Honey",
                            "ingredients": ["greek yogurt", "honey", "cinnamon"],
                            "nutrition": {"calories": 180, "protein": 15, "carbs": 20, "fat": 5}
                        },
                        "snack_2": {
                            "name": "Apple with Almond Butter",
                            "ingredients": ["apple", "almond butter"],
                            "nutrition": {"calories": 200, "protein": 6, "carbs": 25, "fat": 12}
                        }
                    },
                    "day_2": {
                        "breakfast": {
                            "name": "Protein Smoothie Bowl",
                            "ingredients": ["protein powder", "banana", "spinach", "almond milk"],
                            "nutrition": {"calories": 320, "protein": 25, "carbs": 35, "fat": 8}
                        },
                        "lunch": {
                            "name": "Turkey and Avocado Wrap",
                            "ingredients": ["turkey breast", "avocado", "whole wheat tortilla", "lettuce"],
                            "nutrition": {"calories": 450, "protein": 32, "carbs": 42, "fat": 18}
                        },
                        "dinner": {
                            "name": "Lean Beef Stir-Fry",
                            "ingredients": ["lean beef", "broccoli", "bell peppers", "brown rice"],
                            "nutrition": {"calories": 520, "protein": 45, "carbs": 45, "fat": 22}
                        },
                        "snack_1": {
                            "name": "Mixed Nuts and Dried Fruits",
                            "ingredients": ["almonds", "walnuts", "raisins", "cranberries"],
                            "nutrition": {"calories": 220, "protein": 8, "carbs": 18, "fat": 16}
                        },
                        "snack_2": {
                            "name": "Cottage Cheese with Berries",
                            "ingredients": ["cottage cheese", "strawberries", "blueberries"],
                            "nutrition": {"calories": 160, "protein": 18, "carbs": 12, "fat": 4}
                        }
                    },
                    "day_3": {
                        "breakfast": {
                            "name": "Eggs Benedict with Spinach",
                            "ingredients": ["eggs", "spinach", "whole grain toast", "hollandaise"],
                            "nutrition": {"calories": 380, "protein": 22, "carbs": 28, "fat": 24}
                        },
                        "lunch": {
                            "name": "Quinoa Buddha Bowl",
                            "ingredients": ["quinoa", "chickpeas", "kale", "sweet potato", "tahini"],
                            "nutrition": {"calories": 480, "protein": 18, "carbs": 65, "fat": 16}
                        },
                        "dinner": {
                            "name": "Grilled Shrimp with Zucchini Noodles",
                            "ingredients": ["shrimp", "zucchini", "garlic", "olive oil", "lemon"],
                            "nutrition": {"calories": 360, "protein": 38, "carbs": 12, "fat": 18}
                        },
                        "snack_1": {
                            "name": "Hummus with Carrot Sticks",
                            "ingredients": ["hummus", "carrots", "celery"],
                            "nutrition": {"calories": 180, "protein": 8, "carbs": 22, "fat": 8}
                        },
                        "snack_2": {
                            "name": "Dark Chocolate and Almonds",
                            "ingredients": ["dark chocolate", "almonds"],
                            "nutrition": {"calories": 240, "protein": 6, "carbs": 18, "fat": 18}
                        }
                    },
                    "day_4": {
                        "breakfast": {
                            "name": "Protein Pancakes with Maple Syrup",
                            "ingredients": ["protein powder", "oats", "eggs", "maple syrup", "berries"],
                            "nutrition": {"calories": 420, "protein": 28, "carbs": 45, "fat": 12}
                        },
                        "lunch": {
                            "name": "Mediterranean Salad with Tuna",
                            "ingredients": ["tuna", "olives", "cucumber", "tomatoes", "feta cheese"],
                            "nutrition": {"calories": 380, "protein": 35, "carbs": 15, "fat": 20}
                        },
                        "dinner": {
                            "name": "Baked Chicken with Sweet Potato",
                            "ingredients": ["chicken breast", "sweet potato", "green beans", "herbs"],
                            "nutrition": {"calories": 460, "protein": 42, "carbs": 38, "fat": 16}
                        },
                        "snack_1": {
                            "name": "Protein Bar",
                            "ingredients": ["protein bar"],
                            "nutrition": {"calories": 200, "protein": 20, "carbs": 15, "fat": 8}
                        },
                        "snack_2": {
                            "name": "Smoothie with Spinach and Banana",
                            "ingredients": ["spinach", "banana", "almond milk", "protein powder"],
                            "nutrition": {"calories": 220, "protein": 18, "carbs": 25, "fat": 6}
                        }
                    },
                    "day_5": {
                        "breakfast": {
                            "name": "Avocado Toast with Poached Eggs",
                            "ingredients": ["whole grain bread", "avocado", "eggs", "microgreens"],
                            "nutrition": {"calories": 380, "protein": 20, "carbs": 28, "fat": 24}
                        },
                        "lunch": {
                            "name": "Lentil Soup with Whole Grain Bread",
                            "ingredients": ["lentils", "vegetables", "whole grain bread", "olive oil"],
                            "nutrition": {"calories": 420, "protein": 22, "carbs": 55, "fat": 12}
                        },
                        "dinner": {
                            "name": "Grilled Steak with Asparagus",
                            "ingredients": ["lean steak", "asparagus", "mushrooms", "quinoa"],
                            "nutrition": {"calories": 520, "protein": 48, "carbs": 32, "fat": 26}
                        },
                        "snack_1": {
                            "name": "Trail Mix",
                            "ingredients": ["nuts", "seeds", "dried fruits"],
                            "nutrition": {"calories": 200, "protein": 8, "carbs": 20, "fat": 12}
                        },
                        "snack_2": {
                            "name": "Greek Yogurt Parfait",
                            "ingredients": ["greek yogurt", "granola", "berries", "honey"],
                            "nutrition": {"calories": 240, "protein": 16, "carbs": 28, "fat": 8}
                        }
                    },
                    "day_6": {
                        "breakfast": {
                            "name": "Chia Pudding with Mango",
                            "ingredients": ["chia seeds", "coconut milk", "mango", "honey"],
                            "nutrition": {"calories": 320, "protein": 10, "carbs": 42, "fat": 14}
                        },
                        "lunch": {
                            "name": "Grilled Fish Tacos",
                            "ingredients": ["white fish", "corn tortillas", "cabbage slaw", "lime"],
                            "nutrition": {"calories": 440, "protein": 32, "carbs": 38, "fat": 20}
                        },
                        "dinner": {
                            "name": "Vegetarian Buddha Bowl",
                            "ingredients": ["brown rice", "tofu", "vegetables", "peanut sauce"],
                            "nutrition": {"calories": 480, "protein": 18, "carbs": 58, "fat": 20}
                        },
                        "snack_1": {
                            "name": "Edamame",
                            "ingredients": ["edamame", "sea salt"],
                            "nutrition": {"calories": 160, "protein": 14, "carbs": 12, "fat": 6}
                        },
                        "snack_2": {
                            "name": "Fruit and Nut Energy Balls",
                            "ingredients": ["dates", "nuts", "coconut", "cocoa powder"],
                            "nutrition": {"calories": 180, "protein": 6, "carbs": 22, "fat": 10}
                        }
                    },
                    "day_7": {
                        "breakfast": {
                            "name": "Breakfast Burrito",
                            "ingredients": ["eggs", "black beans", "whole grain tortilla", "salsa"],
                            "nutrition": {"calories": 380, "protein": 24, "carbs": 35, "fat": 16}
                        },
                        "lunch": {
                            "name": "Chicken Caesar Salad",
                            "ingredients": ["chicken breast", "romaine lettuce", "parmesan", "caesar dressing"],
                            "nutrition": {"calories": 420, "protein": 38, "carbs": 18, "fat": 24}
                        },
                        "dinner": {
                            "name": "Baked Cod with Mediterranean Vegetables",
                            "ingredients": ["cod fillet", "bell peppers", "zucchini", "olive oil"],
                            "nutrition": {"calories": 400, "protein": 42, "carbs": 22, "fat": 18}
                        },
                        "snack_1": {
                            "name": "Cottage Cheese with Pineapple",
                            "ingredients": ["cottage cheese", "pineapple", "cinnamon"],
                            "nutrition": {"calories": 160, "protein": 16, "carbs": 15, "fat": 4}
                        },
                        "snack_2": {
                            "name": "Mixed Berry Smoothie",
                            "ingredients": ["strawberries", "blueberries", "raspberries", "almond milk"],
                            "nutrition": {"calories": 140, "protein": 4, "carbs": 22, "fat": 4}
                        }
                    }
                },
                "shopping_list": [
                    "oats", "berries", "honey", "almonds", "chicken breast", "salmon", "turkey breast",
                    "avocado", "lean beef", "eggs", "quinoa", "brown rice", "sweet potato", "spinach",
                    "kale", "broccoli", "carrots", "bell peppers", "zucchini", "mushrooms", "asparagus",
                    "greek yogurt", "cottage cheese", "hummus", "dark chocolate", "protein powder",
                    "chia seeds", "coconut milk", "mango", "white fish", "tofu", "edamame", "dates",
                    "black beans", "cod fillet", "pineapple", "mixed berries"
                ],
                "meal_prep_tips": [
                    "Prepare overnight oats for quick breakfasts",
                    "Cook chicken and quinoa in bulk for the week",
                    "Wash and chop vegetables in advance",
                    "Make smoothie ingredients ready to blend",
                    "Prepare snack portions in advance"
                ],
                "substitutions": {
                    "dairy": "almond milk or coconut milk",
                    "gluten": "quinoa or brown rice",
                    "nuts": "sunflower seeds or pumpkin seeds",
                    "eggs": "tofu scramble or chickpea flour",
                    "meat": "lentils, beans, or tempeh"
                }
            }
        
        try:
            # Calculate nutritional needs
            nutrition_needs = self.calculate_nutritional_needs(
                age=user_profile.get('age', 30),
                gender=user_profile.get('gender', 'male'),
                weight=user_profile.get('weight', 70),
                height=user_profile.get('height', 170),
                activity_level=user_profile.get('activity_level', 'moderately_active'),
                goal=user_profile.get('goal', 'maintenance')
            )
            
            # Format the prompt with user data
            prompt = self.meal_plan_prompt.format(
                age=user_profile.get('age', 30),
                gender=user_profile.get('gender', 'male'),
                weight=user_profile.get('weight', 70),
                height=user_profile.get('height', 170),
                activity_level=user_profile.get('activity_level', 'moderately_active'),
                goal=user_profile.get('goal', 'maintenance'),
                dietary_restrictions=user_profile.get('dietary_restrictions', 'none'),
                allergies=user_profile.get('allergies', 'none'),
                preferences=user_profile.get('preferences', 'none'),
                daily_calories=nutrition_needs['daily_calories'],
                daily_protein=nutrition_needs['daily_protein'],
                daily_carbs=nutrition_needs['daily_carbs'],
                daily_fat=nutrition_needs['daily_fat']
            )
            
            # Generate response from AI
            response = self.model.generate_content(prompt)
            
            # Parse the response
            try:
                meal_plan_data = json.loads(response.text)
                meal_plan_data['nutritional_needs'] = nutrition_needs
                return meal_plan_data
            except json.JSONDecodeError:
                # If JSON parsing fails, return a structured error response
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response.text,
                    "nutritional_needs": nutrition_needs
                }
                
        except Exception as e:
            # Check if it's a quota error and use fallback
            if "quota" in str(e).lower() or "429" in str(e):
                print("API quota exceeded, using fallback meal plan")
                # Return the fallback meal plan directly
                nutrition_needs = self.calculate_nutritional_needs(
                    age=user_profile.get('age', 30),
                    gender=user_profile.get('gender', 'male'),
                    weight=user_profile.get('weight', 70),
                    height=user_profile.get('height', 170),
                    activity_level=user_profile.get('activity_level', 'moderately_active'),
                    goal=user_profile.get('goal', 'maintenance')
                )
                
                return {
                    "nutritional_needs": nutrition_needs,
                    "meal_plan": {
                        "day_1": {
                            "breakfast": {
                                "name": "Oatmeal with Berries and Nuts",
                                "ingredients": ["oats", "berries", "honey", "almonds"],
                                "nutrition": {"calories": 350, "protein": 12, "carbs": 55, "fat": 8}
                            },
                            "lunch": {
                                "name": "Grilled Chicken Salad",
                                "ingredients": ["chicken breast", "mixed greens", "cherry tomatoes", "olive oil"],
                                "nutrition": {"calories": 420, "protein": 38, "carbs": 18, "fat": 22}
                            },
                            "dinner": {
                                "name": "Salmon with Roasted Vegetables",
                                "ingredients": ["salmon fillet", "broccoli", "carrots", "quinoa"],
                                "nutrition": {"calories": 480, "protein": 42, "carbs": 38, "fat": 28}
                            },
                            "snack_1": {
                                "name": "Greek Yogurt with Honey",
                                "ingredients": ["greek yogurt", "honey", "cinnamon"],
                                "nutrition": {"calories": 180, "protein": 15, "carbs": 20, "fat": 5}
                            },
                            "snack_2": {
                                "name": "Apple with Almond Butter",
                                "ingredients": ["apple", "almond butter"],
                                "nutrition": {"calories": 200, "protein": 6, "carbs": 25, "fat": 12}
                            }
                        },
                        "day_2": {
                            "breakfast": {
                                "name": "Protein Smoothie Bowl",
                                "ingredients": ["protein powder", "banana", "spinach", "almond milk"],
                                "nutrition": {"calories": 320, "protein": 25, "carbs": 35, "fat": 8}
                            },
                            "lunch": {
                                "name": "Turkey and Avocado Wrap",
                                "ingredients": ["turkey breast", "avocado", "whole wheat tortilla", "lettuce"],
                                "nutrition": {"calories": 450, "protein": 32, "carbs": 42, "fat": 18}
                            },
                            "dinner": {
                                "name": "Lean Beef Stir-Fry",
                                "ingredients": ["lean beef", "broccoli", "bell peppers", "brown rice"],
                                "nutrition": {"calories": 520, "protein": 45, "carbs": 45, "fat": 22}
                            },
                            "snack_1": {
                                "name": "Mixed Nuts and Dried Fruits",
                                "ingredients": ["almonds", "walnuts", "raisins", "cranberries"],
                                "nutrition": {"calories": 220, "protein": 8, "carbs": 18, "fat": 16}
                            },
                            "snack_2": {
                                "name": "Cottage Cheese with Berries",
                                "ingredients": ["cottage cheese", "strawberries", "blueberries"],
                                "nutrition": {"calories": 160, "protein": 18, "carbs": 12, "fat": 4}
                            }
                        },
                        "day_3": {
                            "breakfast": {
                                "name": "Eggs Benedict with Spinach",
                                "ingredients": ["eggs", "spinach", "whole grain toast", "hollandaise"],
                                "nutrition": {"calories": 380, "protein": 22, "carbs": 28, "fat": 24}
                            },
                            "lunch": {
                                "name": "Quinoa Buddha Bowl",
                                "ingredients": ["quinoa", "chickpeas", "kale", "sweet potato", "tahini"],
                                "nutrition": {"calories": 480, "protein": 18, "carbs": 65, "fat": 16}
                            },
                            "dinner": {
                                "name": "Grilled Shrimp with Zucchini Noodles",
                                "ingredients": ["shrimp", "zucchini", "garlic", "olive oil", "lemon"],
                                "nutrition": {"calories": 360, "protein": 38, "carbs": 12, "fat": 18}
                            },
                            "snack_1": {
                                "name": "Hummus with Carrot Sticks",
                                "ingredients": ["hummus", "carrots", "celery"],
                                "nutrition": {"calories": 180, "protein": 8, "carbs": 22, "fat": 8}
                            },
                            "snack_2": {
                                "name": "Dark Chocolate and Almonds",
                                "ingredients": ["dark chocolate", "almonds"],
                                "nutrition": {"calories": 240, "protein": 6, "carbs": 18, "fat": 18}
                            }
                        },
                        "day_4": {
                            "breakfast": {
                                "name": "Protein Pancakes with Maple Syrup",
                                "ingredients": ["protein powder", "oats", "eggs", "maple syrup", "berries"],
                                "nutrition": {"calories": 420, "protein": 28, "carbs": 45, "fat": 12}
                            },
                            "lunch": {
                                "name": "Mediterranean Salad with Tuna",
                                "ingredients": ["tuna", "olives", "cucumber", "tomatoes", "feta cheese"],
                                "nutrition": {"calories": 380, "protein": 35, "carbs": 15, "fat": 20}
                            },
                            "dinner": {
                                "name": "Baked Chicken with Sweet Potato",
                                "ingredients": ["chicken breast", "sweet potato", "green beans", "herbs"],
                                "nutrition": {"calories": 460, "protein": 42, "carbs": 38, "fat": 16}
                            },
                            "snack_1": {
                                "name": "Protein Bar",
                                "ingredients": ["protein bar"],
                                "nutrition": {"calories": 200, "protein": 20, "carbs": 15, "fat": 8}
                            },
                            "snack_2": {
                                "name": "Smoothie with Spinach and Banana",
                                "ingredients": ["spinach", "banana", "almond milk", "protein powder"],
                                "nutrition": {"calories": 220, "protein": 18, "carbs": 25, "fat": 6}
                            }
                        },
                        "day_5": {
                            "breakfast": {
                                "name": "Avocado Toast with Poached Eggs",
                                "ingredients": ["whole grain bread", "avocado", "eggs", "microgreens"],
                                "nutrition": {"calories": 380, "protein": 20, "carbs": 28, "fat": 24}
                            },
                            "lunch": {
                                "name": "Lentil Soup with Whole Grain Bread",
                                "ingredients": ["lentils", "vegetables", "whole grain bread", "olive oil"],
                                "nutrition": {"calories": 420, "protein": 22, "carbs": 55, "fat": 12}
                            },
                            "dinner": {
                                "name": "Grilled Steak with Asparagus",
                                "ingredients": ["lean steak", "asparagus", "mushrooms", "quinoa"],
                                "nutrition": {"calories": 520, "protein": 48, "carbs": 32, "fat": 26}
                            },
                            "snack_1": {
                                "name": "Trail Mix",
                                "ingredients": ["nuts", "seeds", "dried fruits"],
                                "nutrition": {"calories": 200, "protein": 8, "carbs": 20, "fat": 12}
                            },
                            "snack_2": {
                                "name": "Greek Yogurt Parfait",
                                "ingredients": ["greek yogurt", "granola", "berries", "honey"],
                                "nutrition": {"calories": 240, "protein": 16, "carbs": 28, "fat": 8}
                            }
                        },
                        "day_6": {
                            "breakfast": {
                                "name": "Chia Pudding with Mango",
                                "ingredients": ["chia seeds", "coconut milk", "mango", "honey"],
                                "nutrition": {"calories": 320, "protein": 10, "carbs": 42, "fat": 14}
                            },
                            "lunch": {
                                "name": "Grilled Fish Tacos",
                                "ingredients": ["white fish", "corn tortillas", "cabbage slaw", "lime"],
                                "nutrition": {"calories": 440, "protein": 32, "carbs": 38, "fat": 20}
                            },
                            "dinner": {
                                "name": "Vegetarian Buddha Bowl",
                                "ingredients": ["brown rice", "tofu", "vegetables", "peanut sauce"],
                                "nutrition": {"calories": 480, "protein": 18, "carbs": 58, "fat": 20}
                            },
                            "snack_1": {
                                "name": "Edamame",
                                "ingredients": ["edamame", "sea salt"],
                                "nutrition": {"calories": 160, "protein": 14, "carbs": 12, "fat": 6}
                            },
                            "snack_2": {
                                "name": "Fruit and Nut Energy Balls",
                                "ingredients": ["dates", "nuts", "coconut", "cocoa powder"],
                                "nutrition": {"calories": 180, "protein": 6, "carbs": 22, "fat": 10}
                            }
                        },
                        "day_7": {
                            "breakfast": {
                                "name": "Breakfast Burrito",
                                "ingredients": ["eggs", "black beans", "whole grain tortilla", "salsa"],
                                "nutrition": {"calories": 380, "protein": 24, "carbs": 35, "fat": 16}
                            },
                            "lunch": {
                                "name": "Chicken Caesar Salad",
                                "ingredients": ["chicken breast", "romaine lettuce", "parmesan", "caesar dressing"],
                                "nutrition": {"calories": 420, "protein": 38, "carbs": 18, "fat": 24}
                            },
                            "dinner": {
                                "name": "Baked Cod with Mediterranean Vegetables",
                                "ingredients": ["cod fillet", "bell peppers", "zucchini", "olive oil"],
                                "nutrition": {"calories": 400, "protein": 42, "carbs": 22, "fat": 18}
                            },
                            "snack_1": {
                                "name": "Cottage Cheese with Pineapple",
                                "ingredients": ["cottage cheese", "pineapple", "cinnamon"],
                                "nutrition": {"calories": 160, "protein": 16, "carbs": 15, "fat": 4}
                            },
                            "snack_2": {
                                "name": "Mixed Berry Smoothie",
                                "ingredients": ["strawberries", "blueberries", "raspberries", "almond milk"],
                                "nutrition": {"calories": 140, "protein": 4, "carbs": 22, "fat": 4}
                            }
                        }
                    },
                    "shopping_list": [
                        "oats", "berries", "honey", "almonds", "chicken breast", "salmon", "turkey breast",
                        "avocado", "lean beef", "eggs", "quinoa", "brown rice", "sweet potato", "spinach",
                        "kale", "broccoli", "carrots", "bell peppers", "zucchini", "mushrooms", "asparagus",
                        "greek yogurt", "cottage cheese", "hummus", "dark chocolate", "protein powder",
                        "chia seeds", "coconut milk", "mango", "white fish", "tofu", "edamame", "dates",
                        "black beans", "cod fillet", "pineapple", "mixed berries"
                    ],
                    "meal_prep_tips": [
                        "Prepare overnight oats for quick breakfasts",
                        "Cook chicken and quinoa in bulk for the week",
                        "Wash and chop vegetables in advance",
                        "Make smoothie ingredients ready to blend",
                        "Prepare snack portions in advance"
                    ],
                    "substitutions": {
                        "dairy": "almond milk or coconut milk",
                        "gluten": "quinoa or brown rice",
                        "nuts": "sunflower seeds or pumpkin seeds",
                        "eggs": "tofu scramble or chickpea flour",
                        "meat": "lentils, beans, or tempeh"
                    }
                }
            return {"error": f"Error generating meal plan: {str(e)}"}
    
    def generate_custom_meal(self, meal_requirements: Dict) -> Dict:
        """Generate a custom meal based on specific requirements"""
        
        if not self.model:
            # Return a sample custom meal for testing when AI is not available
            return {
                "meal": {
                    "name": f"Custom {meal_requirements.get('meal_type', 'lunch')}",
                    "description": "A delicious and nutritious meal prepared with care",
                    "ingredients": ["protein source", "vegetables", "grains"],
                    "instructions": [
                        "Prepare your ingredients",
                        "Cook according to your preferences",
                        "Season to taste",
                        "Serve hot"
                    ],
                    "nutrition": {
                        "calories": meal_requirements.get('target_calories', 500),
                        "protein": meal_requirements.get('target_protein', 25),
                        "carbs": meal_requirements.get('target_carbs', 50),
                        "fat": meal_requirements.get('target_fat', 20)
                    },
                    "cooking_time": "30 minutes",
                    "difficulty": "Easy",
                    "substitutions": ["Use any protein source", "Substitute vegetables as needed"]
                }
            }
        
        try:
            # Format the prompt with meal requirements
            prompt = self.custom_meal_prompt.format(
                meal_type=meal_requirements.get('meal_type', 'lunch'),
                available_ingredients=meal_requirements.get('available_ingredients', 'any'),
                dietary_restrictions=meal_requirements.get('dietary_restrictions', 'none'),
                allergies=meal_requirements.get('allergies', 'none'),
                target_calories=meal_requirements.get('target_calories', 500),
                target_protein=meal_requirements.get('target_protein', 25),
                target_carbs=meal_requirements.get('target_carbs', 50),
                target_fat=meal_requirements.get('target_fat', 20)
            )
            
            # Generate response from AI
            response = self.model.generate_content(prompt)
            
            # Parse the response
            try:
                meal_data = json.loads(response.text)
                return meal_data
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response.text
                }
                
        except Exception as e:
            # Check if it's a quota error and use fallback
            if "quota" in str(e).lower() or "429" in str(e):
                print("API quota exceeded, using fallback custom meal")
                # Return the fallback custom meal directly
                return {
                    "meal": {
                        "name": f"Custom {meal_requirements.get('meal_type', 'lunch')}",
                        "description": "A delicious and nutritious meal prepared with care",
                        "ingredients": ["protein source", "vegetables", "grains"],
                        "instructions": [
                            "Prepare your ingredients",
                            "Cook according to your preferences",
                            "Season to taste",
                            "Serve hot"
                        ],
                        "nutrition": {
                            "calories": meal_requirements.get('target_calories', 500),
                            "protein": meal_requirements.get('target_protein', 25),
                            "carbs": meal_requirements.get('target_carbs', 50),
                            "fat": meal_requirements.get('target_fat', 20)
                        },
                        "cooking_time": "30 minutes",
                        "difficulty": "Easy",
                        "substitutions": ["Use any protein source", "Substitute vegetables as needed"]
                    }
                }
            return {"error": f"Error generating custom meal: {str(e)}"}
    
    def analyze_nutrition_photo(self, photo_data: bytes, detected_foods: List[str] = None) -> Dict:
        """Analyze a nutrition photo and provide AI insights"""
        
        if not self.model:
            return {"error": "AI model not available. Please check your API key."}
        
        try:
            # Convert photo to base64 for API
            import base64
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')
            
            # Create prompt for photo analysis
            prompt = f"""Analyze this food photo and provide detailed nutritional information.

Detected foods: {detected_foods if detected_foods else 'None detected'}

Please provide:
1. List of foods visible in the image
2. Estimated nutritional values (calories, protein, carbs, fat)
3. Health insights and recommendations
4. Portion size estimates
5. Meal timing suggestions

Format as JSON:
{{
    "foods": [
        {{"name": "", "confidence": 0.0, "estimated_portion": ""}}
    ],
    "nutrition": {{"calories": 0, "protein": 0, "carbs": 0, "fat": 0}},
    "insights": [],
    "recommendations": [],
    "meal_timing": ""
}}"""
            
            # Generate response from AI with image
            response = self.model.generate_content([prompt, {"mime_type": "image/jpeg", "data": photo_base64}])
            
            # Parse the response
            try:
                analysis_data = json.loads(response.text)
                return analysis_data
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response.text
                }
                
        except Exception as e:
            return {"error": f"Error analyzing nutrition photo: {str(e)}"}
    
    def get_nutrition_insights(self, nutrition_data: Dict) -> Dict:
        """Generate AI insights based on nutrition data"""
        
        if not self.model:
            return {"error": "AI model not available. Please check your API key."}
        
        try:
            prompt = f"""Analyze this nutrition data and provide personalized insights:

Nutrition Data:
- Calories: {nutrition_data.get('calories', 0)} kcal
- Protein: {nutrition_data.get('protein', 0)}g
- Carbs: {nutrition_data.get('carbs', 0)}g
- Fat: {nutrition_data.get('fat', 0)}g
- Goal: {nutrition_data.get('goal', 'maintenance')}
- Activity Level: {nutrition_data.get('activity_level', 'moderately_active')}

Provide:
1. Overall nutrition assessment
2. Specific recommendations
3. Areas for improvement
4. Positive aspects to maintain
5. Meal timing suggestions

Format as JSON:
{{
    "assessment": "",
    "recommendations": [],
    "improvements": [],
    "positives": [],
    "meal_timing": ""
}}"""
            
            response = self.model.generate_content(prompt)
            
            try:
                insights_data = json.loads(response.text)
                return insights_data
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response.text
                }
                
        except Exception as e:
            return {"error": f"Error generating nutrition insights: {str(e)}"}

# Global instance
meal_planner = AIMealPlanner() 