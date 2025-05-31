import pymysql
from datetime import datetime, timedelta

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="omaromar",
        database="trainer_app",
        cursorclass=pymysql.cursors.DictCursor
    )

def seed_database():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Create single gym
        gym = {
            'name': 'PowerFit Central',
            'email': 'powerfit@example.com',
            'password': 'gym123',
            'address': '123 Fitness Street',
            'phone': '123-456-7890'
        }
        
        cursor.execute("""
            INSERT INTO gyms (name, email, password, address, phone)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
        """, (
            gym['name'],
            gym['email'],
            gym['password'],
            gym['address'],
            gym['phone']
        ))
        
        # Get gym ID
        cursor.execute("SELECT id FROM gyms WHERE email = 'powerfit@example.com'")
        gym_id = cursor.fetchone()['id']
        
        # Create sample coaches
        coaches = [
            {
                'gym_id': gym_id,
                'name': 'John Trainer',
                'email': 'john@example.com',
                'password': 'coach123',
                'specialization': 'Strength Training',
                'status': 'Active'
            },
            {
                'gym_id': gym_id,
                'name': 'Sarah Wilson',
                'email': 'sarah@example.com',
                'password': 'coach123',
                'specialization': 'Yoga',
                'status': 'Active'
            },
            {
                'gym_id': gym_id,
                'name': 'Mike Johnson',
                'email': 'mike@example.com',
                'password': 'coach123',
                'specialization': 'CrossFit',
                'status': 'Active'
            }
        ]
        
        for coach in coaches:
            cursor.execute("""
                INSERT INTO coaches (gym_id, name, email, password, specialization, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
            """, (
                coach['gym_id'],
                coach['name'],
                coach['email'],
                coach['password'],
                coach['specialization'],
                coach['status']
            ))
        
        # Create sample members
        members = [
            {
                'gym_id': gym_id,
                'name': 'Alice Smith',
                'email': 'alice@example.com',
                'password': 'member123',
                'membership_type': 'Premium'
            },
            {
                'gym_id': gym_id,
                'name': 'Bob Johnson',
                'email': 'bob@example.com',
                'password': 'member123',
                'membership_type': 'Basic'
            },
            {
                'gym_id': gym_id,
                'name': 'Carol White',
                'email': 'carol@example.com',
                'password': 'member123',
                'membership_type': 'VIP'
            }
        ]
        
        for member in members:
            cursor.execute("""
                INSERT INTO members (gym_id, name, email, password, membership_type)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
            """, (
                member['gym_id'],
                member['name'],
                member['email'],
                member['password'],
                member['membership_type']
            ))
        
        # Create some sample sessions
        cursor.execute("SELECT id FROM coaches WHERE email = 'john@example.com'")
        john_id = cursor.fetchone()['id']
        
        cursor.execute("SELECT id FROM members WHERE email = 'alice@example.com'")
        alice_id = cursor.fetchone()['id']
        
        # Create sessions for the next 7 days
        for i in range(7):
            session_date = datetime.now() + timedelta(days=i)
            cursor.execute("""
                INSERT INTO sessions (gym_id, coach_id, member_id, session_date, session_time, duration, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                gym_id,
                john_id,
                alice_id,
                session_date.date(),
                '10:00:00',
                60,
                'Scheduled'
            ))
        
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