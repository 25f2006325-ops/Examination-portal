from datetime import datetime, date, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import (
    db, User, Course, Examination, ExaminationSlot, Booking, Evaluation, ExaminationRubric, examiner_examination
)
from auth import login_required, role_required

student_bp = Blueprint('student', __name__)


# ─── Dashboard ───────────────────────────────────────────────────────────────

@student_bp.route('/')
@role_required('student')
def dashboard():
    """Student dashboard showing examination statistics and upcoming examinations."""
    student_id = session['user_id']
    student = db.session.get(User, student_id)

    # 1. Available examinations count (status='Booking Open')
    available_exams_count = Examination.query.filter_by(status='Booking Open').count()

    # 2. Booked slots count (active bookings with status='Booked')
    booked_slots_count = Booking.query.filter_by(
        student_id=student_id,
        status='Booked'
    ).count()

    # 3. Published results count (bookings with status='Completed' having evaluations)
    published_results_count = (
        Booking.query.filter(
            Booking.student_id == student_id,
            Booking.status == 'Completed',
            Booking.evaluations.any()
        ).count()
    )

    # 4. Upcoming examinations: student is booked for, status='Booked', slot date >= today
    today = date.today()
    upcoming_bookings = (
        Booking.query.join(ExaminationSlot)
        .join(Examination)
        .filter(
            Booking.student_id == student_id,
            Booking.status == 'Booked',
            ExaminationSlot.date >= today
        )
        .order_by(ExaminationSlot.date.asc(), ExaminationSlot.start_time.asc())
        .all()
    )
    upcoming_exams_count = len(upcoming_bookings)

    return render_template(
        'student/dashboard.html',
        student=student,
        available_exams_count=available_exams_count,
        upcoming_exams_count=upcoming_exams_count,
        booked_slots_count=booked_slots_count,
        published_results_count=published_results_count,
        upcoming_bookings=upcoming_bookings
    )


# ─── Profile ─────────────────────────────────────────────────────────────────

@student_bp.route('/profile', methods=['GET', 'POST'])
@role_required('student')
def profile():
    """View and edit student profile (name, email, department, contact)."""
    student = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        department = request.form.get('department', '').strip()
        contact = request.form.get('contact', '').strip()

        if not name or not email:
            flash('Name and email are required fields.', 'danger')
            return render_template('student/profile.html', student=student)

        # Check if email is already in use by another user
        existing_user = User.query.filter(User.email == email, User.id != student.id).first()
        if existing_user:
            flash('Email address is already in use by another account.', 'danger')
            return render_template('student/profile.html', student=student)

        student.name = name
        student.email = email
        student.department = department
        student.contact = contact
        db.session.commit()

        # Keep session user name in sync
        session['name'] = student.name

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.profile'))

    return render_template('student/profile.html', student=student)


# ─── Examinations ────────────────────────────────────────────────────────────

@student_bp.route('/examinations')
@role_required('student')
def examinations():
    """Browse available examinations with optional search by exam name or course name."""
    q = request.args.get('q', '').strip()
    allowed_statuses = ['Booking Open', 'Slot Creation', 'Closed', 'Completed']

    query = Examination.query.join(Course).filter(Examination.status.in_(allowed_statuses))

    if q:
        query = query.filter(
            db.or_(
                Examination.exam_name.ilike(f'%{q}%'),
                Course.course_name.ilike(f'%{q}%'),
                Course.course_code.ilike(f'%{q}%')
            )
        )

    exam_list = query.order_by(Examination.created_at.desc()).all()

    # Track examinations the student is currently booked for
    booked_slots = Booking.query.filter_by(
        student_id=session['user_id'],
        status='Booked'
    ).all()
    booked_exam_ids = {b.slot.examination_id for b in booked_slots if b.slot}

    return render_template(
        'student/examinations.html',
        examinations=exam_list,
        booked_exam_ids=booked_exam_ids,
        q=q
    )


# ─── Slots ───────────────────────────────────────────────────────────────────

@student_bp.route('/examinations/<int:exam_id>/slots')
@role_required('student')
def exam_slots(exam_id):
    """View available examination slots for a specific examination."""
    examination = Examination.query.get_or_404(exam_id)
    slots = (
        ExaminationSlot.query.filter_by(examination_id=exam_id)
        .order_by(ExaminationSlot.date.asc(), ExaminationSlot.start_time.asc())
        .all()
    )

    # Check if student already has a booked slot for this examination
    existing_booking = Booking.query.join(ExaminationSlot).filter(
        Booking.student_id == session['user_id'],
        Booking.status == 'Booked',
        ExaminationSlot.examination_id == exam_id
    ).first()

    now = datetime.now()
    is_booking_time = True
    if examination.slot_booking_start and now < examination.slot_booking_start:
        is_booking_time = False
    if examination.slot_booking_end and now > examination.slot_booking_end:
        is_booking_time = False

    return render_template(
        'student/slots.html',
        examination=examination,
        slots=slots,
        existing_booking=existing_booking,
        is_booking_time=is_booking_time
    )


# ─── Booking ─────────────────────────────────────────────────────────────────

@student_bp.route('/book/<int:slot_id>', methods=['POST'])
@role_required('student')
def book_slot(slot_id):
    """Book a slot following all validation rules."""
    slot = ExaminationSlot.query.get_or_404(slot_id)
    exam = slot.examination

    # 1. Check exam status is 'Booking Open'
    if exam.status != 'Booking Open':
        flash('Booking is not open for this examination', 'danger')
        return redirect(url_for('student.exam_slots', exam_id=slot.examination_id))

    # 2. Check current datetime is between exam's slot_booking_start and slot_booking_end
    now = datetime.now()
    if (exam.slot_booking_start and now < exam.slot_booking_start) or \
       (exam.slot_booking_end and now > exam.slot_booking_end):
        flash('Booking period has ended/not started', 'danger')
        return redirect(url_for('student.exam_slots', exam_id=slot.examination_id))

    # 3. Check slot.status == 'Available' and slot.available_seats > 0
    if slot.status != 'Available' or slot.available_seats <= 0:
        flash('This slot is full', 'danger')
        return redirect(url_for('student.exam_slots', exam_id=slot.examination_id))

    # 4. Check no existing booking (status='Booked') for this student for ANY slot of the same examination
    existing = Booking.query.join(ExaminationSlot).filter(
        Booking.student_id == session['user_id'],
        Booking.status == 'Booked',
        ExaminationSlot.examination_id == slot.examination_id
    ).first()
    if existing:
        flash('You already have a booking for this examination', 'warning')
        return redirect(url_for('student.bookings'))

    # 5. Create Booking, decrement available_seats, set status='Full' if 0 seats remain
    booking = Booking(
        student_id=session['user_id'],
        slot_id=slot.id,
        booking_date=datetime.now(),
        status='Booked'
    )
    db.session.add(booking)
    slot.available_seats -= 1
    if slot.available_seats <= 0:
        slot.available_seats = 0
        slot.status = 'Full'
    db.session.commit()

    flash('Slot booked successfully!', 'success')
    return redirect(url_for('student.bookings'))


# ─── Bookings ────────────────────────────────────────────────────────────────

@student_bp.route('/bookings')
@role_required('student')
def bookings():
    """Show all current active bookings (status='Booked') for the logged in student."""
    current_bookings = (
        Booking.query.filter_by(student_id=session['user_id'], status='Booked')
        .join(ExaminationSlot)
        .order_by(ExaminationSlot.date.asc(), ExaminationSlot.start_time.asc())
        .all()
    )
    return render_template('student/bookings.html', bookings=current_bookings)


@student_bp.route('/bookings/<int:id>/cancel', methods=['POST'])
@role_required('student')
def cancel_booking(id):
    """Cancel an active booking before the slot booking deadline."""
    booking = Booking.query.get_or_404(id)

    # 1. Verify booking belongs to this student
    if booking.student_id != session['user_id']:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('student.bookings'))

    # 2. Check booking status is 'Booked'
    if booking.status != 'Booked':
        flash('Only active bookings can be cancelled.', 'warning')
        return redirect(url_for('student.bookings'))

    # 3. Check current datetime < slot_booking_end (cancel deadline)
    slot = booking.slot
    exam = slot.examination if slot else None
    now = datetime.now()
    if exam and exam.slot_booking_end and now > exam.slot_booking_end:
        flash('Cancellation deadline has passed. This booking cannot be cancelled.', 'danger')
        return redirect(url_for('student.bookings'))

    # 4. Set booking.status = 'Cancelled'
    booking.status = 'Cancelled'

    # 5. Increment slot.available_seats; reset status to 'Available' if it was 'Full'
    if slot:
        slot.available_seats += 1
        if slot.status == 'Full':
            slot.status = 'Available'

    db.session.commit()
    flash('Booking cancelled successfully.', 'success')
    return redirect(url_for('student.bookings'))


# ─── History ─────────────────────────────────────────────────────────────────

@student_bp.route('/history')
@role_required('student')
def history():
    """View all bookings (including cancelled and completed) for this student."""
    all_bookings = (
        Booking.query.filter_by(student_id=session['user_id'])
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return render_template('student/history.html', bookings=all_bookings)


# ─── Results ─────────────────────────────────────────────────────────────────

@student_bp.route('/results')
@role_required('student')
def results():
    """View completed examinations with evaluation details (marks per rubric, total marks, remarks)."""
    completed_bookings = (
        Booking.query.filter_by(student_id=session['user_id'], status='Completed')
        .order_by(Booking.booking_date.desc())
        .all()
    )

    results_data = []
    for booking in completed_bookings:
        if booking.evaluations:
            total_obtained = sum(e.marks_obtained for e in booking.evaluations)
            total_max = sum(e.rubric.max_marks for e in booking.evaluations if e.rubric)
            if total_max == 0 and booking.slot and booking.slot.examination:
                total_max = booking.slot.examination.max_marks
            percentage = round((total_obtained / total_max * 100), 2) if total_max > 0 else 0

            results_data.append({
                'booking': booking,
                'evaluations': booking.evaluations,
                'total_obtained': total_obtained,
                'total_max': total_max,
                'percentage': percentage
            })

    return render_template('student/results.html', results=results_data)
