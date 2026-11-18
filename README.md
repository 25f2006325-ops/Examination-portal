# Examination Management Portal (EMP)

An Examination Management Portal web application built with Flask, SQLite, Jinja2, and Bootstrap 5.

## Features

- **Admin**: Manage courses, examinations, rubrics, examiners, slots, and bookings.
- **Examiner**: Create examination slots, view booked students, evaluate using rubrics.
- **Student**: Browse examinations, book slots, view results and history.

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (via SQLAlchemy ORM)
- **Frontend**: Jinja2 templates, HTML, CSS, Bootstrap 5

## Setup Instructions

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database** (creates tables + seeds Admin user):
   ```bash
   python init_db.py
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.

## Default Admin Credentials

- **Username**: `admin`
- **Password**: `admin123`

## Project Structure

```
├── app.py                 # Main Flask app + auth routes
├── models.py              # SQLAlchemy models
├── auth.py                # Auth decorators
├── admin_routes.py        # Admin blueprint
├── examiner_routes.py     # Examiner blueprint
├── student_routes.py      # Student blueprint
├── init_db.py             # Database initialization
├── requirements.txt       # Dependencies
├── static/css/style.css   # Custom styles
├── templates/             # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── admin/
│   ├── examiner/
│   └── student/
└── instance/emp.db        # SQLite database (auto-created)
```
