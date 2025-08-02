from fastapi import FastAPI, HTTPException, Request, Depends, Form, status, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Body

import pymysql
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
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
from transformers import AutoImageProcessor, SiglipForImageClassification
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

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
        return user
    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")  # Debug log
        return None

# FastAPI dependency version of get_current_user
def get_current_user_dependency(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Database connection
def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="omaromar",
        database="trainer_app",
        cursorclass=pymysql.cursors.DictCursor
    )

# Initialize database tables
def init_db():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Create gyms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gyms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                address VARCHAR(200),
                phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create coaches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coaches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gym_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                specialization VARCHAR(100),
                experience INT DEFAULT 0,
                role_level ENUM('Junior Coach', 'Senior Coach', 'Head Coach', 'Personal Trainer', 'Specialist') DEFAULT 'Senior Coach',
                status ENUM('Active', 'Inactive') DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            )
        """)
        
        # Create members table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gym_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                membership_type ENUM('Basic', 'Premium', 'VIP') DEFAULT 'Basic',
                join_date DATE DEFAULT (CURRENT_DATE),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            )
        """)
        
        # Create member_coach table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS member_coach (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                coach_id INT NOT NULL,
                assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (coach_id) REFERENCES coaches(id),
                UNIQUE KEY unique_member_coach (member_id, coach_id)
            )
        """)
        
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gym_id INT NOT NULL,
                coach_id INT NOT NULL,
                member_id INT NOT NULL,
                session_date DATE NOT NULL,
                session_time TIME NOT NULL,
                duration INT NOT NULL,  -- in minutes
                status ENUM('Scheduled', 'Completed', 'Cancelled') DEFAULT 'Scheduled',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gym_id) REFERENCES gyms(id),
                FOREIGN KEY (coach_id) REFERENCES coaches(id),
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)

        # Create AI Calorie Tracker tables
        
        # Food items database
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS food_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                brand VARCHAR(100),
                barcode VARCHAR(50),
                calories_per_100g DECIMAL(7,2) NOT NULL,
                protein_per_100g DECIMAL(7,2) DEFAULT 0,
                carbs_per_100g DECIMAL(7,2) DEFAULT 0,
                fat_per_100g DECIMAL(7,2) DEFAULT 0,
                fiber_per_100g DECIMAL(7,2) DEFAULT 0,
                sugar_per_100g DECIMAL(7,2) DEFAULT 0,
                sodium_per_100g DECIMAL(7,2) DEFAULT 0,
                category VARCHAR(100),
                source ENUM('OpenFoodFacts', 'Manual', 'AI_Generated') DEFAULT 'Manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_name (name),
                INDEX idx_barcode (barcode)
            )
        """)
        
        # Nutrition logs for tracking meals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nutrition_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                meal_type ENUM('breakfast', 'lunch', 'dinner', 'snack') NOT NULL,
                food_name VARCHAR(200) NOT NULL,
                quantity DECIMAL(7,2) NOT NULL,
                unit ENUM('grams', 'ml', 'pieces', 'cups', 'tablespoons', 'serving') DEFAULT 'grams',
                calories DECIMAL(7,2) NOT NULL,
                protein DECIMAL(7,2) DEFAULT 0,
                carbs DECIMAL(7,2) DEFAULT 0,
                fat DECIMAL(7,2) DEFAULT 0,
                photo_path VARCHAR(500),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                INDEX idx_member_date (member_id, created_at)
            )
        """)
        
        # AI meal analysis and suggestions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meal_analysis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                analysis_date DATE NOT NULL,
                total_calories DECIMAL(7,2) NOT NULL,
                total_protein DECIMAL(7,2) NOT NULL,
                total_carbs DECIMAL(7,2) NOT NULL,
                total_fat DECIMAL(7,2) NOT NULL,
                calorie_goal DECIMAL(7,2),
                protein_goal DECIMAL(7,2),
                carbs_goal DECIMAL(7,2),
                fat_goal DECIMAL(7,2),
                ai_feedback TEXT,
                suggestions TEXT,
                health_score DECIMAL(3,1),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                INDEX idx_member_date (member_id, analysis_date)
            )
        """)
        
        # Coach nutrition comments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nutrition_comments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                coach_id INT NOT NULL,
                comment_date DATE NOT NULL,
                comment TEXT NOT NULL,
                nutrition_log_id INT,
                meal_analysis_id INT,
                comment_type ENUM('General', 'Meal_Specific', 'Goal_Adjustment') DEFAULT 'General',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (coach_id) REFERENCES coaches(id),
                FOREIGN KEY (nutrition_log_id) REFERENCES nutrition_logs(id),
                FOREIGN KEY (meal_analysis_id) REFERENCES meal_analysis(id),
                INDEX idx_member_date (member_id, comment_date)
            )
        """)
        
        # Member nutrition goals and preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nutrition_goals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL UNIQUE,
                daily_calorie_goal DECIMAL(7,2) DEFAULT 2000,
                daily_protein_goal DECIMAL(7,2) DEFAULT 150,
                daily_carbs_goal DECIMAL(7,2) DEFAULT 250,
                daily_fat_goal DECIMAL(7,2) DEFAULT 70,
                goal_type ENUM('Weight_Loss', 'Weight_Gain', 'Maintenance', 'Muscle_Gain') DEFAULT 'Maintenance',
                dietary_restrictions TEXT,
                allergies TEXT,
                preferred_cuisines TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)
        
        # AI-generated nutrition plans
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nutrition_plans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT,
                coach_id INT,
                plan_name VARCHAR(200) NOT NULL,
                plan_data JSON,
                daily_calories INT,
                daily_protein INT,
                daily_carbs INT,
                daily_fat INT,
                notes TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (coach_id) REFERENCES coaches(id),
                INDEX idx_member (member_id),
                INDEX idx_coach (coach_id),
                INDEX idx_created (created_at)
            )
        """)

        # Create payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                gym_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payment_type ENUM('Membership', 'Session', 'Other') NOT NULL,
                status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
                notes TEXT,
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            )
        """)
        
        # Create user_preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                user_type ENUM('coach', 'member') NOT NULL,
                preferred_workout_types JSON,
                preferred_duration INT DEFAULT 60,
                preferred_time_slots JSON,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_pref (user_id, user_type)
            )
        """)
        
        # Create availability_slots table for date and hour based availability
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS availability_slots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                user_type ENUM('coach', 'member') NOT NULL,
                date DATE NOT NULL,
                hour INT NOT NULL CHECK (hour >= 0 AND hour <= 23),
                is_available BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_date_hour (user_id, user_type, date, hour)
            )
        """)
        
        # Keep the old free_days table for backward compatibility (will be removed later)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS free_days (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                user_type ENUM('coach', 'member') NOT NULL,
                day_of_week ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday') NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                start_time TIME DEFAULT '08:00:00',
                end_time TIME DEFAULT '20:00:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_day (user_id, user_type, day_of_week)
            )
        """)
        
        # Messages table for communication between users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                sender_type ENUM('gym', 'coach', 'member') NOT NULL,
                receiver_id INT NOT NULL,
                receiver_type ENUM('gym', 'coach', 'member') NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_sender (sender_id, sender_type),
                INDEX idx_receiver (receiver_id, receiver_type),
                INDEX idx_conversation (sender_id, sender_type, receiver_id, receiver_type),
                INDEX idx_created_at (created_at)
            )
        """)
        
        connection.commit()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

# Initialize database on startup
init_db()

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
                    <option value="admin">Admin</option>
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
    date_range: str = "all",
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
        if date_range != "all":
            if date_range == "today":
                query += " AND s.session_date = CURDATE()"
            elif date_range == "week":
                query += " AND s.session_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
            elif date_range == "month":
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
        
        # Get stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_sessions,
                SUM(CASE WHEN session_date >= CURDATE() THEN 1 ELSE 0 END) as upcoming_sessions
            FROM sessions
            WHERE member_id = %s
        """, (user["id"],))
        stats = cursor.fetchone()
        
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
            "stats": stats,
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

@app.get("/api/regenerate-db")
async def regenerate_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Drop existing tables in correct order (respecting foreign key constraints)
        cursor.execute("DROP TABLE IF EXISTS payments")
        cursor.execute("DROP TABLE IF EXISTS member_coach")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        cursor.execute("DROP TABLE IF EXISTS members")
        cursor.execute("DROP TABLE IF EXISTS coaches")
        cursor.execute("DROP TABLE IF EXISTS gyms")
        
        connection.commit()
        
        # Reinitialize database
        init_db()
        
        # Insert one gym
        cursor.execute("""
            INSERT INTO gyms (name, email, password, address, phone)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            "PowerFit Gym",
            "powerfit@example.com",
            "gym123",
            "123 Fitness Street",
            "123-456-7890"
        ))
        gym_id = cursor.lastrowid
        
        # Insert 4 coaches with specializations
        coaches = [
            ("John Doe", "john@example.com", "coach123", "Strength Training"),
            ("Jane Smith", "jane@example.com", "coach123", "Functional Training"),
            ("Mike Johnson", "mike@example.com", "coach123", "Bodybuilding"),
            ("Sarah Williams", "sarah@example.com", "coach123", "Powerlifting")
        ]
        coach_ids = []
        for coach in coaches:
            cursor.execute("""
                INSERT INTO coaches (gym_id, name, email, password, specialization, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (gym_id, coach[0], coach[1], coach[2], coach[3], "Active"))
            coach_ids.append(cursor.lastrowid)
        
        # Insert 15 members
        members = [
            ("Alice Johnson", "alice@example.com", "member123", "Premium"),
            ("Bob Smith", "bob@example.com", "member123", "Basic"),
            ("Carol White", "carol@example.com", "member123", "VIP"),
            ("David Brown", "david@example.com", "member123", "Premium"),
            ("Eva Davis", "eva@example.com", "member123", "Basic"),
            ("Frank Miller", "frank@example.com", "member123", "Premium"),
            ("Grace Lee", "grace@example.com", "member123", "Basic"),
            ("Henry Wilson", "henry@example.com", "member123", "VIP"),
            ("Ivy Taylor", "ivy@example.com", "member123", "Premium"),
            ("Jack Anderson", "jack@example.com", "member123", "Basic"),
            ("Kelly Martinez", "kelly@example.com", "member123", "Premium"),
            ("Liam Garcia", "liam@example.com", "member123", "Basic"),
            ("Mia Robinson", "mia@example.com", "member123", "VIP"),
            ("Noah Clark", "noah@example.com", "member123", "Premium"),
            ("Olivia Lewis", "olivia@example.com", "member123", "Basic")
        ]
        member_ids = []
        for member in members:
            cursor.execute("""
                INSERT INTO members (gym_id, name, email, password, membership_type, join_date)
                VALUES (%s, %s, %s, %s, %s, CURDATE())
            """, (gym_id, member[0], member[1], member[2], member[3]))
            member_ids.append(cursor.lastrowid)
        
        # Assign members to coaches (distribute members among coaches)
        for i, member_id in enumerate(member_ids):
            coach_id = coach_ids[i % len(coach_ids)]  # Distribute members evenly among coaches
        cursor.execute("""
            INSERT INTO member_coach (member_id, coach_id)
            VALUES (%s, %s)
            """, (member_id, coach_id))
        
        # Add sample sessions with specific exercise types
        today = datetime.now().date()
        
        # Create sessions for the next 7 days
        for day in range(7):
            session_date = today + timedelta(days=day)
            
            # Create 2-3 sessions per day
            for hour in [9, 14, 16]:  # Morning, afternoon, and evening sessions
                # Skip some sessions randomly to make it more realistic
                if hour == 14 and day % 2 == 0:  # Skip some afternoon sessions
                    continue
                
                # Create sessions for each coach
                for coach_id in coach_ids:
                    # Get members assigned to this coach
                    cursor.execute("""
                        SELECT member_id 
                        FROM member_coach 
                        WHERE coach_id = %s
                    """, (coach_id,))
                    coach_members = cursor.fetchall()
                    
                    if coach_members:
                        # Create a session for one of the coach's members
                        member = coach_members[day % len(coach_members)]
                        session_time = f"{hour:02d}:00:00"
                        
                        # Select a random workout template
                        workout_type = random.choice(list(WORKOUT_TEMPLATES.keys()))
                        exercises = WORKOUT_TEMPLATES[workout_type]
                        
                        # Create detailed notes with exercises
                        notes = f"Workout Type: {workout_type}\n"
                        for i, exercise in enumerate(exercises, 1):
                            notes += f"{i}. {exercise}\n"
                        
                        cursor.execute("""
                            INSERT INTO sessions (
                                gym_id,
                                coach_id,
                                member_id,
                                session_date,
                                session_time,
                                duration,
                                status,
                                notes
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            gym_id,
                            coach_id,
                            member["member_id"],
                            session_date,
                            session_time,
                            60,  # 1-hour sessions
                            "Scheduled",
                            notes
                        ))
        
        connection.commit()
        return JSONResponse(content={"detail": "Database regenerated successfully with sample data"})
    except Exception as e:
        connection.rollback()
        print(f"Error regenerating database: {str(e)}")  # Add debug logging
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

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
        
        # Get stats
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT mc.member_id) as total_members,
                COUNT(DISTINCT s.id) as total_sessions,
                COUNT(DISTINCT CASE WHEN s.status = 'Completed' THEN s.id END) as completed_sessions,
                COUNT(DISTINCT CASE WHEN s.session_date >= CURDATE() THEN s.id END) as upcoming_sessions
            FROM coaches c
            LEFT JOIN member_coach mc ON c.id = mc.coach_id
            LEFT JOIN sessions s ON c.id = s.coach_id
            WHERE c.id = %s
        """, (user["id"],))
        stats = cursor.fetchone()
        
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
                "upcoming_sessions": stats["upcoming_sessions"] or 0
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

# Add this constant at the top of your file with your actual API key

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
                        "You are a helpful assistant.\n\n"
                        "Project PowerFit is a modern web-based gym management platform that connects gyms, coaches, and members.\n\n"
                        "• Gyms can manage their staff and clients, monitor member progress, set up different membership types (like Basic, Premium, and VIP), track training sessions, and manage payments.\n"
                        "• Coaches can view their schedule, assign training sessions, track the progress of the members they train, and adjust plans based on preferences.\n"
                        "• Members can log in to see their coach, track past and upcoming training sessions, and manage personal information like training preferences and membership details.\n\n"
                        "Be ready to help users with these common questions:\n\n"
                        "• 'How do I log in?'  \n"
                        "  → You log in with the username and password your gym provided. If you forgot them, ask your gym to reset your login.\n\n"
                        "• 'How do I change my workout preferences?'  \n"
                        "  → After logging in, go to the schedule page where you can update the types of exercises you like or the times you're available. Your coach will use this info to build a better plan for you.\n\n"
                        "• 'How do I see my training schedule?'  \n"
                        "  → You'll find a calendar or list on your dashboard showing all upcoming sessions. If something is missing, ask your coach or gym.\n\n"
                        "• 'Can I change my coach?'  \n"
                        "  → Coaches are usually assigned by the gym, but you can talk to your gym staff if you want to switch.\n\n"
                        "• 'How do I see my progress?'  \n"
                        "  → On your profile or dashboard, you'll find a progress section with a summary of your completed workouts, improvements, or coach feedback.\n\n"
                        "• 'What membership do I have?'  \n"
                        "  → You can check your membership details (like whether you're Basic, Premium, or VIP) on your profile. If you want to upgrade or change it, contact your gym.\n\n"
                        "• 'How do payments work?'  \n"
                        "  → Payments are handled by the gym. You can see your latest membership or session payments in your account area.\n\n"
                        "• 'I need help!'  \n"
                        "  → No problem! You can always message your coach or gym staff directly through the contact section.\n\n"
                        "Answer these questions in a friendly, clear, and simple way, without using technical terms."
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

        cursor.execute("""
            INSERT INTO sessions (gym_id, coach_id, member_id, session_date, session_time, duration, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, 'Scheduled', %s)
        """, (gym_id, coach_id, member_id, session_date, session_time, duration, f"Workout Type: {workout_type}\n{notes}" if notes else f"Workout Type: {workout_type}"))
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
        
        # Mark coach sessions
        for session in coach_sessions:
            day = session['day_name']
            hour = session['hour_slot']
            if day in schedule_grid and 0 <= hour < 24:
                schedule_grid[day][hour]['coach_session'] = {
                    'id': session['id'],
                    'member_name': session['member_name'],
                    'time': session['formatted_time'],
                    'duration': session['duration'],
                    'status': session['status'],
                    'notes': session['notes'],
                    'session_type': session.get('session_type', 'General Training')
                }
                schedule_grid[day][hour]['coach_available'] = False
        
        # Mark member sessions
        for session in member_sessions:
            day = session['day_name']
            hour = session['hour_slot']
            if day in schedule_grid and 0 <= hour < 24:
                schedule_grid[day][hour]['member_session'] = {
                    'id': session['id'],
                    'coach_name': session['coach_name'],
                    'time': session['formatted_time'],
                    'duration': session['duration'],
                    'status': session['status'],
                    'notes': session['notes'],
                    'session_type': session.get('session_type', 'General Training')
                }
                schedule_grid[day][hour]['member_available'] = False
        
        # Calculate availability for both and preference scores
        for day in days:
            for hour in range(24):
                slot = schedule_grid[day][hour]
                slot['available_for_both'] = (
                    slot['coach_available'] and 
                    slot['member_available'] and
                    not slot['coach_session'] and 
                    not slot['member_session']
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
            notes
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
                m.name as first_name,
                m.name as last_name,
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
        
        # Convert datetime objects and split name into first and last name
        for member in members:
            if member['last_nutrition_entry']:
                member['last_nutrition_entry'] = member['last_nutrition_entry'].isoformat()
            
            # Split the name into first and last name
            name_parts = member['first_name'].split(' ', 1)
            member['first_name'] = name_parts[0]
            member['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        
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
        
        # Create sample nutrition data for the past week
        sample_data = [
            # Yesterday
            (member_id, 'Breakfast', 'Oatmeal with berries', 100, 350, 12, 60, 8, '2024-01-15'),
            (member_id, 'Lunch', 'Grilled chicken salad', 150, 450, 35, 15, 25, '2024-01-15'),
            (member_id, 'Dinner', 'Salmon with vegetables', 200, 550, 40, 20, 30, '2024-01-15'),
            
            # 2 days ago
            (member_id, 'Breakfast', 'Greek yogurt with granola', 120, 320, 18, 45, 12, '2024-01-14'),
            (member_id, 'Lunch', 'Turkey sandwich', 180, 480, 28, 55, 18, '2024-01-14'),
            (member_id, 'Dinner', 'Pasta with meatballs', 250, 680, 25, 85, 22, '2024-01-14'),
            
            # 3 days ago
            (member_id, 'Breakfast', 'Eggs and toast', 150, 420, 22, 35, 20, '2024-01-13'),
            (member_id, 'Lunch', 'Caesar salad', 130, 380, 15, 25, 28, '2024-01-13'),
            (member_id, 'Dinner', 'Beef stir fry', 220, 520, 32, 40, 25, '2024-01-13'),
            
            # 4 days ago
            (member_id, 'Breakfast', 'Smoothie bowl', 140, 360, 15, 50, 12, '2024-01-12'),
            (member_id, 'Lunch', 'Quinoa bowl', 160, 440, 18, 65, 16, '2024-01-12'),
            (member_id, 'Dinner', 'Pizza slice', 200, 480, 20, 60, 18, '2024-01-12'),
            
            # 5 days ago
            (member_id, 'Breakfast', 'Protein pancakes', 180, 420, 25, 55, 15, '2024-01-11'),
            (member_id, 'Lunch', 'Tuna salad', 140, 380, 30, 20, 22, '2024-01-11'),
            (member_id, 'Dinner', 'Chicken curry', 220, 520, 28, 45, 24, '2024-01-11'),
            
            # 6 days ago
            (member_id, 'Breakfast', 'Cereal with milk', 120, 300, 12, 50, 8, '2024-01-10'),
            (member_id, 'Lunch', 'Soup and bread', 160, 400, 15, 60, 14, '2024-01-10'),
            (member_id, 'Dinner', 'Fish tacos', 180, 460, 22, 40, 20, '2024-01-10'),
            
            # 7 days ago
            (member_id, 'Breakfast', 'Bagel with cream cheese', 200, 450, 12, 70, 16, '2024-01-09'),
            (member_id, 'Lunch', 'Burger and fries', 250, 650, 25, 75, 28, '2024-01-09'),
            (member_id, 'Dinner', 'Steak with potatoes', 280, 720, 35, 45, 32, '2024-01-09'),
        ]
        
        # Insert sample data
        for data in sample_data:
            cursor.execute("""
                INSERT INTO nutrition_logs 
                (member_id, meal_type, custom_food_name, quantity, total_calories, total_protein, total_carbs, total_fat, log_date)
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
                m.name as first_name,
                m.name as last_name,
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
        
        # Convert datetime objects and split names
        for entry in recent_entries:
            if entry['created_at']:
                entry['created_at'] = entry['created_at'].isoformat()
            
            # Split the name into first and last name
            name_parts = entry['first_name'].split(' ', 1)
            entry['first_name'] = name_parts[0]
            entry['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        
        # Get nutrition trends by member
        trends_query = """
            SELECT 
                m.id,
                m.name as first_name,
                m.name as last_name,
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
        
        # Convert datetime objects and split names
        for trend in trends:
            if trend['date']:
                trend['date'] = trend['date'].isoformat()
            
            # Split the name into first and last name
            name_parts = trend['first_name'].split(' ', 1)
            trend['first_name'] = name_parts[0]
            trend['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        
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
                is_active
            FROM nutrition_plans
            WHERE member_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(plans_query, (member_id,))
        plans = cursor.fetchall()
        
        # Convert datetime objects
        for plan in plans:
            if plan['created_at']:
                plan['created_at'] = plan['created_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "plans": plans
        }
        
    except Exception as e:
        print(f"Error getting nutrition plans: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# AI Meal Planning Endpoints
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
        
        if not meal_planner:
            raise HTTPException(status_code=503, detail="AI meal planner not available")
        
        # Generate meal plan
        meal_plan = meal_planner.generate_meal_plan(user_profile)
        
        if 'error' in meal_plan:
            raise HTTPException(status_code=500, detail=meal_plan['error'])
        
        # Save meal plan to database if user is a member
        if user['user_type'] == 'member':
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO nutrition_plans 
                    (member_id, plan_name, plan_data, created_at) 
                    VALUES (%s, %s, %s, NOW())
                """, (
                    user['id'],
                    f"AI Generated Plan - {datetime.now().strftime('%Y-%m-%d')}",
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
        
        if not meal_planner:
            raise HTTPException(status_code=503, detail="AI meal planner not available")
        
        # Generate custom meal
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
    """Analyze nutrition photo using AI"""
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
        
        # Parse detected foods
        try:
            detected_foods_list = json.loads(detected_foods)
        except:
            detected_foods_list = []
        
        if not meal_planner:
            raise HTTPException(status_code=503, detail="AI meal planner not available")
        
        # Analyze photo with AI
        analysis = meal_planner.analyze_nutrition_photo(photo_data, detected_foods_list)
        
        if 'error' in analysis:
            raise HTTPException(status_code=500, detail=analysis['error'])
        
        # Save to nutrition logs if analysis is successful
        if 'nutrition' in analysis:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                # Save the photo
                photo_filename = f"nutrition_ai_{user['id']}_{int(time.time())}.jpg"
                photo_path = os.path.join("static", "images", photo_filename)
                
                with open(photo_path, "wb") as f:
                    f.write(photo_data)
                
                # Save nutrition data
                nutrition = analysis['nutrition']
                cursor.execute("""
                    INSERT INTO nutrition_logs
                    (member_id, meal_type, food_name, quantity, unit, calories, protein, carbs, fat, photo_path, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    user['id'],
                    meal_type,
                    "AI Analyzed Meal",
                    1,
                    "serving",
                    nutrition.get('calories', 0),
                    nutrition.get('protein', 0),
                    nutrition.get('carbs', 0),
                    nutrition.get('fat', 0),
                    photo_filename,
                    f"AI Analysis: {', '.join([food['name'] for food in analysis.get('foods', [])])}"
                ))
                conn.commit()
                
                # Add AI insights
                analysis['ai_insights'] = meal_planner.get_nutrition_insights({
                    'calories': nutrition.get('calories', 0),
                    'protein': nutrition.get('protein', 0),
                    'carbs': nutrition.get('carbs', 0),
                    'fat': nutrition.get('fat', 0),
                    'goal': 'maintenance',
                    'activity_level': 'moderately_active'
                })
                
            except Exception as e:
                print(f"Error saving AI nutrition analysis: {e}")
            finally:
                cursor.close()
                conn.close()
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing nutrition photo with AI: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 