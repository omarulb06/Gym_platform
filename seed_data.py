import pymysql
import json
from datetime import datetime

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="omaromar",
        database="trainer_app",
        cursorclass=pymysql.cursors.DictCursor
    )

def clear_database(cursor):
    # Delete data from tables in reverse order of dependencies
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM members")
    cursor.execute("DELETE FROM coaches")
    cursor.execute("DELETE FROM gyms")
    print("Database cleared successfully")

def seed_database():
    # Connect to MySQL
    connection = pymysql.connect(
        host="localhost",
        user="root",
        password="omaromar",
        database="trainer_app",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    cursor = connection.cursor()
    
    try:
        # Clear existing data
        clear_database(cursor)
        
        # Insert gyms
        cursor.execute("""
            INSERT INTO gyms (name, contact_info, availability, password) 
            VALUES (%s, %s, %s, %s)
        """, (
            "Fitness First",
            json.dumps({
                "phone": "03-1234567",
                "email": "info@fitnessfirst.com",
                "address": "123 Main St, Tel Aviv"
            }),
            json.dumps({
                "weekdays": {"start": "06:00", "end": "22:00"},
                "weekends": {"start": "08:00", "end": "16:00"}
            }),
            "gym123"  # Default password for gym
        ))
        
        # Insert coaches
        coaches = [
            {
                "name": "David Cohen",
                "email": "david@fitnessfirst.com",
                "phone": "050-1234567",
                "availability": {
                    "weekdays": {"start": "08:00", "end": "20:00"},
                    "weekends": {"start": "09:00", "end": "15:00"}
                },
                "password": "coach123"
            },
            {
                "name": "Sarah Levi",
                "email": "sarah@fitnessfirst.com",
                "phone": "050-2345678",
                "availability": {
                    "weekdays": {"start": "07:00", "end": "19:00"},
                    "weekends": {"start": "08:00", "end": "14:00"}
                },
                "password": "coach456"
            },
            {
                "name": "Michael Brown",
                "email": "michael@fitnessfirst.com",
                "phone": "050-3456789",
                "availability": {
                    "weekdays": {"start": "09:00", "end": "21:00"},
                    "weekends": {"start": "10:00", "end": "16:00"}
                },
                "password": "coach789"
            }
        ]
        
        for coach in coaches:
            cursor.execute("""
                INSERT INTO coaches (name, email, phone, availability, password) 
                VALUES (%s, %s, %s, %s, %s)
            """, (
                coach["name"],
                coach["email"],
                coach["phone"],
                json.dumps(coach["availability"]),
                coach["password"]
            ))
        
        # Insert members
        members = [
            {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "050-4567890",
                "coach_id": 1,
                "availability": {
                    "weekdays": {"start": "17:00", "end": "20:00"},
                    "weekends": {"start": "10:00", "end": "14:00"}
                },
                "password": "member123"
            },
            {
                "name": "Mary Johnson",
                "email": "mary@example.com",
                "phone": "050-5678901",
                "coach_id": 2,
                "availability": {
                    "weekdays": {"start": "18:00", "end": "21:00"},
                    "weekends": {"start": "11:00", "end": "15:00"}
                },
                "password": "member456"
            },
            {
                "name": "Rachel Green",
                "email": "rachel@example.com",
                "phone": "050-6789012",
                "coach_id": 1,
                "availability": {
                    "weekdays": {"start": "16:00", "end": "19:00"},
                    "weekends": {"start": "09:00", "end": "13:00"}
                },
                "password": "member789"
            },
            {
                "name": "Tom Wilson",
                "email": "tom@example.com",
                "phone": "050-7890123",
                "coach_id": 3,
                "availability": {
                    "weekdays": {"start": "19:00", "end": "21:00"},
                    "weekends": {"start": "12:00", "end": "16:00"}
                },
                "password": "member101"
            }
        ]
        
        for member in members:
            cursor.execute("""
                INSERT INTO members (name, email, phone, coach_id, availability, password) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                member["name"],
                member["email"],
                member["phone"],
                member["coach_id"],
                json.dumps(member["availability"]),
                member["password"]
            ))
        
        # Insert sessions
        sessions = [
            {
                "name": "Morning Strength Training",
                "coach_id": 1,
                "start_time": "08:00",
                "end_time": "09:00",
                "day": "Monday",
                "status": "scheduled",
                "details": "Focus on upper body strength",
                "member_ids": [1, 3]
            },
            {
                "name": "Evening Cardio",
                "coach_id": 2,
                "start_time": "18:00",
                "end_time": "19:00",
                "day": "Wednesday",
                "status": "scheduled",
                "details": "High-intensity cardio workout",
                "member_ids": [2, 4]
            },
            {
                "name": "Evening Strength",
                "coach_id": 3,
                "start_time": "19:00",
                "end_time": "20:00",
                "day": "Tuesday",
                "status": "scheduled",
                "details": "Full body strength training",
                "member_ids": [1, 2]
            },
            {
                "name": "Weekend Workout",
                "coach_id": 1,
                "start_time": "10:00",
                "end_time": "11:00",
                "day": "Saturday",
                "status": "scheduled",
                "details": "Mixed cardio and strength",
                "member_ids": [3, 4]
            }
        ]
        
        for session in sessions:
            cursor.execute("""
                INSERT INTO sessions (name, coach_id, start_time, end_time, day, status, details, member_ids) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session["name"],
                session["coach_id"],
                session["start_time"],
                session["end_time"],
                session["day"],
                session["status"],
                session["details"],
                json.dumps(session["member_ids"])
            ))
        
        # Update JSON arrays in gyms table
        cursor.execute("""
            UPDATE gyms 
            SET coaches = %s, members = %s 
            WHERE name = 'Fitness First'
        """, (
            json.dumps([1, 2, 3]),  # All coach IDs
            json.dumps([1, 2, 3, 4])  # All member IDs
        ))
        
        # Update JSON arrays in coaches table
        for coach_id in [1, 2, 3]:
            member_ids = [m["coach_id"] == coach_id for m in members]
            cursor.execute("""
                UPDATE coaches 
                SET members = %s 
                WHERE id = %s
            """, (json.dumps(member_ids), coach_id))
        
        # Update JSON arrays in members table
        for member_id in [1, 2, 3, 4]:
            session_ids = [s["member_ids"] for s in sessions if member_id in s["member_ids"]]
            cursor.execute("""
                UPDATE members 
                SET sessions = %s 
                WHERE id = %s
            """, (json.dumps(session_ids), member_id))
        
        connection.commit()
        print("Database seeded successfully!")
        
    except Exception as e:
        print(f"Error seeding database: {str(e)}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    seed_database() 