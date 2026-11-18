"""
Initialize the database and seed the Admin user.
Run this script once before starting the application:
    python init_db.py
"""
from app import app
from models import db, User
from werkzeug.security import generate_password_hash


def init_database():
    """Create all tables and seed the default Admin user."""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully.")

        # Check if Admin already exists
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@emp.com',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                name='Administrator',
                department='Administration',
                is_approved=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully.")
            print("  Username: admin")
            print("  Password: admin123")
        else:
            print("Admin user already exists.")


if __name__ == '__main__':
    init_database()
