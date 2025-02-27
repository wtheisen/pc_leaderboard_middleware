from flask import Flask, request, render_template, jsonify, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func
from datetime import datetime, timezone
import requests
import json
import os
import secrets
import subprocess
import tempfile
import shutil
from pathlib import Path
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired
import pytz
from collections import defaultdict
from datetime import timedelta
import csv

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')  # Use a secure key
db = SQLAlchemy(app)


class AdminToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    net_id = db.Column(db.String(100), unique=True, nullable=False)  # Student's net id
    anonymous_id = db.Column(db.String(8), unique=True, nullable=False)  # Public identifier
    display_net_id = db.Column(db.Boolean, default=False)  # Preference for displaying net id
    secret_token = db.Column(db.String(32), unique=True, nullable=False)  # Secret token for verification
    debug = db.Column(db.Boolean, default=False)  # New column for debug users

    # Define the relationship to Submissions
    submissions = db.relationship('Submission', back_populates='student', lazy=True)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(8), db.ForeignKey('student.anonymous_id'), nullable=False)  # Link to anonymous_id
    status = db.Column(db.String(100), nullable=False)
    assignment = db.Column(db.String(100), nullable=False)
    code_score = db.Column(db.Float)
    runtime = db.Column(db.Float)  # in seconds
    lint_errors = db.Column(db.Float)
    submission_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Define the relationship back to Student
    student = db.relationship('Student', back_populates='submissions', primaryjoin="Submission.student_id == Student.anonymous_id")

class UpdateProfileForm(FlaskForm):
    display_net_id = BooleanField('Display Net ID on Leaderboard')
    secret_token = StringField('Secret Token', validators=[DataRequired()])
    submit = SubmitField('Update Profile')

class AdminAccessForm(FlaskForm):
    secret_token = StringField('Admin Secret Token', validators=[DataRequired()])
    submit = SubmitField('Access Admin Page')

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_open = db.Column(db.Boolean, default=True)  # Whether submissions are open
    deadline = db.Column(db.DateTime, nullable=False)  # Deadline for submissions
    description = db.Column(db.Text, nullable=True)  # Optional description

# Create the database tables
with app.app_context():
    db.create_all()

def parse_dredd_response(response_data):
    """Extract relevant metrics from Dredd's response"""
    result = {
        'result': 'failure',
        'code_score': 0.0,
        'runtime': 0.0,
    }
    
    try:
        # Extract code score - assuming it's in the main score field
        result['result'] = response_data.get('result', 'failure')
        result['code_score'] = float(response_data.get('score', 0.0))
        result['runtime'] = float(response_data.get('time', 0.0))
        
    except (ValueError, IndexError, KeyError) as e:
        print(f"Error parsing Dredd response: {e}")
        
    return result

def populate_student_table():
    """
    Populate the student table with all students in the class
    and assigns them a secret token for submission verification and LB display
    """
    # Path to the CSV file
    csv_file_path = 'students.csv'

    with open(csv_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            net_id = row['netid']
            # Check if the student already exists
            existing_student = Student.query.filter_by(net_id=net_id).first()

            if not existing_student:
                # Generate a unique anonymous ID and secret token
                anonymous_id = generate_anonymous_id()
                secret_token = generate_secret_token()

                # Create a new student record
                new_student = Student(
                    net_id=net_id,
                    anonymous_id=anonymous_id,
                    secret_token=secret_token
                )
                db.session.add(new_student)

    # Commit the changes to the database
    db.session.commit()

def generate_anonymous_id():
    """Generate a unique 8-character anonymous ID"""
    while True:
        anon_id = f"{secrets.token_hex(3)}"  # Creates IDs like "student_a3f"
        if not Student.query.filter_by(anonymous_id=anon_id).first():
            return anon_id

def generate_secret_token():
    """Generate a unique secret token"""
    return secrets.token_hex(8)

def get_student(student_token):
    """Get existing student or create new one with anonymous ID"""
    if not student_token:
        raise ValueError("Secret Submission Token is required but not provided.")
    
    student = Student.query.filter_by(secret_token=student_token).first()

    if not student:
        raise ValueError("Invalid secret submission token.")

    return student

def run_lint(file_path):
    file_ext = Path(file_path).suffix
    file_name = Path(file_path).name

    if file_ext == '.py':
        lint_command = ['python3', '-m', 'pylint', file_path]
        temp_output = subprocess.run(lint_command, capture_output=True, text=True)
        lint_errors = subprocess.run(['/usr/bin/grep', '-c', '-E', file_name], input=temp_output.stdout, capture_output=True, text=True).stdout
        lint_command = ['pylint']
    elif file_ext in ['.c', '.cpp']:
        lint_command = ['/usr/bin/cpplint', file_path]
        temp_output = subprocess.run(lint_command, capture_output=True, text=True)
        lint_errors = subprocess.run(['/usr/bin/grep', '-c', '-E', file_name + ':'], input=temp_output.stdout, capture_output=True, text=True).stdout
        lint_command = ['cpplint']
    else:
        lint_command = []
        lint_errors = -1

    return lint_errors, lint_command

def calculate_ranks_for_assignment(assignment_name):
    def rank_score(value, sorted_values):
        """Assign a score between 0 and 1 based on rank"""
        if len(sorted_values) == 1:
            return 1.0, 0.0
        rank = sorted_values.index(value)
        return 1 - (rank / (len(sorted_values) - 1)), rank

    latest_submission_times = db.session.query(
        Submission.student_id,
        func.max(Submission.submission_time).label("latest_time")
    ).filter(
        Submission.assignment == assignment_name
    ).group_by(
        Submission.student_id
    ).subquery()

    latest_submissions = db.session.query(Submission)\
        .join(latest_submission_times, 
            (Submission.student_id == latest_submission_times.c.student_id) & 
            (Submission.submission_time == latest_submission_times.c.latest_time))\
        .join(Student, Submission.student_id == Student.anonymous_id).all()
        # .filter(Student.debug == False)\

    if not latest_submissions:
        return []

    sorted_runtimes = sorted(s.runtime for s in latest_submissions)
    sorted_submission_times = sorted(s.submission_time.timestamp() for s in latest_submissions)
    sorted_lint_errors = sorted(s.lint_errors for s in latest_submissions)

    leaderboard_data = []
    for submission in latest_submissions:
        student_id = submission.student.anonymous_id
        runtime_score, runtime_rank = rank_score(submission.runtime, sorted_runtimes)
        time_score, time_rank = rank_score(submission.submission_time.timestamp(), sorted_submission_times)
        lint_score, lint_rank = rank_score(submission.lint_errors, sorted_lint_errors)
        code_score = submission.code_score / 100
        
        weighted_score = (
            0.4 * runtime_score +
            0.3 * lint_score +
            0.2 * time_score +
            0.1 * code_score
        )

        if 'exercise' in assignment_name:
            weighted_score *= 0.25
        
        leaderboard_data.append({
            'student_id': student_id,
            'total_score': weighted_score,
            'runtime_rank': runtime_rank + 1,
            'time_rank': time_rank + 1,
            'lint_rank': lint_rank + 1,
            'code_score': code_score,
            'submission_time': submission.submission_time
        })

    return leaderboard_data

@app.route('/assignment/<name>')
def assignment_view(name):
    """View all submissions for an assignment"""
    # Get all submissions for the assignment, ordered by submission time descending
    all_submissions = Submission.query\
        .join(Student, Submission.student_id == Student.anonymous_id)\
        .filter(Submission.assignment == name)\
        .order_by(Submission.submission_time.desc())\
        .all()

    # Calculate overall stats
    submission_count = len(all_submissions)
    avg_code_score = sum(s.code_score for s in all_submissions) / submission_count if submission_count else 0.0
    avg_runtime = sum(s.runtime for s in all_submissions) / submission_count if submission_count else 0.0
    avg_lint_errors = sum(s.lint_errors for s in all_submissions) / submission_count if submission_count else 0.0
    fastest_runtime = min(s.runtime for s in all_submissions) if submission_count else 0.0
    highest_code_score = max(s.code_score for s in all_submissions) if submission_count else 0.0

    # Prepare submissions with display names, leaderboard points, and ranks
    for sub in all_submissions:
        display_name = sub.student.net_id if sub.student.display_net_id else sub.student.anonymous_id
        sub.display_name = display_name

    # Use the calculate_ranks_for_assignment function to get ranked submissions, excluding debug students
    lbd = calculate_ranks_for_assignment(name)

    for sub in all_submissions:

        for lbd_sub in lbd:
            if sub.submission_time == lbd_sub['submission_time']:
                sub.is_most_recent = True

                sub.leaderboard_points = lbd_sub['total_score']
                sub.runtime_rank = lbd_sub['runtime_rank']
                sub.lint_rank = lbd_sub['lint_rank']
                sub.time_rank = lbd_sub['time_rank']
                break

    # Pass all submissions and recent submissions with ranks to the template
    return render_template('assignment.html',
                           submissions=all_submissions,
                           assignment_name=name,
                           stats={
                               'submission_count': submission_count,
                               'avg_code_score': avg_code_score,
                               'avg_runtime': avg_runtime,
                               'avg_lint_errors': avg_lint_errors,
                               'fastest_runtime': fastest_runtime,
                               'highest_code_score': highest_code_score
                           })

@app.route('/assignments')
def index():
    """View all submissions with sorting options"""
    sort_by = request.args.get('sort', 'submission_time')
    order = request.args.get('order', 'desc')
    
    # Build the query
    query = Submission.query
    
    # Apply sorting
    if hasattr(Submission, sort_by):
        sort_attr = getattr(Submission, sort_by)
        if order == 'desc':
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
    
    submissions = query.all()
    return render_template('index.html', submissions=submissions)

@app.route('/student/<name>', methods=['GET', 'POST'])
def student_view(name):
    """View submissions for a specific student and allow real name display"""
    student = Student.query.filter_by(anonymous_id=name).first()
    if not student:
        return jsonify({"error": "Student not found"}), 404

    # Create form for displaying username
    form = UpdateProfileForm()
    if form.validate_on_submit():
        if form.secret_token.data == student.secret_token:
            student.display_net_id = form.display_net_id.data
            db.session.commit()
            flash("Preferences updated successfully!", "success")
            return redirect(url_for('student_view', name=name))
        else:
            form.secret_token.errors.append("Invalid secret token.")

    form.display_net_id.data = student.display_net_id

    # Fetch the most recent submission for each student for each assignment
    latest_submission_times = db.session.query(
        Submission.student_id,
        Submission.assignment,
        func.max(Submission.submission_time).label("latest_time")
    ).group_by(
        Submission.student_id, Submission.assignment
    ).subquery()

    recent_submissions = db.session.query(Submission)\
        .join(latest_submission_times, 
              (Submission.student_id == latest_submission_times.c.student_id) & 
              (Submission.assignment == latest_submission_times.c.assignment) & 
              (Submission.submission_time == latest_submission_times.c.latest_time))\
        .all()

    # Fetch all submissions for the student
    submissions = Submission.query.filter_by(student_id=name)\
                                .order_by(Submission.submission_time.desc())\
                                .all()

    # Filter recent submissions for the same assignment
    recent_assignment_submissions = [s for s in submissions if s in recent_submissions]

    for sub in submissions:
        if sub in recent_assignment_submissions:
            sub.is_most_recent = True
            lbd = calculate_ranks_for_assignment(sub.assignment)

            for lbd_sub in lbd:
                if lbd_sub['student_id'] == sub.student_id:
                    sub.runtime_rank = lbd_sub['runtime_rank']
                    sub.lint_rank = lbd_sub['lint_rank']
                    sub.time_rank = lbd_sub['time_rank']
                    sub.leaderboard_points = lbd_sub['total_score']
                    break

    # Calculate averages
    if submissions:
        avg_code_score = sum(s.code_score for s in submissions) / len(submissions)
        avg_runtime = sum(s.runtime for s in submissions) / len(submissions)
        avg_lint_errors = sum(s.lint_errors for s in submissions) / len(submissions)
    else:
        avg_code_score = avg_runtime = avg_lint_errors = 0.0
        
    for submission in submissions:
        submission.submission_time = convert_to_est(submission.submission_time)
    
    # Pass the form to the template
    return render_template('student.html', form=form, submissions=submissions, avg_code_score=avg_code_score, avg_runtime=avg_runtime, avg_lint_errors=avg_lint_errors, display_name=student.net_id if student.display_net_id else student.anonymous_id)

def load_due_dates():
    """Load challenge due dates from JSON file."""
    with open('static/json/challenge_due_dates.json') as f:
        return json.load(f)

@app.route('/')
def leaderboard():
    leaderboard_data = calculate_leaderboard_data()
    assignments = db.session.query(Submission.assignment).distinct().all()
    due_dates = load_due_dates()  # Load due dates
    return render_template('leaderboard.html', 
                           leaderboard=leaderboard_data,
                           total_assignments=len(assignments),
                           due_dates=due_dates)  # Pass due dates to template

@app.route('/leaderboard_data')
def leaderboard_data():
    leaderboard_data = calculate_leaderboard_data()
    return jsonify(leaderboard_data)

@app.route('/admin', methods=['GET', 'POST'])
def view_mappings():
    form = AdminAccessForm()
    if form.validate_on_submit() or 'admin_token' in session:
        if 'admin_token' not in session:
            admin_token = AdminToken.query.first()
            if admin_token and form.secret_token.data == admin_token.token:
                session['admin_token'] = form.secret_token.data
            else:
                form.secret_token.errors.append("Invalid secret token.")
                return render_template('admin_access.html', form=form)

        if request.method == 'POST':
            if 'student_id' in request.form:
                student_id = request.form.get('student_id')
                student = Student.query.filter_by(anonymous_id=student_id).first()
                if student:
                    student.debug = not student.debug
                    db.session.commit()
                    flash("Debug status updated successfully!", "success")
            elif 'assignment_id' in request.form:
                assignment_id = request.form.get('assignment_id')
                is_open = 'is_open' in request.form
                deadline = request.form.get('deadline')

                assignment = Assignment.query.get(assignment_id)
                if assignment:
                    assignment.is_open = is_open
                    assignment.deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M:%S')
                    db.session.commit()
                    flash("Assignment updated successfully!", "success")
            elif 'action' in request.form:
                action = request.form.get('action')
                if action == 'open_all_assignments':
                    Assignment.query.update({Assignment.is_open: True})
                    db.session.commit()
                    flash("All assignments opened successfully!", "success")
                elif action == 'close_all_assignments':
                    Assignment.query.update({Assignment.is_open: False})
                    db.session.commit()
                    flash("All assignments closed successfully!", "success")
                elif action == 'open_all_exercises':
                    Assignment.query.filter(Assignment.name.like('%exercise%')).update({Assignment.is_open: True})
                    db.session.commit()
                    flash("All exercises opened successfully!", "success")
                elif action == 'close_all_exercises':
                    Assignment.query.filter(Assignment.name.like('%exercise%')).update({Assignment.is_open: False})
                    db.session.commit()
                    flash("All exercises closed successfully!", "success")
            elif 'exercise_id' in request.form:
                exercise_id = request.form.get('exercise_id')
                is_open = 'is_open' in request.form
                deadline = request.form.get('deadline')

                exercise = Assignment.query.get(exercise_id)
                if exercise:
                    exercise.is_open = is_open
                    exercise.deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M:%S')
                    db.session.commit()
                    flash("Exercise updated successfully!", "success")
            elif 'netid' in request.form:
                net_id = request.form.get('netid')
                # Generate a unique anonymous ID and secret token
                anonymous_id = generate_anonymous_id()
                secret_token = generate_secret_token()

                # Create a new student record
                new_student = Student(
                    net_id=net_id,
                    anonymous_id=anonymous_id,
                    secret_token=secret_token
                )
                db.session.add(new_student)
                db.session.commit()
                flash("Student added successfully!", "success")

        mappings = {
            student.anonymous_id: [
                student.net_id,
                student.display_net_id,
                student.secret_token,
                student.debug
            ]
            for student in Student.query.all()
        }

        exercises = Assignment.query.filter(Assignment.name.like('%exercise%')).all()
        challenges = Assignment.query.filter(Assignment.name.like('%challenge%')).all()

        return render_template('admin_access.html', form=form, mappings=mappings, assignments=challenges, exercises=exercises)
    
    return render_template('admin_access.html', form=form)

@app.context_processor
def inject_data():
    students = Student.query.all()
    assignments = db.session.query(Submission.assignment).distinct().all()
    return dict(students=students, assignments=[a[0] for a in assignments])

def calculate_leaderboard_data():
    def rank_score(value, sorted_values):
        """Assign a score between 0 and 1 based on rank"""
        if len(sorted_values) == 1:
            return 1.0
        rank = sorted_values.index(value)
        return 1 - (rank / (len(sorted_values) - 1))

    # Query the database for assignments that are due
    today = datetime.now(pytz.timezone('US/Eastern')).date()
    due_assignments = Assignment.query.filter(Assignment.deadline <= today, Assignment.is_open == True).all()

    total_due_assignments = len(due_assignments)

    student_scores = {}
    debug_scores = {}

    # Get all distinct assignments
    all_assignments = db.session.query(Submission.assignment).distinct().all()
    all_assignments = [a[0] for a in all_assignments]

    for assignment in all_assignments:
        latest_submission_times = db.session.query(
            Submission.student_id,
            func.max(Submission.submission_time).label("latest_time")
        ).filter(
            Submission.assignment == assignment
        ).group_by(
            Submission.student_id
        ).subquery()

        latest_submissions = db.session.query(Submission)\
            .join(latest_submission_times, 
                (Submission.student_id == latest_submission_times.c.student_id) & 
                (Submission.submission_time == latest_submission_times.c.latest_time))\
            .all()

        if not latest_submissions:
            continue

        sorted_runtimes = sorted(s.runtime for s in latest_submissions)
        sorted_submission_times = sorted(s.submission_time.timestamp() for s in latest_submissions)
        sorted_lint_errors = sorted(s.lint_errors for s in latest_submissions)

        for submission in latest_submissions:
            student_id = submission.student.anonymous_id
            scores_dict = debug_scores if submission.student.debug else student_scores

            if student_id not in scores_dict:
                scores_dict[student_id] = {
                    'total_score': 0, 
                    'exercises_completed': 0,
                    'challenges_completed': 0,
                    'assignment_count': 0,
                    'total_runtime': 0,
                    'total_submission_time': 0,
                    'total_lint_errors': 0,
                    'tags': [],
                    'is_debug': submission.student.debug
                }

            runtime_rank = rank_score(submission.runtime, sorted_runtimes)
            time_rank = rank_score(submission.submission_time.timestamp(), sorted_submission_times)
            lint_rank = rank_score(submission.lint_errors, sorted_lint_errors)
            code_score = submission.code_score / 100
            
            weighted_score = (
                0.4 * runtime_rank +
                0.3 * lint_rank +
                0.2 * time_rank +
                0.1 * code_score
            )

            if 'exercise' in assignment:
                weighted_score *= 0.25
                scores_dict[student_id]['exercises_completed'] += 1
            else:
                scores_dict[student_id]['challenges_completed'] += 1
            
            scores_dict[student_id]['total_score'] += weighted_score
            scores_dict[student_id]['total_runtime'] += submission.runtime
            # scores_dict[student_id]['total_submission_time'] += submission.submission_time.timestamp()
            scores_dict[student_id]['total_submission_time'] += time_rank
            scores_dict[student_id]['total_lint_errors'] += submission.lint_errors

    # Mark students who haven't completed at least 50% of the due assignments as debug
    min_assignments_required = total_due_assignments * 0.5
    for student_id, scores in {**student_scores, **debug_scores}.items():
        if scores['challenges_completed'] < min_assignments_required:
            scores['is_debug'] = True

    leaderboard_data = []
    for student_id, scores in {**student_scores, **debug_scores}.items():
        student = Student.query.filter_by(anonymous_id=student_id).first()
        display_name = student.net_id if student.display_net_id else student.anonymous_id

        avg_score = scores['total_score'] / (scores['challenges_completed'] + scores['exercises_completed'])
        avg_runtime = scores['total_runtime'] / (scores['challenges_completed'] + scores['exercises_completed'])
        avg_submission_time = scores['total_submission_time'] / (scores['challenges_completed'] + scores['exercises_completed'])
        avg_lint_errors = scores['total_lint_errors'] / (scores['challenges_completed'] + scores['exercises_completed'])
        
        leaderboard_data.append({
            'student_id': student_id,
            'display_name': display_name,
            'average_score': avg_score,
            'total_score': scores['total_score'],
            'exercises_completed': scores['exercises_completed'],
            'challenges_completed': scores['challenges_completed'],
            'avg_runtime': avg_runtime,
            'avg_submission_time': avg_submission_time,
            'avg_lint_errors': avg_lint_errors,
            'tags': scores['tags'],
            'is_debug': scores['is_debug']
        })

    leaderboard_data.sort(key=lambda x: x['total_score'], reverse=True)

    position = {
        0: 1,
        1: 2,
        2: 3,
        3: 4,
        4: 5
    }

    debug_count = 0
    for i, entry in enumerate(leaderboard_data):
        if entry['is_debug']:
            debug_count += 1
            entry['position'] = '*'
        else:
            entry['position'] = position.get(i - debug_count, i - debug_count + 1)

    if leaderboard_data:
        # Find the first non-debug student with the minimum runtime
        min_runtime_student = next((student for student in sorted(leaderboard_data, key=lambda x: x['avg_runtime']) if not student['is_debug']), None)
        
        # Find the first non-debug student with the earliest submission time
        earliest_submission_student = next((student for student in sorted(leaderboard_data, key=lambda x: x['avg_submission_time']) if not student['is_debug']), None)
        
        # Find the first non-debug student with the lowest lint errors
        lowest_lint_errors_student = next((student for student in sorted(leaderboard_data, key=lambda x: x['avg_lint_errors']) if not student['is_debug']), None)
        
        # Assign tags if the students are found
        if min_runtime_student:
            min_runtime_student['tags'].append('Fastest Coder')
        if earliest_submission_student:
            earliest_submission_student['tags'].append('Early Bird')
        if lowest_lint_errors_student:
            lowest_lint_errors_student['tags'].append('Lint Master')

    return leaderboard_data

@app.route('/recent_submissions')
def recent_submissions():
    try:
        # Fetch the most recent submissions, limit to the last 5 for example
        recent_subs = Submission.query.order_by(Submission.submission_time.desc()).limit(5).all()

        # Convert submission times to EST
        for submission in recent_subs:
            submission.submission_time = convert_to_est(submission.submission_time)

        # Convert submissions to a list of dictionaries
        recent_subs_data = [{
            'submission_time': sub.submission_time.strftime('%m-%d %-I:%M:%S %p'),
            'student_name': sub.student.net_id if sub.student.display_net_id else sub.student.anonymous_id,
            'student_id': sub.student.anonymous_id,  # Always include for the link
            'assignment': sub.assignment,
            'code_score': sub.code_score,
            'runtime': sub.runtime,
            'lint_errors': sub.lint_errors,
            'status': sub.status
        } for sub in recent_subs]

        return jsonify(recent_subs_data)
    except Exception as e:
        app.logger.error(f"Error fetching recent submissions: {e}")
        return jsonify({"error": "An error occurred while fetching recent submissions."}), 500

def convert_to_est(utc_dt):
    est = pytz.timezone('US/Eastern')

    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    return utc_dt.astimezone(est)

@app.route('/submissions_per_day')
def submissions_per_day():
    try:
        # Get the range parameter from the request
        range_param = request.args.get('range', '1W')  # Default to 1 week if not specified

        # Determine the start date based on the range parameter
        today = datetime.now(pytz.timezone('US/Eastern')).date()
        if range_param == '1D':
            start_date = today - timedelta(days=1)
        elif range_param == '3D':
            start_date = today - timedelta(days=3)
        elif range_param == '1W':
            start_date = today - timedelta(weeks=1)
        elif range_param == '2W':
            start_date = today - timedelta(weeks=2)
        elif range_param == '1M':
            start_date = today - timedelta(days=30)
        elif range_param == 'ALL':
            start_date = None  # No start date, include all data
        else:
            return jsonify({"error": "Invalid range parameter."}), 400

        # Query submissions based on the start date
        if start_date:
            submissions = Submission.query.filter(Submission.submission_time >= start_date).all()
        else:
            submissions = Submission.query.all()

        # Count successful and unsuccessful submissions per day
        submissions_count = defaultdict(lambda: {'success': 0, 'failure': 0})
        for sub in submissions:
            date = convert_to_est(sub.submission_time).date()
            if sub.status == 'Success':
                submissions_count[date]['success'] += 1
            else:
                submissions_count[date]['failure'] += 1

        # Prepare data for the chart, ensuring all days in the range are included
        chart_data = []
        current_date = start_date + timedelta(days=1) if start_date else min(submissions_count.keys()) + timedelta(days=1)
        while current_date <= today:
            chart_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'success': submissions_count[current_date]['success'],
                'failure': submissions_count[current_date]['failure']
            })
            current_date += timedelta(days=1)

        return jsonify(chart_data)
    except Exception as e:
        app.logger.error(f"Error fetching submissions per day: {e}")
        return jsonify({"error": "An error occurred while fetching submissions per day."}), 500

@app.route('/details')
def details():
    """Render the details page."""
    return render_template('details.html')

@app.route('/code/<assignment>', methods=['POST'])
def proxy_code(assignment):
    """Proxy code submissions to Dredd and record metadata"""
    try:
        # Check if the assignment is accepting submissions
        assignment_record = Assignment.query.filter_by(name=assignment).first()
        if not assignment_record or not assignment_record.is_open:
            return jsonify({"error": "Submissions for this assignment are currently closed."}), 403

        dredd_slug = request.headers.get('X-Dredd-Code-Slug', 'code')
        student_token = request.headers.get('X-Submission-Token')

        anon_student = get_student(student_token).anonymous_id

        # Get the source file from the request
        source_file = request.files['source']

        # Create a temporary file with the same extension as the uploaded file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(source_file.filename).suffix)
        try:
            # Save the uploaded file to the temporary file
            source_file.save(temp_file.name)
            temp_file.close()
            # Run the linting process
            lint_errors = run_lint(temp_file.name)
            # Dredd Configuration
            DREDD_CODE_URL = f'https://dredd.h4x0r.space/{dredd_slug}/cse-30872-fa24/'
            print(DREDD_CODE_URL + assignment)
            # Read the file again for forwarding
            with open(temp_file.name, 'rb') as f:
                response = requests.post(DREDD_CODE_URL + assignment,
                                         files={'source': (source_file.filename, f)})
                dredd_result = response.json()

            print(dredd_result)
            # Parse metrics from Dredd's response
            metrics = parse_dredd_response(dredd_result)
        finally:
            # Ensure the temporary file is deleted
            os.unlink(temp_file.name)

        # Record the submission
        submission = Submission(
            student_id=anon_student,
            assignment=assignment,
            status=metrics['result'],
            code_score=metrics['code_score'],
            runtime=metrics['runtime'],
            lint_errors=lint_errors[0],  # Use the lint score from the script
        )
        
        db.session.add(submission)
        db.session.commit()
        
        # Return Dredd's original response
        return jsonify(dredd_result), response.status_code
        
    except Exception as e:
        print(request.files['source'])
        return jsonify({"error": str(e)}), 500

@app.route('/online_editor', methods=['GET'])
def online_editor():
    return render_template('editor.html')

@app.route('/list_assignments', methods=['GET'])
def list_assignments():
    # Assuming assignments are stored in a specific directory
    assignments_dir = 'static/exercises'
    assignments = []

    # Walk through the directory to find assignments
    for root, dirs, files in os.walk(assignments_dir):
        for file in files:
            if file == 'template.py':  # Assuming each assignment has a template.py
                assignment_path = os.path.relpath(root, assignments_dir)
                assignments.append(assignment_path)

    assignments = sorted(assignments)
    return jsonify(assignments)

@app.route('/get_template/<path:assignment>', methods=['GET'])
def get_template(assignment):
    # Construct the path to the template file
    template_path = os.path.join('static/exercises', assignment, 'template.py')
    return send_file(template_path)

if __name__ == '__main__':
    with app.app_context():
        populate_student_table()  # Populate the student table
    app.run(host='0.0.0.0', debug=True, port=9696)
