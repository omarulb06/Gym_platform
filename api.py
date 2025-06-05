from fastapi import FastAPI, HTTPException, Request, Depends, Form
import pymysql
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
import secrets
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import bcrypt
import json
import os
import random

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
                FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
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

        # Create notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                sender_type ENUM('gym', 'coach', 'member') NOT NULL,
                receiver_id INT NOT NULL,
                receiver_type ENUM('gym', 'coach', 'member') NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create messages table
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
                INDEX idx_sender (sender_id, sender_type),
                INDEX idx_receiver (receiver_id, receiver_type)
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


# Member API Endpoints
@app.get("/api/member/dashboard", response_class=HTMLResponse)
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


@app.get("/api/regenerate-db")
async def regenerate_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Drop tables in reverse order of dependencies
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Drop all tables
        tables = [
            "messages",
            "notifications",
            "payments",
            "sessions",
            "member_coach",
            "members",
            "coaches",
            "gyms"
        ]
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception as e:
                print(f"Error dropping table {table}: {str(e)}")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        # Create tables in correct order
        # Create gyms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gyms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                address TEXT,
                phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create coaches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coaches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                gym_id INT NOT NULL,
                specialization VARCHAR(100),
                phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
            )
        """)
        
        # Create members table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                gym_id INT NOT NULL,
                membership_type ENUM('Basic', 'Premium', 'VIP') DEFAULT 'Basic',
                membership_start_date DATE,
                membership_end_date DATE,
                phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
            )
        """)
        
        # Create member_coach table
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

        # Create notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                sender_type ENUM('gym', 'coach', 'member') NOT NULL,
                receiver_id INT NOT NULL,
                receiver_type ENUM('gym', 'coach', 'member') NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create messages table
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
                INDEX idx_sender (sender_id, sender_type),
                INDEX idx_receiver (receiver_id, receiver_type)
            )
        """)
        
        # Insert sample data
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
                INSERT INTO coaches (name, email, password, gym_id, specialization, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (coach[0], coach[1], coach[2], gym_id, coach[3], "123-456-7890"))
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
                INSERT INTO members (name, email, password, gym_id, membership_type, membership_start_date, phone)
                VALUES (%s, %s, %s, %s, %s, CURDATE(), %s)
            """, (member[0], member[1], member[2], gym_id, member[3], "123-456-7890"))
            member_ids.append(cursor.lastrowid)
        
        # Assign members to coaches (distribute members among coaches)
        for i, member_id in enumerate(member_ids):
            coach_id = coach_ids[i % len(coach_ids)]  # Distribute members evenly among coaches
            cursor.execute("""
                INSERT INTO member_coach (member_id, coach_id)
                VALUES (%s, %s)
            """, (member_id, coach_id))
        
        # Add sample sessions
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
                            "Regular training session"
                        ))
        
        connection.commit()
        return {"message": "Database regenerated successfully with sample data"}
    except Exception as e:
        print(f"Error regenerating database: {str(e)}")
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        connection.close()



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


@app.get("/api/user")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session_id")
    return response


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


# Notification endpoints
@app.post("/api/notifications/send")
async def send_notification(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get notification data from request
        data = await request.json()
        required_fields = ["receiver_id", "receiver_type", "title", "message"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate receiver type
        if data["receiver_type"] not in ["gym", "coach", "member"]:
            raise HTTPException(status_code=400, detail="Invalid receiver type")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check permissions based on user type
            if user["user_type"] == "gym":
                # Gym can send to anyone
                pass
            elif user["user_type"] == "coach":
                # Coach can only send to their gym or their members
                if data["receiver_type"] == "gym":
                    # Verify it's their gym
                    cursor.execute("SELECT gym_id FROM coaches WHERE id = %s", (user["id"],))
                    coach = cursor.fetchone()
                    if not coach or coach["gym_id"] != data["receiver_id"]:
                        raise HTTPException(status_code=403, detail="Can only send to your gym")
                elif data["receiver_type"] == "member":
                    # Verify member is assigned to this coach
                    cursor.execute("""
                        SELECT 1 FROM member_coach 
                        WHERE coach_id = %s AND member_id = %s
                    """, (user["id"], data["receiver_id"]))
                    if not cursor.fetchone():
                        raise HTTPException(status_code=403, detail="Can only send to your members")
                else:
                    raise HTTPException(status_code=403, detail="Invalid receiver type for coach")
            elif user["user_type"] == "member":
                # Member can only send to their gym or their coach
                if data["receiver_type"] == "gym":
                    # Verify it's their gym
                    cursor.execute("SELECT gym_id FROM members WHERE id = %s", (user["id"],))
                    member = cursor.fetchone()
                    if not member or member["gym_id"] != data["receiver_id"]:
                        raise HTTPException(status_code=403, detail="Can only send to your gym")
                elif data["receiver_type"] == "coach":
                    # Verify coach is assigned to this member
                    cursor.execute("""
                        SELECT 1 FROM member_coach 
                        WHERE member_id = %s AND coach_id = %s
                    """, (user["id"], data["receiver_id"]))
                    if not cursor.fetchone():
                        raise HTTPException(status_code=403, detail="Can only send to your coach")
                else:
                    raise HTTPException(status_code=403, detail="Invalid receiver type for member")
            
            # Create notification
            cursor.execute("""
                INSERT INTO notifications (
                    sender_id,
                    sender_type,
                    receiver_id,
                    receiver_type,
                    title,
                    message
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user["id"],
                user["user_type"],
                data["receiver_id"],
                data["receiver_type"],
                data["title"],
                data["message"]
            ))
            
            notification_id = cursor.lastrowid
            conn.commit()
            
            return {
                "message": "Notification sent successfully",
                "notification_id": notification_id
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error sending notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notifications")
async def get_notifications(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get notifications for the user
        cursor.execute("""
            SELECT 
                n.*,
                CASE 
                    WHEN n.sender_type = 'gym' THEN g.name
                    WHEN n.sender_type = 'coach' THEN c.name
                    WHEN n.sender_type = 'member' THEN m.name
                END as sender_name
            FROM notifications n
            LEFT JOIN gyms g ON n.sender_type = 'gym' AND n.sender_id = g.id
            LEFT JOIN coaches c ON n.sender_type = 'coach' AND n.sender_id = c.id
            LEFT JOIN members m ON n.sender_type = 'member' AND n.sender_id = m.id
            WHERE n.receiver_id = %s AND n.receiver_type = %s
            ORDER BY n.created_at DESC
        """, (user["id"], user["user_type"]))
        
        notifications = cursor.fetchall()
        
        # Format notifications
        formatted_notifications = []
        for notification in notifications:
            formatted_notifications.append({
                "id": notification["id"],
                "sender": {
                    "id": notification["sender_id"],
                    "type": notification["sender_type"],
                    "name": notification["sender_name"]
                },
                "title": notification["title"],
                "message": notification["message"],
                "is_read": bool(notification["is_read"]),
                "created_at": notification["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return formatted_notifications
        
    except Exception as e:
        print(f"Error getting notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify notification belongs to user
        cursor.execute("""
            SELECT 1 FROM notifications 
            WHERE id = %s AND receiver_id = %s AND receiver_type = %s
        """, (notification_id, user["id"], user["user_type"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Mark as read
        cursor.execute("""
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE id = %s
        """, (notification_id,))
        
        conn.commit()
        return {"message": "Notification marked as read"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error marking notification as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/notifications/recipients")
async def get_notification_recipients(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        recipients = []
        
        if user["user_type"] == "gym":
            # Gym can send to all coaches and members
            cursor.execute("""
                SELECT id, name, 'coach' as type 
                FROM coaches 
                WHERE gym_id = %s
            """, (user["id"],))
            coaches = cursor.fetchall()
            recipients.extend(coaches)
            
            cursor.execute("""
                SELECT id, name, 'member' as type 
                FROM members 
                WHERE gym_id = %s
            """, (user["id"],))
            members = cursor.fetchall()
            recipients.extend(members)
            
        elif user["user_type"] == "coach":
            # Coach can send to their gym and their members
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type 
                FROM gyms g
                JOIN coaches c ON c.gym_id = g.id
                WHERE c.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                recipients.append(gym)
            
            cursor.execute("""
                SELECT m.id, m.name, 'member' as type 
                FROM members m
                JOIN member_coach mc ON mc.member_id = m.id
                WHERE mc.coach_id = %s
            """, (user["id"],))
            members = cursor.fetchall()
            recipients.extend(members)
            
        elif user["user_type"] == "member":
            # Member can send to their gym and their coach
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type 
                FROM gyms g
                JOIN members m ON m.gym_id = g.id
                WHERE m.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                recipients.append(gym)
            
            cursor.execute("""
                SELECT c.id, c.name, 'coach' as type 
                FROM coaches c
                JOIN member_coach mc ON mc.coach_id = c.id
                WHERE mc.member_id = %s
            """, (user["id"],))
            coach = cursor.fetchone()
            if coach:
                recipients.append(coach)
        
        return recipients
        
    except Exception as e:
        print(f"Error getting notification recipients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Messaging endpoints
@app.post("/api/messages/send")
async def send_message(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get message data from request
        data = await request.json()
        required_fields = ["receiver_id", "receiver_type", "message"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate receiver type
        if data["receiver_type"] not in ["gym", "coach", "member"]:
            raise HTTPException(status_code=400, detail="Invalid receiver type")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check permissions based on user type
            if user["user_type"] == "gym":
                # Gym can send to anyone in their gym
                if data["receiver_type"] == "coach":
                    cursor.execute("SELECT 1 FROM coaches WHERE id = %s AND gym_id = %s", 
                                 (data["receiver_id"], user["id"]))
                elif data["receiver_type"] == "member":
                    cursor.execute("SELECT 1 FROM members WHERE id = %s AND gym_id = %s", 
                                 (data["receiver_id"], user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=403, detail="Can only send to users in your gym")
            elif user["user_type"] == "coach":
                # Coach can only send to their gym or their members
                if data["receiver_type"] == "gym":
                    cursor.execute("SELECT gym_id FROM coaches WHERE id = %s", (user["id"],))
                    coach = cursor.fetchone()
                    if not coach or coach["gym_id"] != data["receiver_id"]:
                        raise HTTPException(status_code=403, detail="Can only send to your gym")
                elif data["receiver_type"] == "member":
                    cursor.execute("""
                        SELECT 1 FROM member_coach 
                        WHERE coach_id = %s AND member_id = %s
                    """, (user["id"], data["receiver_id"]))
                    if not cursor.fetchone():
                        raise HTTPException(status_code=403, detail="Can only send to your members")
                else:
                    raise HTTPException(status_code=403, detail="Invalid receiver type for coach")
            elif user["user_type"] == "member":
                # Member can only send to their gym or their coach
                if data["receiver_type"] == "gym":
                    cursor.execute("SELECT gym_id FROM members WHERE id = %s", (user["id"],))
                    member = cursor.fetchone()
                    if not member or member["gym_id"] != data["receiver_id"]:
                        raise HTTPException(status_code=403, detail="Can only send to your gym")
                elif data["receiver_type"] == "coach":
                    cursor.execute("""
                        SELECT 1 FROM member_coach 
                        WHERE member_id = %s AND coach_id = %s
                    """, (user["id"], data["receiver_id"]))
                    if not cursor.fetchone():
                        raise HTTPException(status_code=403, detail="Can only send to your coach")
                else:
                    raise HTTPException(status_code=403, detail="Invalid receiver type for member")
            
            # Create message
            cursor.execute("""
                INSERT INTO messages (
                    sender_id,
                    sender_type,
                    receiver_id,
                    receiver_type,
                    message
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user["id"],
                user["user_type"],
                data["receiver_id"],
                data["receiver_type"],
                data["message"]
            ))
            
            message_id = cursor.lastrowid
            conn.commit()
            
            return {
                "message": "Message sent successfully",
                "message_id": message_id
            }
            
        except HTTPException as he:
            conn.rollback()
            raise he
        except Exception as e:
            conn.rollback()
            print(f"Error sending message: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages")
async def get_messages(request: Request, conversation_id: str = None):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if conversation_id:
            # Get messages for a specific conversation
            sender_id, sender_type = conversation_id.split('_')
            
            cursor.execute("""
                SELECT 
                    m.*,
                    CASE 
                        WHEN m.sender_type = 'gym' THEN g.name
                        WHEN m.sender_type = 'coach' THEN c.name
                        WHEN m.sender_type = 'member' THEN mem.name
                    END as sender_name
                FROM messages m
                LEFT JOIN gyms g ON m.sender_type = 'gym' AND m.sender_id = g.id
                LEFT JOIN coaches c ON m.sender_type = 'coach' AND m.sender_id = c.id
                LEFT JOIN members mem ON m.sender_type = 'member' AND m.sender_id = mem.id
                WHERE (
                    (m.sender_id = %s AND m.sender_type = %s AND m.receiver_id = %s AND m.receiver_type = %s)
                    OR 
                    (m.sender_id = %s AND m.sender_type = %s AND m.receiver_id = %s AND m.receiver_type = %s)
                )
                ORDER BY m.created_at ASC
            """, (
                user["id"], user["user_type"], sender_id, sender_type,
                sender_id, sender_type, user["id"], user["user_type"]
            ))
        else:
            # Get all conversations
            cursor.execute("""
                SELECT DISTINCT
                    CASE 
                        WHEN m.sender_id = %s THEN m.receiver_id
                        ELSE m.sender_id
                    END as conversation_id,
                    CASE 
                        WHEN m.sender_id = %s THEN m.receiver_type
                        ELSE m.sender_type
                    END as conversation_type,
                    CASE 
                        WHEN m.sender_id = %s THEN 
                            CASE 
                                WHEN m.receiver_type = 'gym' THEN g.name
                                WHEN m.receiver_type = 'coach' THEN c.name
                                WHEN m.receiver_type = 'member' THEN mem.name
                            END
                        ELSE 
                            CASE 
                                WHEN m.sender_type = 'gym' THEN g.name
                                WHEN m.sender_type = 'coach' THEN c.name
                                WHEN m.sender_type = 'member' THEN mem.name
                            END
                    END as conversation_name,
                    MAX(m.created_at) as last_message_time,
                    COUNT(CASE WHEN m.is_read = FALSE AND m.receiver_id = %s THEN 1 END) as unread_count
                FROM messages m
                LEFT JOIN gyms g ON (
                    (m.sender_type = 'gym' AND m.sender_id = g.id) OR 
                    (m.receiver_type = 'gym' AND m.receiver_id = g.id)
                )
                LEFT JOIN coaches c ON (
                    (m.sender_type = 'coach' AND m.sender_id = c.id) OR 
                    (m.receiver_type = 'coach' AND m.receiver_id = c.id)
                )
                LEFT JOIN members mem ON (
                    (m.sender_type = 'member' AND m.sender_id = mem.id) OR 
                    (m.receiver_type = 'member' AND m.receiver_id = mem.id)
                )
                WHERE m.sender_id = %s OR m.receiver_id = %s
                GROUP BY conversation_id, conversation_type, conversation_name
                ORDER BY last_message_time DESC
            """, (user["id"], user["id"], user["id"], user["id"], user["id"], user["id"]))
        
        results = cursor.fetchall()
        
        if conversation_id:
            # Format individual messages
            formatted_messages = []
            for message in results:
                formatted_messages.append({
                    "id": message["id"],
                    "sender": {
                        "id": message["sender_id"],
                        "type": message["sender_type"],
                        "name": message["sender_name"]
                    },
                    "message": message["message"],
                    "is_read": bool(message["is_read"]),
                    "created_at": message["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                })
            return formatted_messages
        else:
            # Format conversations
            formatted_conversations = []
            for conv in results:
                formatted_conversations.append({
                    "id": f"{conv['conversation_id']}_{conv['conversation_type']}",
                    "name": conv["conversation_name"],
                    "type": conv["conversation_type"],
                    "last_message_time": conv["last_message_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "unread_count": conv["unread_count"]
                })
            return formatted_conversations
        
    except Exception as e:
        print(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.put("/api/messages/{message_id}/read")
async def mark_message_read(message_id: int, request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify message belongs to user
        cursor.execute("""
            SELECT 1 FROM messages 
            WHERE id = %s AND receiver_id = %s AND receiver_type = %s
        """, (message_id, user["id"], user["user_type"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Mark as read
        cursor.execute("""
            UPDATE messages 
            SET is_read = TRUE 
            WHERE id = %s
        """, (message_id,))
        
        conn.commit()
        return {"message": "Message marked as read"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error marking message as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/messages/contacts")
async def get_message_contacts(request: Request):
    # Get user from session
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        contacts = []
        
        if user["user_type"] == "gym":
            # Gym can message all coaches and members
            cursor.execute("""
                SELECT id, name, 'coach' as type 
                FROM coaches 
                WHERE gym_id = %s
            """, (user["id"],))
            coaches = cursor.fetchall()
            contacts.extend(coaches)
            
            cursor.execute("""
                SELECT id, name, 'member' as type 
                FROM members 
                WHERE gym_id = %s
            """, (user["id"],))
            members = cursor.fetchall()
            contacts.extend(members)
            
        elif user["user_type"] == "coach":
            # Coach can message their gym and their members
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type 
                FROM gyms g
                JOIN coaches c ON c.gym_id = g.id
                WHERE c.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                contacts.append(gym)
            
            cursor.execute("""
                SELECT m.id, m.name, 'member' as type 
                FROM members m
                JOIN member_coach mc ON mc.member_id = m.id
                WHERE mc.coach_id = %s
            """, (user["id"],))
            members = cursor.fetchall()
            contacts.extend(members)
            
        elif user["user_type"] == "member":
            # Member can message their gym and their coach
            cursor.execute("""
                SELECT g.id, g.name, 'gym' as type 
                FROM gyms g
                JOIN members m ON m.gym_id = g.id
                WHERE m.id = %s
            """, (user["id"],))
            gym = cursor.fetchone()
            if gym:
                contacts.append(gym)
            
            cursor.execute("""
                SELECT c.id, c.name, 'coach' as type 
                FROM coaches c
                JOIN member_coach mc ON mc.coach_id = c.id
                WHERE mc.member_id = %s
            """, (user["id"],))
            coach = cursor.fetchone()
            if coach:
                contacts.append(coach)
        
        return contacts
        
    except Exception as e:
        print(f"Error getting message contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/gym/messages", response_class=HTMLResponse)
async def get_gym_messages_page(request: Request):
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
        
        # Return the messages page template with gym details
        return templates.TemplateResponse(
            "messaging.html",
            {
                "request": request,
                "user": user,
                "user_type": "gym",
                "user_details": gym_details
            }
        )
    except Exception as e:
        print(f"Error getting gym messages page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/messages", response_class=HTMLResponse)
async def get_coach_messages_page(request: Request):
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
        
        # Return the messages page template with coach details
        return templates.TemplateResponse(
            "messaging.html",
            {
                "request": request,
                "user": user,
                "user_type": "coach",
                "user_details": coach_details
            }
        )
    except Exception as e:
        print(f"Error getting coach messages page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/member/messages", response_class=HTMLResponse)
async def get_member_messages_page(request: Request):
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
        
        # Return the messages page template with member details
        return templates.TemplateResponse(
            "messaging.html",
            {
                "request": request,
                "user": user,
                "user_type": "member",
                "user_details": member_details
            }
        )
    except Exception as e:
        print(f"Error getting member messages page: {str(e)}")
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
        # Get coach details with gym info
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 