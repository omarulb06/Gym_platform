# PowerFit - Gym Management Platform

A modern web-based gym management system that connects gyms, coaches, and members in a seamless platform.

## Features

### For Gyms
- Manage multiple coaches and members
- Track membership types and status
- Monitor session schedules
- View gym statistics and performance metrics

### For Coaches
- Manage assigned members
- Schedule and track training sessions
- View member progress and history
- Access daily schedule and upcoming sessions

### For Members
- View assigned coach information
- Track training sessions and progress
- Manage membership details
- Access session history

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: MySQL
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **Authentication**: Session-based authentication

## Prerequisites

- Python 3.7+
- MySQL Server
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd gym-management-platform
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Set up the MySQL database:
```bash
mysql -u root -p
CREATE DATABASE trainer_app;
```

4. Configure the database connection in `api.py`:
```python
def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="your_username",
        password="your_password",
        database="trainer_app",
        cursorclass=pymysql.cursors.DictCursor
    )
```

## Running the Application

1. Start the FastAPI server:
```bash
python api.py
```

2. Access the application at:
```
http://localhost:8000
```

## Test Data

The application includes endpoints to create test data:

1. Create a test coach:
```
http://localhost:8000/api/create-test-coach
```

2. Create test members and sessions:
```
http://localhost:8000/api/create-test-data
```

## API Endpoints

### Authentication
- `POST /api/login` - User login

### Gym Endpoints
- `GET /api/gym/{gym_id}/coaches` - Get gym coaches
- `GET /api/gym/{gym_id}/members` - Get gym members
- `GET /api/gym/{gym_id}/sessions` - Get gym sessions

### Coach Endpoints
- `GET /api/coach/members` - Get coach's members
- `GET /api/coach/{coach_id}/schedule` - Get coach's schedule
- `POST /api/coach/sessions` - Schedule new session

### Member Endpoints
- `GET /api/member/{member_id}/sessions` - Get member's sessions
- `GET /api/member/{member_id}/coach` - Get member's coach

## Database Schema

The application uses the following main tables:
- `gyms` - Gym information
- `coaches` - Coach details
- `members` - Member information
- `sessions` - Training sessions
- `member_coach` - Member-Coach relationships

