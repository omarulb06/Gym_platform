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
    current_user: dict = Depends(get_current_user)
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
                   SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                   MAX(CASE WHEN s.status = 'completed' THEN s.session_date ELSE NULL END) as last_session
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
    current_user: dict = Depends(get_current_user)
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
    current_user: dict = Depends(get_current_user)
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
    current_user: dict = Depends(get_current_user)
):
    # Redirect to the member-specific endpoint with member_id=0 (all members)
    return await get_member_progress(0, time_range, current_user)

@app.get("/api/coach/progress/{member_id}")
async def get_member_progress(
    member_id: int,
    time_range: str = "month",
    current_user: dict = Depends(get_current_user)
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
                    -- Calculate membership revenue only
                    SELECT COALESCE(SUM(
                        CASE 
                            WHEN m.membership_type = 'Basic' THEN 50.00
                            WHEN m.membership_type = 'Premium' THEN 100.00
                            WHEN m.membership_type = 'VIP' THEN 200.00
                        END
                    ), 0)
                    FROM members m
                    WHERE m.gym_id = %s
                    AND m.join_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
                    AND m.join_date < DATE_ADD(DATE_FORMAT(CURDATE(), '%%Y-%%m-01'), INTERVAL 1 MONTH)
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
                        workout_type = lines[0].replace(' Workout:', '')
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
                        notes = f"{workout_type} Workout:\n"
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
        
        # Validate required fields
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
async def get_coach_member_details(member_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get member details with verification that they belong to the coach
        cursor.execute("""
            SELECT 
                m.*,
                mc.assigned_date,
                COUNT(s.id) as total_sessions,
                SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                MAX(CASE WHEN s.status = 'completed' THEN s.session_date ELSE NULL END) as last_session
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
        """, (member_id, current_user["id"]))
        recent_sessions = cursor.fetchall()
        
        # Format recent sessions
        formatted_sessions = []
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
                "notes": session["notes"]
            })
        
        cursor.close()
        conn.close()
        
        return {
            "member": {
                "id": member["id"],
                "name": member["name"],
                "email": member["email"],
                "membership_type": member["membership_type"],
                "join_date": member["join_date"].strftime("%Y-%m-%d") if member["join_date"] else None,
                "assigned_date": member["assigned_date"].strftime("%Y-%m-%d") if member["assigned_date"] else None,
                "total_sessions": member["total_sessions"] or 0,
                "completed_sessions": member["completed_sessions"] or 0,
                "last_session": member["last_session"].strftime("%Y-%m-%d") if member["last_session"] else None
            },
            "recent_sessions": formatted_sessions
        }
    except Exception as e:
        print(f"Error in get_coach_member_details: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving member details")

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

@app.get("/api/coach/members/")
async def get_coach_members_root(current_user: dict = Depends(get_current_user)):
    # Redirect to the main members endpoint
    return RedirectResponse(url="/api/coach/members")

@app.post("/api/coach/sessions")
async def create_coach_session(
    request: Request,
    current_user: dict = Depends(get_current_user)
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
    current_user: dict = Depends(get_current_user)
):
    if current_user["user_type"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query
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
        
        cursor.close()
        conn.close()
        
        return JSONResponse(content=formatted_sessions)
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
    current_user: dict = Depends(get_current_user)
):
    if current_user["user_type"] != "member":
        raise HTTPException(status_code=403, detail="Only members can access this endpoint")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Base query
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
        
        cursor.close()
        conn.close()
        
        return formatted_sessions
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

@app.get("/api/member/progress")
async def get_member_progress_data(current_user: dict = Depends(get_current_user)):
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
        
        # Get revenue statistics
        cursor.execute("""
            SELECT 
                SUM(CASE 
                    WHEN membership_type = 'Basic' THEN 50.00
                    WHEN membership_type = 'Premium' THEN 100.00
                    WHEN membership_type = 'VIP' THEN 200.00
                END) as monthly_revenue
            FROM members 
            WHERE gym_id = %s
            AND join_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
            AND join_date < DATE_ADD(DATE_FORMAT(CURDATE(), '%%Y-%%m-01'), INTERVAL 1 MONTH)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 