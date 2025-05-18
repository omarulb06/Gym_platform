from fastapi import FastAPI, HTTPException, Request
import pymysql
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

app = FastAPI(title="Gym Management Platform")

# Add CORS middleware with more specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # NiceGUI's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

# Initialize database on startup
init_db()

@app.post("/api/login")
async def login(request: Request):
    try:
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        
        # For demo purposes, hardcoded admin
        if email == "admin@fitnessfirst.com" and password == "admin123":
            return JSONResponse(content={
                "user_type": "admin",
                "name": "Admin",
                "email": email,
                "id": 1
            })
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:
            # Check in coaches table
            cursor.execute("SELECT * FROM coaches WHERE email = %s AND password = %s", (email, password))
            coach = cursor.fetchone()
            if coach:
                return JSONResponse(content={
                    "user_type": "coach",
                    "name": coach['name'],
                    "email": coach['email'],
                    "id": coach['id'],
                    "gym_id": coach['gym_id'],
                    "specialization": coach.get('specialization', '')
                })
            
            # Check in members table
            cursor.execute("SELECT * FROM members WHERE email = %s AND password = %s", (email, password))
            member = cursor.fetchone()
            if member:
                return JSONResponse(content={
                    "user_type": "member",
                    "name": member['name'],
                    "email": member['email'],
                    "id": member['id'],
                    "gym_id": member['gym_id'],
                    "membership_type": member.get('membership_type', 'Basic')
                })
            
            # Check in gyms table
            cursor.execute("SELECT * FROM gyms WHERE email = %s AND password = %s", (email, password))
            gym = cursor.fetchone()
            if gym:
                return JSONResponse(content={
                    "user_type": "gym",
                    "name": gym['name'],
                    "email": gym['email'],
                    "id": gym['id']
                })
            
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

@app.get("/api/coach/{coach_id}/members")
async def get_coach_members(coach_id: int):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT m.* 
            FROM members m 
            JOIN member_coach mc ON m.id = mc.member_id 
            WHERE mc.coach_id = %s
        """, (coach_id,))
        
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