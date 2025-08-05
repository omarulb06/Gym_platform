import os
import pymysql

# Database connection
def get_db_connection():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "omaromar"),
        database=os.environ.get("DB_NAME", "trainer_app"),
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