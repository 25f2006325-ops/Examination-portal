from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Many-to-many association table: Examiner <-> Examination
examiner_examination = db.Table('examiner_examination',
    db.Column('examiner_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('examination_id', db.Integer, db.ForeignKey('examination.id'), primary_key=True)
)


class User(db.Model):
    """Single user table for Admin, Examiner, and Student roles."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'examiner', 'student'
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), default='')
    contact = db.Column(db.String(20), default='')
    is_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    slots_created = db.relationship('ExaminationSlot', backref='examiner', lazy=True,
                                    foreign_keys='ExaminationSlot.examiner_id')
    bookings = db.relationship('Booking', backref='student', lazy=True,
                               foreign_keys='Booking.student_id')
    assigned_examinations = db.relationship('Examination', secondary=examiner_examination,
                                           backref=db.backref('assigned_examiners', lazy=True))

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Course(db.Model):
    """A course under which examinations are conducted."""
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active')  # 'active' / 'inactive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One course -> many examinations
    examinations = db.relationship('Examination', backref='course', lazy=True,
                                   cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'


class Examination(db.Model):
    """An examination created by Admin for a particular course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    exam_name = db.Column(db.String(200), nullable=False)
    exam_type = db.Column(db.String(50), nullable=False)  # Viva / Practical / Project Demo / Assessment
    duration = db.Column(db.Integer, default=60)  # duration in minutes
    max_marks = db.Column(db.Float, nullable=False)
    slot_creation_start = db.Column(db.DateTime)
    slot_creation_end = db.Column(db.DateTime)
    slot_booking_start = db.Column(db.DateTime)
    slot_booking_end = db.Column(db.DateTime)
    status = db.Column(db.String(30), default='Draft')  # Draft / Slot Creation / Booking Open / Closed / Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One examination -> many rubrics, slots
    rubrics = db.relationship('ExaminationRubric', backref='examination', lazy=True,
                              cascade='all, delete-orphan')
    slots = db.relationship('ExaminationSlot', backref='examination', lazy=True,
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Examination {self.exam_name}>'


class ExaminationRubric(db.Model):
    """Defines evaluation criteria for an examination."""
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    criterion_name = db.Column(db.String(200), nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, default=1.0)
    description = db.Column(db.Text, default='')

    def __repr__(self):
        return f'<Rubric {self.criterion_name}>'


class ExaminationSlot(db.Model):
    """A time slot created by an examiner for an examination."""
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False, default=1)
    available_seats = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), default='Available')  # Available / Full / Cancelled / Completed

    # One slot -> many bookings
    bookings = db.relationship('Booking', backref='slot', lazy=True,
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Slot {self.id} on {self.date}>'


class Booking(db.Model):
    """A record of a student booking an examination slot."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('examination_slot.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked')  # Booked / Cancelled / Completed

    # One booking -> many evaluations (one per rubric criterion)
    evaluations = db.relationship('Evaluation', backref='booking', lazy=True,
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Booking {self.id} - {self.status}>'


class Evaluation(db.Model):
    """Evaluation record linking a booking to a rubric criterion with marks."""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('examination_rubric.id'), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False, default=0)
    remarks = db.Column(db.Text, default='')
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)

    rubric = db.relationship('ExaminationRubric')

    def __repr__(self):
        return f'<Evaluation booking={self.booking_id} rubric={self.rubric_id}>'
