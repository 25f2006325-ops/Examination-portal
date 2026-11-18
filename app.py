from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'emp-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Register Blueprints
from admin_routes import admin_bp
from examiner_routes import examiner_bp
from student_routes import student_bp

app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(examiner_bp, url_prefix='/examiner')
app.register_blueprint(student_bp, url_prefix='/student')


# ─── Index ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Redirect to role-specific dashboard if logged in, else to login."""
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'examiner':
            return redirect(url_for('examiner.dashboard'))
        elif role == 'student':
            return redirect(url_for('student.dashboard'))
    return redirect(url_for('login'))


# ─── Authentication ──────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            # Check if examiner is approved
            if user.role == 'examiner' and not user.is_approved:
                flash('Your account is awaiting Admin approval.', 'warning')
                return redirect(url_for('login'))

            # Check if account is active
            if not user.is_active:
                flash('Your account has been deactivated. Contact the administrator.', 'danger')
                return redirect(url_for('login'))

            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            session['name'] = user.name
            session['role'] = user.role

            flash(f'Welcome, {user.name}!', 'success')

            # Redirect to role-specific dashboard
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'examiner':
                return redirect(url_for('examiner.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        role = request.form.get('role', 'student')
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip()
        contact = request.form.get('contact', '').strip()

        # Only student and examiner can register
        if role not in ['student', 'examiner']:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('register'))

        # Check for existing username or email
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        # Validate required fields
        if not name or not username or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('register'))

        # Create user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            name=name,
            department=department,
            contact=contact,
            is_approved=(role == 'student'),  # Students are auto-approved
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()

        if role == 'examiner':
            flash('Registration successful! Please wait for Admin approval before logging in.', 'info')
        else:
            flash('Registration successful! You can now log in.', 'success')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
