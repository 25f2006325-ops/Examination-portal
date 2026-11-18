from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, User, Course, Examination, ExaminationRubric, ExaminationSlot, Booking, Evaluation, examiner_examination
from auth import login_required, role_required
from datetime import datetime, date, time

examiner_bp = Blueprint('examiner', __name__)


def parse_time_input(time_str):
    """Parse time string from HH:MM or HH:MM:SS format."""
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Invalid time format: {time_str}")


# ─── Dashboard ───────────────────────────────────────────────────────────────

@examiner_bp.route('/')
@role_required('examiner')
def dashboard():
    examiner = db.session.get(User, session['user_id'])

    # Assigned examinations count
    assigned_exams_count = len(examiner.assigned_examinations)

    # Created examination slots count
    slots = examiner.slots_created
    created_slots_count = len(slots)

    # Number of students booked across examiner's slots
    slot_ids = [slot.id for slot in slots]
    if slot_ids:
        booked_bookings = Booking.query.filter(
            Booking.slot_id.in_(slot_ids),
            Booking.status == 'Booked'
        ).all()
        students_booked_count = len(booked_bookings)
        pending_evaluations_count = sum(1 for b in booked_bookings if not b.evaluations)
    else:
        students_booked_count = 0
        pending_evaluations_count = 0

    return render_template(
        'examiner/dashboard.html',
        examiner=examiner,
        assigned_exams_count=assigned_exams_count,
        created_slots_count=created_slots_count,
        students_booked_count=students_booked_count,
        pending_evaluations_count=pending_evaluations_count
    )


# ─── Profile ─────────────────────────────────────────────────────────────────

@examiner_bp.route('/profile', methods=['GET', 'POST'])
@role_required('examiner')
def profile():
    examiner = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        department = request.form.get('department', '').strip()
        contact = request.form.get('contact', '').strip()

        if not name or not email:
            flash('Name and email are required fields.', 'danger')
            return render_template('examiner/profile.html', examiner=examiner)

        # Check if email is used by another user
        existing_user = User.query.filter(User.email == email, User.id != examiner.id).first()
        if existing_user:
            flash('This email is already registered by another account.', 'danger')
            return render_template('examiner/profile.html', examiner=examiner)

        examiner.name = name
        examiner.email = email
        examiner.department = department
        examiner.contact = contact
        session['name'] = examiner.name

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('examiner.profile'))

    return render_template('examiner/profile.html', examiner=examiner)


# ─── Assigned Examinations ───────────────────────────────────────────────────

@examiner_bp.route('/examinations')
@role_required('examiner')
def examinations():
    examiner = db.session.get(User, session['user_id'])
    examinations = examiner.assigned_examinations
    return render_template('examiner/examinations.html', examiner=examiner, examinations=examinations)


# ─── Slots List ──────────────────────────────────────────────────────────────

@examiner_bp.route('/slots')
@role_required('examiner')
def slots():
    examiner = db.session.get(User, session['user_id'])
    slots = ExaminationSlot.query.filter_by(examiner_id=examiner.id).order_by(
        ExaminationSlot.date.desc(),
        ExaminationSlot.start_time.asc()
    ).all()
    now = datetime.now()
    return render_template('examiner/slots.html', examiner=examiner, slots=slots, now=now)


# ─── Create Slot ─────────────────────────────────────────────────────────────

@examiner_bp.route('/slots/create', methods=['GET', 'POST'])
@role_required('examiner')
def create_slot():
    examiner = db.session.get(User, session['user_id'])
    now = datetime.now()

    # Dropdown of assigned examinations that are currently in slot creation period
    eligible_examinations = [
        exam for exam in examiner.assigned_examinations
        if exam.slot_creation_start and exam.slot_creation_end and exam.slot_creation_start <= now <= exam.slot_creation_end
    ]

    if request.method == 'POST':
        exam_id = request.form.get('examination_id')
        slot_date_str = request.form.get('date', '').strip()
        start_time_str = request.form.get('start_time', '').strip()
        end_time_str = request.form.get('end_time', '').strip()
        max_capacity_str = request.form.get('max_capacity', '').strip()

        if not (exam_id and slot_date_str and start_time_str and end_time_str and max_capacity_str):
            flash('All fields are required to create a slot.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        exam = db.session.get(Examination, exam_id)
        if not exam or exam not in examiner.assigned_examinations:
            flash('Selected examination is not assigned to you or does not exist.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        # BUSINESS LOGIC: Check that current datetime is between exam's slot_creation_start and slot_creation_end
        if not (exam.slot_creation_start and exam.slot_creation_end and exam.slot_creation_start <= now <= exam.slot_creation_end):
            flash('Slot creation is only allowed within the examination slot creation period.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        try:
            slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
            start_time_obj = parse_time_input(start_time_str)
            end_time_obj = parse_time_input(end_time_str)
            max_capacity = int(max_capacity_str)
        except ValueError:
            flash('Invalid date, time, or capacity format.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        if max_capacity < 1:
            flash('Maximum capacity must be at least 1.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        if start_time_obj >= end_time_obj:
            flash('End time must be after start time.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)

        # Set available_seats = max_capacity on create
        new_slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner.id,
            date=slot_date,
            start_time=start_time_obj,
            end_time=end_time_obj,
            max_capacity=max_capacity,
            available_seats=max_capacity,
            status='Available'
        )
        db.session.add(new_slot)
        db.session.commit()

        flash('Examination slot created successfully.', 'success')
        return redirect(url_for('examiner.slots'))

    return render_template('examiner/slot_form.html', examiner=examiner, examinations=eligible_examinations)


# ─── Edit Slot ───────────────────────────────────────────────────────────────

@examiner_bp.route('/slots/<int:id>/edit', methods=['GET', 'POST'])
@role_required('examiner')
def edit_slot(id):
    examiner = db.session.get(User, session['user_id'])
    slot = ExaminationSlot.query.get_or_404(id)

    # Verify slot belongs to this examiner
    if slot.examiner_id != examiner.id:
        flash('You do not have permission to edit this slot.', 'danger')
        return redirect(url_for('examiner.slots'))

    # Only allow if current datetime is before exam's slot_booking_start
    now = datetime.now()
    if slot.examination.slot_booking_start and now >= slot.examination.slot_booking_start:
        flash('Cannot edit slot: student booking period has already started.', 'danger')
        return redirect(url_for('examiner.slots'))

    # Examinations list containing the slot's examination
    examinations = examiner.assigned_examinations
    if slot.examination not in examinations:
        examinations = [slot.examination] + list(examinations)

    if request.method == 'POST':
        exam_id = request.form.get('examination_id')
        slot_date_str = request.form.get('date', '').strip()
        start_time_str = request.form.get('start_time', '').strip()
        end_time_str = request.form.get('end_time', '').strip()
        max_capacity_str = request.form.get('max_capacity', '').strip()

        if not (slot_date_str and start_time_str and end_time_str and max_capacity_str):
            flash('All fields are required.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)

        if exam_id:
            exam = db.session.get(Examination, exam_id)
            if exam and exam in examiner.assigned_examinations:
                slot.examination_id = exam.id

        try:
            slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
            start_time_obj = parse_time_input(start_time_str)
            end_time_obj = parse_time_input(end_time_str)
            max_capacity = int(max_capacity_str)
        except ValueError:
            flash('Invalid date, time, or capacity format.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)

        if max_capacity < 1:
            flash('Maximum capacity must be at least 1.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)

        if start_time_obj >= end_time_obj:
            flash('End time must be after start time.', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)

        booked_seats = sum(1 for b in slot.bookings if b.status == 'Booked')
        if max_capacity < booked_seats:
            flash(f'Maximum capacity cannot be less than currently booked seats ({booked_seats}).', 'danger')
            return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)

        slot.date = slot_date
        slot.start_time = start_time_obj
        slot.end_time = end_time_obj
        slot.max_capacity = max_capacity
        slot.available_seats = max_capacity - booked_seats
        if slot.available_seats == 0:
            slot.status = 'Full'
        elif slot.status == 'Full' and slot.available_seats > 0:
            slot.status = 'Available'

        db.session.commit()
        flash('Examination slot updated successfully.', 'success')
        return redirect(url_for('examiner.slots'))

    return render_template('examiner/slot_form.html', examiner=examiner, slot=slot, examinations=examinations)


# ─── Delete Slot ─────────────────────────────────────────────────────────────

@examiner_bp.route('/slots/<int:id>/delete', methods=['POST'])
@role_required('examiner')
def delete_slot(id):
    examiner = db.session.get(User, session['user_id'])
    slot = ExaminationSlot.query.get_or_404(id)

    # 1. Slot belongs to this examiner
    if slot.examiner_id != examiner.id:
        flash('You do not have permission to delete this slot.', 'danger')
        return redirect(url_for('examiner.slots'))

    # 2. Current date/time is before exam's slot_booking_start
    now = datetime.now()
    if slot.examination.slot_booking_start and now >= slot.examination.slot_booking_start:
        flash('Cannot delete slot: student booking period has already started.', 'danger')
        return redirect(url_for('examiner.slots'))

    # 3. No bookings exist for this slot
    if slot.bookings and len(slot.bookings) > 0:
        flash('Cannot delete slot: bookings already exist for this slot.', 'danger')
        return redirect(url_for('examiner.slots'))

    db.session.delete(slot)
    db.session.commit()
    flash('Examination slot deleted successfully.', 'success')
    return redirect(url_for('examiner.slots'))


# ─── Booked Students ─────────────────────────────────────────────────────────

@examiner_bp.route('/slots/<int:id>/students')
@role_required('examiner')
def booked_students(id):
    examiner = db.session.get(User, session['user_id'])
    slot = ExaminationSlot.query.get_or_404(id)

    # Verify slot belongs to this examiner
    if slot.examiner_id != examiner.id:
        flash('You do not have permission to view students for this slot.', 'danger')
        return redirect(url_for('examiner.slots'))

    bookings = Booking.query.filter_by(slot_id=slot.id).all()
    return render_template('examiner/booked_students.html', examiner=examiner, slot=slot, bookings=bookings)


# ─── Evaluate Student ────────────────────────────────────────────────────────

@examiner_bp.route('/slots/<int:slot_id>/evaluate/<int:booking_id>', methods=['GET', 'POST'])
@role_required('examiner')
def evaluate(slot_id, booking_id):
    examiner = db.session.get(User, session['user_id'])
    slot = ExaminationSlot.query.get_or_404(slot_id)

    # Verify slot belongs to this examiner
    if slot.examiner_id != examiner.id:
        flash('You do not have permission to evaluate bookings in this slot.', 'danger')
        return redirect(url_for('examiner.slots'))

    # Verify booking belongs to this slot
    booking = Booking.query.get_or_404(booking_id)
    if booking.slot_id != slot.id:
        flash('Booking does not belong to this slot.', 'danger')
        return redirect(url_for('examiner.booked_students', id=slot.id))

    rubrics = ExaminationRubric.query.filter_by(examination_id=slot.examination_id).all()
    existing_evals = {ev.rubric_id: ev for ev in booking.evaluations}

    if request.method == 'POST':
        eval_data = []
        for rubric in rubrics:
            marks_str = request.form.get(f'marks_{rubric.id}', '').strip()
            remarks = request.form.get(f'remarks_{rubric.id}', '').strip()

            try:
                marks = float(marks_str)
            except ValueError:
                flash(f'Please enter a valid numeric mark for "{rubric.criterion_name}".', 'danger')
                return render_template(
                    'examiner/evaluate.html',
                    examiner=examiner,
                    slot=slot,
                    booking=booking,
                    rubrics=rubrics,
                    existing_evals=existing_evals
                )

            if marks < 0 or marks > rubric.max_marks:
                flash(f'Marks for "{rubric.criterion_name}" must be between 0 and {rubric.max_marks}.', 'danger')
                return render_template(
                    'examiner/evaluate.html',
                    examiner=examiner,
                    slot=slot,
                    booking=booking,
                    rubrics=rubrics,
                    existing_evals=existing_evals
                )

            eval_data.append((rubric, marks, remarks))

        # Save/update Evaluation records for each rubric criterion
        for rubric, marks, remarks in eval_data:
            evaluation = Evaluation.query.filter_by(booking_id=booking.id, rubric_id=rubric.id).first()
            if not evaluation:
                evaluation = Evaluation(booking_id=booking.id, rubric_id=rubric.id)
                db.session.add(evaluation)

            evaluation.marks_obtained = marks
            evaluation.remarks = remarks
            evaluation.evaluated_at = datetime.now()

        # Update booking status to 'Completed'
        booking.status = 'Completed'
        db.session.commit()

        flash(f'Evaluation for {booking.student.name} saved successfully.', 'success')
        return redirect(url_for('examiner.booked_students', id=slot.id))

    return render_template(
        'examiner/evaluate.html',
        examiner=examiner,
        slot=slot,
        booking=booking,
        rubrics=rubrics,
        existing_evals=existing_evals
    )
