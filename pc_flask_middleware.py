from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func
from datetime import datetime
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

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')  # Use a secure key
db = SQLAlchemy(app)


class AdminToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_id = db.Column(db.String(100), unique=True, nullable=False)  # Real GitHub username
    anonymous_id = db.Column(db.String(8), unique=True, nullable=False)  # Public identifier
    real_name = db.Column(db.String(100), nullable=True)  # Real name of the student
    display_real_name = db.Column(db.Boolean, default=False)  # Preference for displaying real name
    secret_token = db.Column(db.String(32), unique=True, nullable=False)  # Secret token for verification

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
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)

    # Define the relationship back to Student
    student = db.relationship('Student', back_populates='submissions', primaryjoin="Submission.student_id == Student.anonymous_id")

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,  # This now stores the anonymized ID
            'status': self.status,
            'assignment': self.assignment,
            'code_score': self.code_score,
            'runtime': self.runtime,
            'lint_errors': self.lint_errors,
            'submission_time': self.submission_time.strftime('%Y-%m-%d %H:%M:%S')
        }

class UpdateProfileForm(FlaskForm):
    real_name = StringField('Real Name', validators=[DataRequired()])
    display_real_name = BooleanField('Display Real Name on Leaderboard')
    secret_token = StringField('Secret Token', validators=[DataRequired()])
    submit = SubmitField('Update Profile')

class AdminAccessForm(FlaskForm):
    secret_token = StringField('Admin Secret Token', validators=[DataRequired()])
    submit = SubmitField('Access Admin Page')

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

def generate_anonymous_id():
    """Generate a unique 8-character anonymous ID"""
    while True:
        anon_id = f"{secrets.token_hex(3)}"  # Creates IDs like "student_a3f"
        if not Student.query.filter_by(anonymous_id=anon_id).first():
            return anon_id

def generate_secret_token():
    """Generate a unique secret token"""
    return secrets.token_hex(16)

def get_or_create_student(github_id):
    """Get existing student or create new one with anonymous ID"""
    if not github_id:
        raise ValueError("GitHub ID is required but not provided.")
    
    student = Student.query.filter_by(github_id=github_id).first()
    if not student:
        student = Student(
            github_id=github_id,
            anonymous_id=generate_anonymous_id(),
            secret_token=generate_secret_token()
        )
        db.session.add(student)
        db.session.commit()
    return student

def run_lint(file_path):
    file_ext = Path(file_path).suffix
    file_name = Path(file_path).name
    print(f"File name: {file_name}")

    if file_ext == '.py':
        temp_output =  subprocess.run(['python3', '-m', 'pylint', file_path], capture_output=True, text=True)
        return subprocess.run(['/usr/bin/grep', '-c', '-E', file_name], input=temp_output.stdout, capture_output=True, text=True).stdout
    elif file_ext in ['.c', '.cpp']:
        temp_output = subprocess.run(['/usr/bin/cpplint', file_path], capture_output=True, text=True)
        return subprocess.run(['/usr/bin/grep', '-c', '-E', file_name + ':'], input=temp_output.stdout, capture_output=True, text=True).stdout
    return -1

@app.route('/code/<assignment>', methods=['POST'])
def proxy_code(assignment):
    """Proxy code submissions to Dredd and record metadata"""
    try:
        dredd_slug = request.headers.get('X-Dredd-Code-Slug')
        student_github_username = request.headers.get('X-GitHub-User')
        anon_student = get_or_create_student(student_github_username).anonymous_id

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

            # Read the file again for forwarding
            with open(temp_file.name, 'rb') as f:
                response = requests.post(DREDD_CODE_URL + assignment,
                                         files={'source': (source_file.filename, f)})
                dredd_result = response.json()

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
            lint_errors=lint_errors  # Use the lint score from the script
        )
        
        db.session.add(submission)
        db.session.commit()
        
        # Return Dredd's original response
        return jsonify(dredd_result), response.status_code
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    form = UpdateProfileForm()
    if form.validate_on_submit():
        if form.secret_token.data == student.secret_token:
            student.real_name = form.real_name.data
            student.display_real_name = form.display_real_name.data
            db.session.commit()
            return redirect(url_for('student_view', name=name))
        else:
            form.secret_token.errors.append("Invalid secret token.")

    form.real_name.data = student.real_name
    form.display_real_name.data = student.display_real_name

    submissions = Submission.query.filter_by(student_id=name)\
                                .order_by(Submission.submission_time.desc())\
                                .all()
    
    # Calculate averages
    if submissions:
        avg_code_score = sum(s.code_score for s in submissions) / len(submissions)
        avg_runtime = sum(s.runtime for s in submissions) / len(submissions)
        avg_lint_errors = sum(s.lint_errors for s in submissions) / len(submissions)
    else:
        avg_code_score = avg_runtime = avg_lint_errors = 0.0
        
    return render_template('student.html',
                         submissions=submissions,
                         student_id=name,
                         avg_code_score=avg_code_score,
                         avg_runtime=avg_runtime,
                         avg_lint_errors=avg_lint_errors,
                         form=form)

@app.route('/assignment/<name>')
def assignment_view(name):
    """View all submissions for an assignment"""
    submissions = Submission.query.filter_by(assignment=name)\
                                .order_by(Submission.code_score.desc())\
                                .all()
    
    # Calculate statistics
    if submissions:
        stats = {
            'avg_code_score': sum(s.code_score for s in submissions) / len(submissions),
            'avg_runtime': sum(s.runtime for s in submissions) / len(submissions),
            'avg_lint_errors': sum(s.lint_errors for s in submissions) / len(submissions),
            'fastest_runtime': min(s.runtime for s in submissions),
            'highest_code_score': max(s.code_score for s in submissions),
            'submission_count': len(submissions)
        }
    else:
        stats = {
            'avg_code_score': 0.0,
            'avg_runtime': 0.0,
            'avg_lint_errors': 0.0,
            'fastest_runtime': 0.0,
            'highest_code_score': 0.0,
            'submission_count': 0
        }
    
    return render_template('assignment.html',
                         submissions=submissions,
                         assignment_name=name,
                         stats=stats)

@app.route('/')
def leaderboard():
    """Calculate weighted scores and distribute bonus points"""
    
    def rank_score(value, sorted_values):
        """Assign a score between 0 and 1 based on rank"""
        if len(sorted_values) == 1:
            return 1.0  # If there's only one value, it gets the maximum score
        rank = sorted_values.index(value)
        return 1 - (rank / (len(sorted_values) - 1))

    # Get all assignments
    assignments = db.session.query(Submission.assignment).distinct().all()
    assignments = [a[0] for a in assignments]
    
    # Calculate scores per student per assignment
    student_scores = {}
    
    for assignment in assignments:
        # Subquery to get the latest submission time for each student for the given assignment
        latest_submission_times = db.session.query(
            Submission.student_id,
            func.max(Submission.submission_time).label("latest_time")
        ).filter(
            Submission.assignment == assignment
        ).group_by(
            Submission.student_id
        ).subquery()

        # Main query: Join with the subquery to get the full Submission data
        latest_submissions = db.session.query(Submission)\
            .join(latest_submission_times, 
                (Submission.student_id == latest_submission_times.c.student_id) & 
                (Submission.submission_time == latest_submission_times.c.latest_time))\
            .all()

        if not latest_submissions:
            continue
        
        # Sort submissions for ranking
        sorted_runtimes = sorted(s.runtime for s in latest_submissions)
        sorted_submission_times = sorted(s.submission_time.timestamp() for s in latest_submissions)
        sorted_lint_errors = sorted(s.lint_errors for s in latest_submissions)

        for submission in latest_submissions:
            student_id = submission.student.anonymous_id
            if student_id not in student_scores:
                student_scores[student_id] = {
                    'total_score': 0, 
                    'assignment_count': 0,
                    'total_runtime': 0,
                    'total_submission_time': 0,
                    'total_lint_errors': 0,
                    'tags': []
                }

            # Rank-based scores
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
            
            student_scores[student_id]['total_score'] += weighted_score
            student_scores[student_id]['assignment_count'] += 1
            student_scores[student_id]['total_runtime'] += submission.runtime
            student_scores[student_id]['total_submission_time'] += submission.submission_time.timestamp()
            student_scores[student_id]['total_lint_errors'] += submission.lint_errors
    
    # Calculate average scores and create leaderboard
    leaderboard_data = []
    for student_id, scores in student_scores.items():
        student = Student.query.filter_by(anonymous_id=student_id).first()
        display_name = student.real_name if student.display_real_name else student.anonymous_id

        avg_score = scores['total_score'] / scores['assignment_count']
        avg_runtime = scores['total_runtime'] / scores['assignment_count']
        avg_submission_time = scores['total_submission_time'] / scores['assignment_count']
        avg_lint_errors = scores['total_lint_errors'] / scores['assignment_count']
        
        leaderboard_data.append({
            'student_id': student_id,
            'display_name': display_name,
            'average_score': avg_score,
            'total_score': scores['total_score'],
            'assignments_completed': scores['assignment_count'],
            'avg_runtime': avg_runtime,
            'avg_submission_time': avg_submission_time,
            'avg_lint_errors': avg_lint_errors,
            'tags': scores['tags']
        })
    
    # Sort by average score
    leaderboard_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Assign bonus points
    position = {
        0: 1,  # First place
        1: 2,  # Second place
        2: 3,  # Third place
        3: 4,  # Fourth place
        4: 5   # Fifth place
    }
    
    # Add bonus points to entries
    for i, entry in enumerate(leaderboard_data):
        entry['position'] = position.get(i, 0)
    
    # Determine tags
    if leaderboard_data:
        min_runtime_student = min(leaderboard_data, key=lambda x: x['avg_runtime'])
        earliest_submission_student = min(leaderboard_data, key=lambda x: x['avg_submission_time'])
        lowest_lint_errors_student = min(leaderboard_data, key=lambda x: x['avg_lint_errors'])
        
        min_runtime_student['tags'].append('Fastest Coder')
        earliest_submission_student['tags'].append('Early Bird')
        lowest_lint_errors_student['tags'].append('Lint Master')
    
    return render_template('leaderboard.html', 
                         leaderboard=leaderboard_data,
                         total_assignments=len(assignments))

@app.route('/admin', methods=['GET', 'POST'])
def view_mappings():
    form = AdminAccessForm()
    if form.validate_on_submit():
        # Retrieve the token from the database
        admin_token = AdminToken.query.first()
        if admin_token and form.secret_token.data == admin_token.token:
            mappings = {
                student.anonymous_id: [
                    student.github_id,
                    student.real_name,
                    student.display_real_name,
                    student.secret_token
                ]
                for student in Student.query.all()
            }
            return render_template('admin_access.html', form=form, mappings=mappings)
        else:
            form.secret_token.errors.append("Invalid secret token.")
    
    return render_template('admin_access.html', form=form)

@app.context_processor
def inject_data():
    students = Student.query.all()
    assignments = db.session.query(Submission.assignment).distinct().all()
    return dict(students=students, assignments=[a[0] for a in assignments])

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=9696)
