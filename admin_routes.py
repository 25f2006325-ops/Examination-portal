from datetime import datetime, date, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, User, Course, Examination, ExaminationRubric, ExaminationSlot, Booking, Evaluation, examiner_examination
from auth import login_required, role_required

admin_bp = Blueprint('admin', __name__)


def parse_datetime(dt_str):
    """Helper to parse datetime from HTML datetime-local inputs."""
    if not dt_str:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            pass
    return None


# ─── Dashboard ────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@role_required('admin')
def dashboard():
    """Admin dashboard showing overall system counts."""
    total_courses = Course.query.count()
    total_examinations = Examination.query.count()
    total_examiners = User.query.filter_by(role='examiner').count()
    total_students = User.query.filter_by(role='student').count()
    total_slots = ExaminationSlot.query.count()
    total_bookings = Booking.query.count()

    return render_template(
        'admin/dashboard.html',
        total_courses=total_courses,
        total_examinations=total_examinations,
        total_examiners=total_examiners,
        total_students=total_students,
        total_slots=total_slots,
        total_bookings=total_bookings
    )


# ─── Courses CRUD ─────────────────────────────────────────────────────────────

@admin_bp.route('/courses')
@role_required('admin')
def courses():
    """List all courses."""
    courses_list = Course.query.order_by(Course.created_at.desc()).all()
    return render_template('admin/courses.html', courses=courses_list)


@admin_bp.route('/courses/create', methods=['GET', 'POST'])
@role_required('admin')
def create_course():
    """Create a new course."""
    if request.method == 'POST':
        course_code = request.form.get('course_code', '').strip().upper()
        course_name = request.form.get('course_name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'active')

        if not course_code or not course_name:
            flash('Course code and course name are required.', 'danger')
            return render_template('admin/course_form.html', course=None)

        existing = Course.query.filter_by(course_code=course_code).first()
        if existing:
            flash(f'Course code "{course_code}" already exists.', 'danger')
            return render_template('admin/course_form.html', course=None)

        course = Course(
            course_code=course_code,
            course_name=course_name,
            description=description,
            status=status
        )
        db.session.add(course)
        db.session.commit()
        flash('Course created successfully!', 'success')
        return redirect(url_for('admin.courses'))

    return render_template('admin/course_form.html', course=None)


@admin_bp.route('/courses/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_course(id):
    """Edit an existing course."""
    course = Course.query.get_or_404(id)

    if request.method == 'POST':
        course_code = request.form.get('course_code', '').strip().upper()
        course_name = request.form.get('course_name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'active')

        if not course_code or not course_name:
            flash('Course code and course name are required.', 'danger')
            return render_template('admin/course_form.html', course=course)

        existing = Course.query.filter(Course.course_code == course_code, Course.id != id).first()
        if existing:
            flash(f'Course code "{course_code}" is already in use by another course.', 'danger')
            return render_template('admin/course_form.html', course=course)

        course.course_code = course_code
        course.course_name = course_name
        course.description = description
        course.status = status
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin.courses'))

    return render_template('admin/course_form.html', course=course)


@admin_bp.route('/courses/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_course(id):
    """Delete a course."""
    course = Course.query.get_or_404(id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully.', 'success')
    return redirect(url_for('admin.courses'))


# ─── Examinations CRUD ────────────────────────────────────────────────────────

@admin_bp.route('/examinations')
@role_required('admin')
def examinations():
    """List all examinations with course info."""
    exams = Examination.query.order_by(Examination.created_at.desc()).all()
    return render_template('admin/examinations.html', examinations=exams)


@admin_bp.route('/examinations/create', methods=['GET', 'POST'])
@role_required('admin')
def create_examination():
    """Create a new examination."""
    courses = Course.query.order_by(Course.course_code.asc()).all()

    if request.method == 'POST':
        course_id = request.form.get('course_id', type=int)
        exam_name = request.form.get('exam_name', '').strip()
        exam_type = request.form.get('exam_type', 'Viva')
        duration = request.form.get('duration', default=60, type=int)
        max_marks = request.form.get('max_marks', type=float)
        slot_creation_start = parse_datetime(request.form.get('slot_creation_start'))
        slot_creation_end = parse_datetime(request.form.get('slot_creation_end'))
        slot_booking_start = parse_datetime(request.form.get('slot_booking_start'))
        slot_booking_end = parse_datetime(request.form.get('slot_booking_end'))
        status = request.form.get('status', 'Draft')

        if not course_id or not exam_name or max_marks is None:
            flash('Course, Examination Name, and Max Marks are required.', 'danger')
            return render_template('admin/exam_form.html', exam=None, courses=courses)

        exam = Examination(
            course_id=course_id,
            exam_name=exam_name,
            exam_type=exam_type,
            duration=duration,
            max_marks=max_marks,
            slot_creation_start=slot_creation_start,
            slot_creation_end=slot_creation_end,
            slot_booking_start=slot_booking_start,
            slot_booking_end=slot_booking_end,
            status=status
        )
        db.session.add(exam)
        db.session.commit()
        flash('Examination created successfully!', 'success')
        return redirect(url_for('admin.examinations'))

    return render_template('admin/exam_form.html', exam=None, courses=courses)


@admin_bp.route('/examinations/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_examination(id):
    """Edit an existing examination."""
    exam = Examination.query.get_or_404(id)
    courses = Course.query.order_by(Course.course_code.asc()).all()

    if request.method == 'POST':
        course_id = request.form.get('course_id', type=int)
        exam_name = request.form.get('exam_name', '').strip()
        exam_type = request.form.get('exam_type', 'Viva')
        duration = request.form.get('duration', default=60, type=int)
        max_marks = request.form.get('max_marks', type=float)
        slot_creation_start = parse_datetime(request.form.get('slot_creation_start'))
        slot_creation_end = parse_datetime(request.form.get('slot_creation_end'))
        slot_booking_start = parse_datetime(request.form.get('slot_booking_start'))
        slot_booking_end = parse_datetime(request.form.get('slot_booking_end'))
        status = request.form.get('status', exam.status)

        if not course_id or not exam_name or max_marks is None:
            flash('Course, Examination Name, and Max Marks are required.', 'danger')
            return render_template('admin/exam_form.html', exam=exam, courses=courses)

        exam.course_id = course_id
        exam.exam_name = exam_name
        exam.exam_type = exam_type
        exam.duration = duration
        exam.max_marks = max_marks
        exam.slot_creation_start = slot_creation_start
        exam.slot_creation_end = slot_creation_end
        exam.slot_booking_start = slot_booking_start
        exam.slot_booking_end = slot_booking_end
        exam.status = status

        db.session.commit()
        flash('Examination updated successfully!', 'success')
        return redirect(url_for('admin.examinations'))

    return render_template('admin/exam_form.html', exam=exam, courses=courses)


@admin_bp.route('/examinations/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_examination(id):
    """Delete an examination."""
    exam = Examination.query.get_or_404(id)
    db.session.delete(exam)
    db.session.commit()
    flash('Examination deleted successfully.', 'success')
    return redirect(url_for('admin.examinations'))


# ─── Assign Examiners to Examination ──────────────────────────────────────────

@admin_bp.route('/examinations/<int:exam_id>/assign-examiners', methods=['GET', 'POST'])
@role_required('admin')
def assign_examiners(exam_id):
    """Assign or remove approved examiners from an examination."""
    exam = Examination.query.get_or_404(exam_id)
    all_approved_examiners = User.query.filter_by(
        role='examiner', is_approved=True, is_active=True
    ).order_by(User.name.asc()).all()

    if request.method == 'POST':
        # Get list of selected examiner IDs from form checkboxes
        selected_ids = request.form.getlist('examiner_ids', type=int)

        # Fetch selected examiner objects
        selected_examiners = User.query.filter(
            User.id.in_(selected_ids),
            User.role == 'examiner',
            User.is_approved == True,
            User.is_active == True
        ).all() if selected_ids else []

        # Replace the current assignment list entirely
        exam.assigned_examiners = selected_examiners
        db.session.commit()

        count = len(selected_examiners)
        flash(f'{count} examiner(s) assigned to "{exam.exam_name}" successfully.', 'success')
        return redirect(url_for('admin.examinations'))

    # IDs of currently assigned examiners
    assigned_ids = {e.id for e in exam.assigned_examiners}
    return render_template(
        'admin/assign_examiners.html',
        exam=exam,
        all_examiners=all_approved_examiners,
        assigned_ids=assigned_ids
    )


# ─── Rubrics CRUD ─────────────────────────────────────────────────────────────

@admin_bp.route('/examinations/<int:exam_id>/rubrics')
@role_required('admin')
def rubrics(exam_id):
    """List rubrics for a specific examination."""
    exam = Examination.query.get_or_404(exam_id)
    rubrics_list = ExaminationRubric.query.filter_by(examination_id=exam_id).all()
    return render_template('admin/rubrics.html', examination=exam, rubrics=rubrics_list)


@admin_bp.route('/examinations/<int:exam_id>/rubrics/create', methods=['GET', 'POST'])
@role_required('admin')
def create_rubric(exam_id):
    """Create a new rubric for an examination."""
    exam = Examination.query.get_or_404(exam_id)

    if request.method == 'POST':
        criterion_name = request.form.get('criterion_name', '').strip()
        max_marks = request.form.get('max_marks', type=float)
        weightage = request.form.get('weightage', default=1.0, type=float)
        description = request.form.get('description', '').strip()

        if not criterion_name or max_marks is None:
            flash('Criterion name and max marks are required.', 'danger')
            return render_template('admin/rubric_form.html', examination=exam, rubric=None)

        rubric = ExaminationRubric(
            examination_id=exam_id,
            criterion_name=criterion_name,
            max_marks=max_marks,
            weightage=weightage,
            description=description
        )
        db.session.add(rubric)
        db.session.commit()
        flash('Rubric criterion created successfully!', 'success')
        return redirect(url_for('admin.rubrics', exam_id=exam_id))

    return render_template('admin/rubric_form.html', examination=exam, rubric=None)


@admin_bp.route('/rubrics/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_rubric(id):
    """Edit an existing rubric."""
    rubric = ExaminationRubric.query.get_or_404(id)
    exam = rubric.examination

    if request.method == 'POST':
        criterion_name = request.form.get('criterion_name', '').strip()
        max_marks = request.form.get('max_marks', type=float)
        weightage = request.form.get('weightage', default=1.0, type=float)
        description = request.form.get('description', '').strip()

        if not criterion_name or max_marks is None:
            flash('Criterion name and max marks are required.', 'danger')
            return render_template('admin/rubric_form.html', examination=exam, rubric=rubric)

        rubric.criterion_name = criterion_name
        rubric.max_marks = max_marks
        rubric.weightage = weightage
        rubric.description = description
        db.session.commit()
        flash('Rubric criterion updated successfully!', 'success')
        return redirect(url_for('admin.rubrics', exam_id=exam.id))

    return render_template('admin/rubric_form.html', examination=exam, rubric=rubric)


@admin_bp.route('/rubrics/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_rubric(id):
    """Delete a rubric."""
    rubric = ExaminationRubric.query.get_or_404(id)
    exam_id = rubric.examination_id
    db.session.delete(rubric)
    db.session.commit()
    flash('Rubric criterion deleted successfully.', 'success')
    return redirect(url_for('admin.rubrics', exam_id=exam_id))


# ─── Examiner Management ──────────────────────────────────────────────────────

@admin_bp.route('/examiners')
@role_required('admin')
def examiners():
    """List all examiners with approval and active statuses."""
    examiners_list = User.query.filter_by(role='examiner').order_by(User.created_at.desc()).all()
    return render_template('admin/examiners.html', examiners=examiners_list)


@admin_bp.route('/examiners/<int:id>/approve', methods=['POST'])
@role_required('admin')
def approve_examiner(id):
    """Approve an examiner."""
    examiner = User.query.get_or_404(id)
    examiner.is_approved = True
    examiner.is_active = True
    db.session.commit()
    flash(f'Examiner "{examiner.name}" has been approved.', 'success')
    return redirect(url_for('admin.examiners'))


@admin_bp.route('/examiners/<int:id>/deactivate', methods=['POST'])
@role_required('admin')
def deactivate_examiner(id):
    """Deactivate an examiner."""
    examiner = User.query.get_or_404(id)
    examiner.is_active = False
    examiner.is_approved = False
    db.session.commit()
    flash(f'Examiner "{examiner.name}" has been deactivated.', 'warning')
    return redirect(url_for('admin.examiners'))


@admin_bp.route('/examiners/<int:id>/activate', methods=['POST'])
@role_required('admin')
def activate_examiner(id):
    """Activate an examiner."""
    examiner = User.query.get_or_404(id)
    examiner.is_active = True
    db.session.commit()
    flash(f'Examiner "{examiner.name}" has been activated.', 'success')
    return redirect(url_for('admin.examiners'))


# ─── Students View ────────────────────────────────────────────────────────────

@admin_bp.route('/students')
@role_required('admin')
def students():
    """List all registered students."""
    students_list = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
    return render_template('admin/students.html', students=students_list)


# ─── Slots View ───────────────────────────────────────────────────────────────

@admin_bp.route('/slots')
@role_required('admin')
def all_slots():
    """View all examination slots with examiner and exam info."""
    slots_list = ExaminationSlot.query.order_by(
        ExaminationSlot.date.desc(),
        ExaminationSlot.start_time.asc()
    ).all()
    return render_template('admin/slots.html', slots=slots_list)


# ─── Bookings View & Management ───────────────────────────────────────────────

@admin_bp.route('/bookings')
@role_required('admin')
def all_bookings():
    """View all bookings."""
    bookings_list = Booking.query.order_by(Booking.booking_date.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings_list)


@admin_bp.route('/bookings/<int:id>/reschedule', methods=['GET', 'POST'])
@role_required('admin')
def reschedule_booking(id):
    """Reschedule a student's booking to a different available slot for the same exam."""
    booking = Booking.query.get_or_404(id)
    current_slot = booking.slot

    available_slots = ExaminationSlot.query.filter(
        ExaminationSlot.examination_id == current_slot.examination_id,
        ExaminationSlot.id != current_slot.id,
        ExaminationSlot.available_seats > 0,
        ExaminationSlot.status == 'Available'
    ).order_by(ExaminationSlot.date.asc(), ExaminationSlot.start_time.asc()).all()

    if request.method == 'POST':
        new_slot_id = request.form.get('slot_id', type=int)

        if not new_slot_id:
            flash('Please select a new slot to reschedule.', 'warning')
            return redirect(url_for('admin.reschedule_booking', id=id))

        new_slot = ExaminationSlot.query.get_or_404(new_slot_id)

        if new_slot.examination_id != current_slot.examination_id:
            flash('Selected slot does not belong to the same examination.', 'danger')
            return redirect(url_for('admin.reschedule_booking', id=id))

        if new_slot.available_seats <= 0 or new_slot.status != 'Available':
            flash('Selected slot is no longer available.', 'danger')
            return redirect(url_for('admin.reschedule_booking', id=id))

        # Update available seats on current slot
        current_slot.available_seats += 1
        if current_slot.status == 'Full' and current_slot.available_seats > 0:
            current_slot.status = 'Available'

        # Update available seats on new slot
        new_slot.available_seats -= 1
        if new_slot.available_seats == 0:
            new_slot.status = 'Full'

        # Move booking
        booking.slot_id = new_slot.id
        booking.booking_date = datetime.now()
        db.session.commit()

        flash(f'Booking #{booking.id} rescheduled successfully to {new_slot.date} ({new_slot.start_time.strftime("%H:%M")} - {new_slot.end_time.strftime("%H:%M")}).', 'success')
        return redirect(url_for('admin.all_bookings'))

    return render_template('admin/reschedule.html', booking=booking, available_slots=available_slots)


# ─── Change Examiner ──────────────────────────────────────────────────────────

@admin_bp.route('/slots/<int:id>/change-examiner', methods=['GET', 'POST'])
@role_required('admin')
def change_examiner(id):
    """Change the assigned examiner for an examination slot."""
    slot = ExaminationSlot.query.get_or_404(id)
    examiners_list = User.query.filter_by(
        role='examiner',
        is_approved=True,
        is_active=True
    ).order_by(User.name.asc()).all()

    if request.method == 'POST':
        examiner_id = request.form.get('examiner_id', type=int)

        if not examiner_id:
            flash('Please select an examiner.', 'warning')
            return redirect(url_for('admin.change_examiner', id=id))

        new_examiner = User.query.filter_by(
            id=examiner_id,
            role='examiner',
            is_approved=True,
            is_active=True
        ).first()

        if not new_examiner:
            flash('Selected examiner is invalid or not approved/active.', 'danger')
            return redirect(url_for('admin.change_examiner', id=id))

        slot.examiner_id = new_examiner.id
        db.session.commit()
        flash(f'Examiner for Slot #{slot.id} changed to {new_examiner.name}.', 'success')
        return redirect(url_for('admin.all_slots'))

    return render_template('admin/change_examiner.html', slot=slot, examiners=examiners_list)


# ─── Search ───────────────────────────────────────────────────────────────────

@admin_bp.route('/search')
@role_required('admin')
def search():
    """Search across students, examiners, examinations, and bookings."""
    query = request.args.get('q', '').strip()
    students_list = []
    examiners_list = []
    examinations_list = []
    bookings_list = []

    if query:
        # Search students by name or username
        students_list = User.query.filter(
            User.role == 'student',
            (User.name.ilike(f'%{query}%') | User.username.ilike(f'%{query}%'))
        ).all()

        # Search examiners by name or username
        examiners_list = User.query.filter(
            User.role == 'examiner',
            (User.name.ilike(f'%{query}%') | User.username.ilike(f'%{query}%'))
        ).all()

        # Search examinations by exam_name
        examinations_list = Examination.query.filter(
            Examination.exam_name.ilike(f'%{query}%')
        ).all()

        # Search bookings by booking id
        if query.isdigit():
            booking_match = db.session.get(Booking, int(query))
            if booking_match:
                bookings_list.append(booking_match)

    return render_template(
        'admin/search.html',
        query=query,
        students=students_list,
        examiners=examiners_list,
        examinations=examinations_list,
        bookings=bookings_list
    )
