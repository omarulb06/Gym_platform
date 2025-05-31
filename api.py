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

def get_current_user(request: Request) -> Optional[dict]:
    session_id = request.cookies.get("session_id")
    return active_sessions.get(session_id)

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
                
                if (response.ok) {
                    window.location.href = '/dashboard';
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
                    response = JSONResponse(content=user_data)
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
                    response = JSONResponse(content=user_data)
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
                    response = JSONResponse(content=user_data)
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
async def get_coach_members(request: Request):
    try:
        # Get user from session using our existing session management
        user = get_current_user(request)
        if not user or user["user_type"] != "coach":
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        print(f"Getting members for coach ID: {user['id']}")  # Debug log
        
        # Get members associated with the coach
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # First, get the coach's gym_id
            cursor.execute("SELECT gym_id FROM coaches WHERE id = %s", (user["id"],))
            coach = cursor.fetchone()
            if not coach:
                raise HTTPException(status_code=404, detail="Coach not found")
            
            print(f"Coach's gym_id: {coach['gym_id']}")  # Debug log
            
            # Then get all members from that gym
            cursor.execute("""
                SELECT m.*, 
                       COUNT(s.id) as total_sessions,
                       'active' as status
                FROM members m
                LEFT JOIN sessions s ON m.id = s.member_id AND s.coach_id = %s
                WHERE m.gym_id = %s
                GROUP BY m.id
            """, (user["id"], coach["gym_id"]))
            
            members = cursor.fetchall()
            print(f"Found {len(members)} members")  # Debug log
            
            return members
        except Exception as e:
            print(f"Database error: {str(e)}")  # Debug log
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Gym endpoints
@app.get("/api/gym/{gym_id}/coaches")
async def get_gym_coaches(gym_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT c.*, 
                   COUNT(DISTINCT mc.member_id) as assigned_members,
                   COUNT(DISTINCT s.id) as total_sessions
            FROM coaches c
            LEFT JOIN member_coach mc ON c.id = mc.coach_id
            LEFT JOIN sessions s ON c.id = s.coach_id
            WHERE c.gym_id = %s
            GROUP BY c.id
        """, (gym_id,))
        coaches = cursor.fetchall()
        return JSONResponse(content=coaches)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/gym/{gym_id}/members")
async def get_gym_members(gym_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT m.*, 
                   c.name as coach_name,
                   COUNT(DISTINCT s.id) as total_sessions
            FROM members m
            LEFT JOIN member_coach mc ON m.id = mc.member_id
            LEFT JOIN coaches c ON mc.coach_id = c.id
            LEFT JOIN sessions s ON m.id = s.member_id
            WHERE m.gym_id = %s
            GROUP BY m.id
        """, (gym_id,))
        members = cursor.fetchall()
        return JSONResponse(content=members)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/gym/{gym_id}/sessions")
async def get_gym_sessions(gym_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT s.*, c.name as coach_name, m.name as member_name
            FROM sessions s
            JOIN coaches c ON s.coach_id = c.id
            JOIN members m ON s.member_id = m.id
            WHERE s.gym_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
        """, (gym_id,))
        
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

# Session management endpoints
@app.post("/api/sessions")
async def create_session(request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO sessions (gym_id, coach_id, member_id, session_date, session_time, duration, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['gym_id'],
            data['coach_id'],
            data['member_id'],
            data['session_date'],
            data['session_time'],
            data['duration'],
            data.get('notes', '')
        ))
        
        connection.commit()
        return JSONResponse(content={"detail": "Session created successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.put("/api/sessions/{session_id}")
async def update_session(session_id: int, request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE sessions 
            SET status = %s, notes = %s
            WHERE id = %s
        """, (data['status'], data.get('notes', ''), session_id))
        
        connection.commit()
        return JSONResponse(content={"detail": "Session updated successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

# Member-Coach relationship endpoints
@app.post("/api/member-coach")
async def assign_coach_to_member(request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO member_coach (member_id, coach_id)
            VALUES (%s, %s)
        """, (data['member_id'], data['coach_id']))
        
        connection.commit()
        return JSONResponse(content={"detail": "Coach assigned successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.delete("/api/member-coach/{member_id}/{coach_id}")
async def remove_coach_from_member(member_id: int, coach_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            DELETE FROM member_coach
            WHERE member_id = %s AND coach_id = %s
        """, (member_id, coach_id))
        
        connection.commit()
        return JSONResponse(content={"detail": "Coach removed successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.post("/api/gym/{gym_id}/coach")
async def add_coach(gym_id: int, request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO coaches (gym_id, name, email, password, specialization, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            gym_id,
            data['name'],
            data['email'],
            data['password'],
            data.get('specialization', ''),
            data.get('status', 'Active')
        ))
        
        connection.commit()
        return JSONResponse(content={"detail": "Coach added successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.post("/api/gym/{gym_id}/member")
async def add_member(gym_id: int, request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO members (gym_id, name, email, password, membership_type)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            gym_id,
            data['name'],
            data['email'],
            data['password'],
            data.get('membership_type', 'Basic')
        ))
        
        connection.commit()
        return JSONResponse(content={"detail": "Member added successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.post("/api/gym/{gym_id}/assign-coach")
async def assign_coach_to_member(gym_id: int, request: Request):
    try:
        data = await request.json()
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify that both coach and member belong to the gym
        cursor.execute("""
            SELECT 1 FROM coaches WHERE id = %s AND gym_id = %s
        """, (data['coach_id'], gym_id))
        if not cursor.fetchone():
            return JSONResponse(
                status_code=400,
                content={"detail": "Coach does not belong to this gym"}
            )
        
        cursor.execute("""
            SELECT 1 FROM members WHERE id = %s AND gym_id = %s
        """, (data['member_id'], gym_id))
        if not cursor.fetchone():
            return JSONResponse(
                status_code=400,
                content={"detail": "Member does not belong to this gym"}
            )
        
        # Assign coach to member
        cursor.execute("""
            INSERT INTO member_coach (member_id, coach_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE coach_id = VALUES(coach_id)
        """, (data['member_id'], data['coach_id']))
        
        connection.commit()
        return JSONResponse(content={"detail": "Coach assigned successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/")
    
    # Get role-specific data
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        if user["user_type"] == "admin":
            # Get overall statistics for admin
            cursor.execute("SELECT COUNT(*) as count FROM gyms")
            total_gyms = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM coaches")
            total_coaches = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM members")
            total_members = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            total_sessions = cursor.fetchone()['count']
            
            stats = {
                "total_gyms": total_gyms,
                "total_coaches": total_coaches,
                "total_members": total_members,
                "total_sessions": total_sessions
            }
            
        elif user["user_type"] == "gym":
            # Get gym-specific statistics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT c.id) as total_coaches,
                    COUNT(DISTINCT m.id) as total_members,
                    COUNT(DISTINCT s.id) as total_sessions
                FROM gyms g
                LEFT JOIN coaches c ON g.id = c.gym_id
                LEFT JOIN members m ON g.id = m.gym_id
                LEFT JOIN sessions s ON g.id = s.gym_id
                WHERE g.id = %s
            """, (user["id"],))
            stats = cursor.fetchone()
            
        elif user["user_type"] == "coach":
            # Get coach-specific statistics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT mc.member_id) as total_members,
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(DISTINCT CASE WHEN s.status = 'Scheduled' THEN s.id END) as upcoming_sessions
                FROM coaches c
                LEFT JOIN member_coach mc ON c.id = mc.coach_id
                LEFT JOIN sessions s ON c.id = s.coach_id
                WHERE c.id = %s
            """, (user["id"],))
            stats = cursor.fetchone()
            
        elif user["user_type"] == "member":
            # Get member-specific statistics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(DISTINCT CASE WHEN s.status = 'Scheduled' THEN s.id END) as upcoming_sessions,
                    m.membership_type
                FROM members m
                LEFT JOIN sessions s ON m.id = s.member_id
                WHERE m.id = %s
                GROUP BY m.membership_type
            """, (user["id"],))
            stats = cursor.fetchone()
        
        # Return the coach dashboard template with stats
        return templates.TemplateResponse(
            "coach/dashboard.html",
            {"request": request, "stats": stats}
        )
        
    except Exception as e:
        print(f"Error getting dashboard data: {str(e)}")
        return HTMLResponse(content="Error loading dashboard")
    finally:
        cursor.close()
        connection.close()

@app.get("/api/create-test-coach")
async def create_test_coach_get():
    return await create_test_coach()

@app.post("/api/create-test-coach")
async def create_test_coach():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First create a test gym if it doesn't exist
        cursor.execute("""
            INSERT INTO gyms (name, email, password, address, phone)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
        """, (
            "Test Gym",
            "testgym@example.com",
            "gym123",
            "123 Test Street",
            "123-456-7890"
        ))
        
        gym_id = cursor.lastrowid or cursor.execute("SELECT id FROM gyms WHERE email = 'testgym@example.com'").fetchone()['id']
        
        # Create test coach
        cursor.execute("""
            INSERT INTO coaches (gym_id, name, email, password, specialization, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
        """, (
            gym_id,
            "Test Coach",
            "testcoach@example.com",
            "coach123",
            "Fitness Training",
            "Active"
        ))
        
        connection.commit()
        return JSONResponse(content={"detail": "Test coach created successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/check-test-coach")
async def check_test_coach():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First check if the gym exists
        cursor.execute("SELECT * FROM gyms WHERE email = %s", ("testgym@example.com",))
        gym = cursor.fetchone()
        
        # Then check if the coach exists
        cursor.execute("SELECT * FROM coaches WHERE email = %s", ("testcoach@example.com",))
        coach = cursor.fetchone()
        
        return JSONResponse(content={
            "gym_exists": bool(gym),
            "coach_exists": bool(coach),
            "gym_data": gym if gym else None,
            "coach_data": coach if coach else None
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/api/reset-db")
async def reset_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Drop existing tables
        cursor.execute("DROP TABLE IF EXISTS member_coach")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        cursor.execute("DROP TABLE IF EXISTS members")
        cursor.execute("DROP TABLE IF EXISTS coaches")
        cursor.execute("DROP TABLE IF EXISTS gyms")
        
        connection.commit()
        
        # Reinitialize database
        init_db()
        
        return JSONResponse(content={"detail": "Database reset successfully"})
    except Exception as e:
        connection.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        cursor.close()
        connection.close()

@app.get("/coach/members", response_class=HTMLResponse)
async def get_coach_members_page(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Return the members page template
    return templates.TemplateResponse(
        "coach/members.html",
        {"request": request}
    )

@app.get("/coach/schedule/today")
async def get_coach_schedule_today(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get today's schedule
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT s.*, m.name as member_name
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.coach_id = %s
            AND DATE(s.session_date) = CURDATE()
            ORDER BY s.session_time
        """, (user["id"],))
        
        schedule = cursor.fetchall()
        
        # Format the schedule data
        formatted_schedule = []
        for session in schedule:
            formatted_schedule.append({
                "id": session["id"],
                "member_name": session["member_name"],
                "session_type": session["session_type"],
                "session_time": session["session_time"].strftime("%I:%M %p")
            })
        
        return formatted_schedule
    finally:
        cursor.close()
        conn.close()

@app.get("/coach/members/{member_id}", response_class=HTMLResponse)
async def get_member_details_page(member_id: int, request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        return RedirectResponse(url="/")
    
    # Return the member details page template
    return templates.TemplateResponse(
        "coach/member_details.html",
        {"request": request}
    )

@app.get("/coach/members/{member_id}")
async def get_member_details(member_id: int, request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get member details
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify the member belongs to the coach's gym
        cursor.execute("""
            SELECT m.*, 
                   COUNT(s.id) as total_sessions,
                   CASE 
                       WHEN m.membership_end_date >= CURDATE() THEN 'active'
                       ELSE 'inactive'
                   END as status
            FROM members m
            LEFT JOIN sessions s ON m.id = s.member_id AND s.coach_id = %s
            WHERE m.id = %s
            AND m.gym_id = (SELECT gym_id FROM coaches WHERE id = %s)
            GROUP BY m.id
        """, (user["id"], member_id, user["id"]))
        
        member = cursor.fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        # Get member's recent sessions
        cursor.execute("""
            SELECT s.*, m.name as member_name
            FROM sessions s
            JOIN members m ON s.member_id = m.id
            WHERE s.member_id = %s AND s.coach_id = %s
            ORDER BY s.session_date DESC, s.session_time DESC
            LIMIT 5
        """, (member_id, user["id"]))
        
        recent_sessions = cursor.fetchall()
        
        return {
            "member": member,
            "recent_sessions": recent_sessions
        }
    finally:
        cursor.close()
        conn.close()

@app.post("/api/coach/sessions")
async def schedule_session(request: Request):
    # Get user from session using our existing session management
    user = get_current_user(request)
    if not user or user["user_type"] != "coach":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get session data from request
    data = await request.json()
    member_id = data.get("member_id")
    session_date = data.get("session_date")
    session_time = data.get("session_time")
    session_type = data.get("session_type")
    
    if not all([member_id, session_date, session_time, session_type]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Verify the member belongs to the coach's gym
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 1 FROM members m
            WHERE m.id = %s
            AND m.gym_id = (SELECT gym_id FROM coaches WHERE id = %s)
        """, (member_id, user["id"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Member not found or not associated with your gym")
        
        # Check for scheduling conflicts
        cursor.execute("""
            SELECT 1 FROM sessions
            WHERE coach_id = %s
            AND session_date = %s
            AND session_time = %s
        """, (user["id"], session_date, session_time))
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Time slot is already booked")
        
        # Insert the new session
        cursor.execute("""
            INSERT INTO sessions (coach_id, member_id, session_date, session_time, session_type, status)
            VALUES (%s, %s, %s, %s, %s, 'scheduled')
        """, (user["id"], member_id, session_date, session_time, session_type))
        
        conn.commit()
        return {"message": "Session scheduled successfully"}
    finally:
        cursor.close()
        conn.close()

@app.get("/api/create-test-data")
async def create_test_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # First, get a coach to assign members to
            cursor.execute("SELECT id, gym_id FROM coaches WHERE email = 'john@example.com'")
            coach = cursor.fetchone()
            if not coach:
                raise HTTPException(status_code=404, detail="Test coach not found")
            
            # Create test members
            test_members = [
                ("Alice Johnson", "alice@example.com", "member123", "Premium"),
                ("Bob Smith", "bob@example.com", "member123", "Basic"),
                ("Carol White", "carol@example.com", "member123", "VIP"),
                ("David Brown", "david@example.com", "member123", "Premium"),
                ("Eva Davis", "eva@example.com", "member123", "Basic")
            ]
            
            for name, email, password, membership_type in test_members:
                # Insert member
                cursor.execute("""
                    INSERT INTO members (gym_id, name, email, password, membership_type, join_date)
                    VALUES (%s, %s, %s, %s, %s, CURDATE())
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
                """, (coach['gym_id'], name, email, password, membership_type))
                
                member_id = cursor.lastrowid or cursor.execute("SELECT id FROM members WHERE email = %s", (email,)).fetchone()['id']
                
                # Assign member to coach
                cursor.execute("""
                    INSERT INTO member_coach (member_id, coach_id)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE coach_id = VALUES(coach_id)
                """, (member_id, coach['id']))
                
                # Add some sessions
                for i in range(3):  # Add 3 sessions per member
                    session_date = datetime.now().date() + timedelta(days=i*7)
                    session_time = datetime.strptime("10:00", "%H:%M").time()
                    cursor.execute("""
                        INSERT INTO sessions (gym_id, coach_id, member_id, session_date, session_time, duration, status)
                        VALUES (%s, %s, %s, %s, %s, 60, 'Scheduled')
                    """, (coach['gym_id'], coach['id'], member_id, session_date, session_time))
            
            conn.commit()
            return {"message": "Test data created successfully"}
            
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 