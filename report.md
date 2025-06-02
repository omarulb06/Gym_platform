# Gym Management Platform - Project Report

## Overview
The Gym Management Platform is a comprehensive web application designed to streamline the management of gym operations, including member management, coach assignments, session scheduling, and payment tracking. The platform serves multiple user roles: gym administrators, coaches, and members, each with specific functionalities and access levels.

## Database Structure

### Core Tables

1. **Gyms**
   - Primary table for gym information
   - Fields: id, name, email, password, address, phone, created_at
   - Acts as the parent entity for all other tables

2. **Coaches**
   - Stores coach information
   - Fields: id, gym_id (FK), name, email, password, specialization, status, created_at
   - Linked to gyms through gym_id
   - Can be assigned to multiple members

3. **Members**
   - Stores member information
   - Fields: id, gym_id (FK), name, email, password, membership_type, join_date, created_at
   - Linked to gyms through gym_id
   - Can be assigned to one coach

4. **Member_Coach**
   - Junction table for many-to-many relationship between members and coaches
   - Fields: id, member_id (FK), coach_id (FK), assigned_date
   - Manages the assignment of members to coaches

5. **Sessions**
   - Stores training session information
   - Fields: id, gym_id (FK), coach_id (FK), member_id (FK), session_date, session_time, duration, status, notes, created_at
   - Links gyms, coaches, and members together
   - Tracks session status (Scheduled, Completed, Cancelled)

6. **Payments**
   - Manages financial transactions
   - Fields: id, member_id (FK), gym_id (FK), amount, payment_date, payment_type, status, notes
   - Tracks both membership and session payments

## Database Relationships

1. **Gym to Coaches**
   - One-to-Many relationship
   - A gym can have multiple coaches
   - Each coach belongs to one gym

2. **Gym to Members**
   - One-to-Many relationship
   - A gym can have multiple members
   - Each member belongs to one gym

3. **Coach to Members**
   - Many-to-Many relationship through member_coach table
   - A coach can train multiple members
   - A member can be assigned to one coach

4. **Sessions Relationships**
   - Links gyms, coaches, and members
   - Each session belongs to one gym, one coach, and one member
   - Tracks the complete training session lifecycle

## Key Features

### 1. User Authentication
- Role-based authentication (Gym, Coach, Member)
- Secure session management
- Password protection

### 2. Gym Management
- Member registration and management
- Coach management and assignment
- Session scheduling
- Payment tracking
- Dashboard with key metrics

### 3. Coach Features
- View assigned members
- Schedule training sessions
- Track member progress
- Manage session status
- View personal schedule

### 4. Member Features
- View assigned coach
- View training schedule
- Track session history
- View membership status
- Access workout information

### 5. Session Management
- Create and schedule sessions
- Track session status
- Record workout details
- Handle session conflicts
- Manage session payments

### 6. Payment System
- Track membership payments
- Handle session payments
- Different pricing tiers based on membership type
- Payment status tracking

## Technical Implementation

### Backend
- FastAPI framework for API development
- MySQL database for data storage
- JWT-based authentication
- RESTful API endpoints

### Security Features
- Password hashing
- Session management
- Role-based access control
- Input validation
- SQL injection prevention

### Data Validation
- Email format validation
- Password strength requirements
- Membership type validation
- Session conflict checking
- Payment validation

## Membership Types and Pricing

1. **Basic Membership**
   - Base price: $50/month
   - Standard session price: $25

2. **Premium Membership**
   - Base price: $100/month
   - Discounted session price: $20 (20% discount)

3. **VIP Membership**
   - Base price: $200/month
   - Discounted session price: $15 (40% discount)

## Future Enhancements

1. **Additional Features**
   - Workout progress tracking
   - Nutrition planning
   - Equipment management
   - Class scheduling
   - Online booking system

2. **Technical Improvements**
   - Real-time notifications
   - Mobile app integration
   - Advanced analytics
   - Payment gateway integration
   - Automated reporting

## Conclusion
The Gym Management Platform provides a robust solution for gym management, offering comprehensive features for gym administrators, coaches, and members. The system's modular design and clear database relationships ensure scalability and maintainability. The platform successfully addresses the core needs of gym management while providing a foundation for future enhancements. 