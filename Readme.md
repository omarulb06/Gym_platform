# Gym Management Platform

## Project Overview
The Gym Management Platform simplifies scheduling and managing training sessions for personal trainers, gym managers, and clients. It enables gym managers to manage gyms and trainers, clients to book sessions, and trainers to create personalized programs. The platform includes a scheduling optimization algorithm for efficient session management.

## Objectives
- **Gym Management**: Manage gyms and assign trainers (one-to-many relationship).
- **Trainer Management**: Handle trainer details, gym associations, and clients.
- **Customer Management**: Allow session bookings, memberships, and trainer interactions.
- **Schedule Optimization**: Algorithm-driven scheduling based on availability.
- **Personalized Programs**: Trainers create custom programs for clients.
- **Access Control**: Role-based access (Admin, Manager, Trainer, Customer, Visitor).

## Entities

### Gym
**Attributes**:
- **Gym ID** (Primary Key)
- **Gym Name**
- **Address**
- **Contact Number**
- **Email**
- **Trainers** (linked via relationship)

**Description**:  
A physical location with multiple trainers. Trainers are linked to one gym; clients book sessions at the gym.

---

### Trainer
**Attributes**:
- **Trainer ID** (Primary Key)
- **Name**
- **Email**
- **Phone Number**
- **Associated Gym** (one gym)
- **Clients** (linked via relationship)
- **Schedule** (session availability)

**Description**:  
Trainers create personalized programs and manage schedules. They can work independently or be linked to a gym.

---

### Customer
**Attributes**:
- **Customer ID** (Primary Key)
- **Name**
- **Email**
- **Phone Number**
- **Membership Type** (Gym and/or Trainer)
- **Associated Trainers**
- **Gym Membership** (if applicable)
- **Schedule** (session bookings)

**Description**:  
Customers book sessions with trainers (at a gym or privately). Memberships can be gym-based or trainer-specific.

---

## Functionalities

### 1. Gym Management
- Manager: Add/edit/remove gyms, assign trainers.
- View trainers per gym.

### 2. Trainer Management
- Trainers create programs and set availability.
- Add/edit/remove assign customers.

### 3. Customer Management
- Customers view/book trainers.
- Admin manages accounts and memberships.

### 4. Scheduling System
- Algorithm optimizes schedules to avoid conflicts.
- Real-time updates for trainer availability.

### 5. Communication
- Notifications for bookings/cancellations.
- Email/SMS reminders for sessions.

---

## Technology Stack

### Frontend
- **HTML5**: Website structure.
- **CSS3**: Styling and responsiveness.
- **JavaScript**: Dynamic content.

### Backend
- **Python (Flask)**: RESTful APIs and logic.
- **MySQL**: Database management.

### Scheduling Algorithm
- **Greedy Algorithm**: Minimizes scheduling conflicts.

### Additional Libraries
- **SQLAlchemy**: Database interaction.

---

## Flowchart

### 1. User Authentication
- Role-based access (Admin, Manager, Trainer, Customer).

### 2. Gym/Trainer/Customer Interactions
- Admin manages gyms/trainers.
- Trainers manage programs/schedules.
- Customers book sessions.

### 3. Scheduling and Optimization
- System checks trainer availability before booking.
- Algorithm updates schedules dynamically.

---

## Non-Functional Requirements
- **Scalability**: Support growing user base.
- **Security**: Encrypt sensitive data (e.g., passwords).
- **Performance**: Fast response times for bookings.
- **Usability**: Intuitive interface for all roles.

---

## Conclusion
The Gym Management Platform streamlines gym operations by automating scheduling, memberships, and personalized training programs. It enhances efficiency for managers, trainers, and clients, creating a seamless fitness management experience.
