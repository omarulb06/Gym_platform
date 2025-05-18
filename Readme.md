# Gym Management Platform

## Project Overview

The Gym Management Platform is a comprehensive web-based solution designed to streamline the interaction between gym customers and personal trainers. The platform facilitates session scheduling, program management, and optimal time slot allocation for training sessions.

## Core Features

### User Management
- **Customer Portal**
  - Account creation and profile management
  - Session booking and scheduling
  - Program tracking and progress monitoring
  - Preference settings for training times

- **Trainer Portal**
  - Profile and availability management
  - Session scheduling and management
  - Program creation and customization
  - Client progress tracking

- **Admin Portal**
  - Gym and trainer management
  - User oversight and system administration
  - Analytics and reporting

### Key Functionalities
- Smart scheduling system with conflict resolution
- Personalized training program creation
- Real-time availability tracking
- Automated session reminders
- Multi-gym support for trainers

## Database Structure

### Users Table
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    user_type ENUM('customer', 'trainer', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Gyms Table
```sql
CREATE TABLE gyms (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(255) NOT NULL,
    contact_number VARCHAR(20),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Trainer_Gym_Association Table
```sql
CREATE TABLE trainer_gym_association (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trainer_id INT NOT NULL,
    gym_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (trainer_id) REFERENCES users(id),
    FOREIGN KEY (gym_id) REFERENCES gyms(id)
);
```

### Trainer_Profiles Table
```sql
CREATE TABLE trainer_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    specialty VARCHAR(100),
    certification TEXT,
    experience_years INT,
    hourly_rate DECIMAL(10,2),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Customer_Profiles Table
```sql
CREATE TABLE customer_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    fitness_goals TEXT,
    medical_conditions TEXT,
    preferred_training_times JSON,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Sessions Table
```sql
CREATE TABLE sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trainer_id INT NOT NULL,
    customer_id INT NOT NULL,
    gym_id INT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status ENUM('scheduled', 'completed', 'cancelled') DEFAULT 'scheduled',
    session_type ENUM('one-on-one', 'group') DEFAULT 'one-on-one',
    notes TEXT,
    FOREIGN KEY (trainer_id) REFERENCES users(id),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (gym_id) REFERENCES gyms(id)
);
```

### Training_Programs Table
```sql
CREATE TABLE training_programs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trainer_id INT NOT NULL,
    customer_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
    FOREIGN KEY (trainer_id) REFERENCES users(id),
    FOREIGN KEY (customer_id) REFERENCES users(id)
);
```

### Program_Exercises Table
```sql
CREATE TABLE program_exercises (
    id INT PRIMARY KEY AUTO_INCREMENT,
    program_id INT NOT NULL,
    exercise_name VARCHAR(100) NOT NULL,
    sets INT,
    reps INT,
    duration INT,
    notes TEXT,
    FOREIGN KEY (program_id) REFERENCES training_programs(id)
);
```

## Technical Stack

### Frontend
- NiceGUI for modern, responsive web interface
- Built-in components and styling
- Real-time updates and interactive elements
- Easy integration with Python backend

### Backend
- Python Flask framework
- RESTful API architecture
- JWT authentication

### Database
- MySQL for data persistence
- SQLAlchemy ORM for database operations

## Getting Started

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   npm install
   ```
3. Set up the database:
   ```bash
   python seed_data.py
   ```
4. Run the development server:
   ```bash
   python app.py
   npm start
   ```
