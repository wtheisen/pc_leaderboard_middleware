from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func
from datetime import datetime
import requests
import json
import os
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
db = SQLAlchemy(app)

# Dredd Configuration
DREDD_CODE_SLUG = 'debug' if bool(os.environ.get('DEBUG', False)) else 'code'
DREDD_CODE_URL = f'https://dredd.h4x0r.space/{DREDD_CODE_SLUG}/cse-30872-fa24/'

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    github_id = db.Column(db.String(100), unique=True, nullable=False)  # Real GitHub username
    anonymous_id = db.Column(db.String(8), unique=True, nullable=False)  # Public identifier

    # Define the relationship to Submissions
    submissions = db.relationship('Submission', back_populates='student', lazy=True)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(8), db.ForeignKey('student.anonymous_id'), nullable=False)  # Link to anonymous_id
    assignment = db.Column(db.String(100), nullable=False)
    code_score = db.Column(db.Float)
    runtime = db.Column(db.Float)  # in seconds
    lint_score = db.Column(db.Float)
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)

    # Define the relationship back to Student
    student = db.relationship('Student', back_populates='submissions', primaryjoin="Submission.student_id == Student.anonymous_id")

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,  # This now stores the anonymized ID
            'assignment': self.assignment,
            'code_score': self.code_score,
            'runtime': self.runtime,
            'lint_score': self.lint_score,
            'submission_time': self.submission_time.strftime('%Y-%m-%d %H:%M:%S')
        }

# Create the database tables
with app.app_context():
    db.create_all()

def parse_dredd_response(response_data):
    """Extract relevant metrics from Dredd's response"""
    result = {
        'code_score': 0.0,
        'runtime': 0.0,
        'lint_score': 0.0
    }
    
    try:
        # Extract code score - assuming it's in the main score field
        result['code_score'] = float(response_data.get('score', 0.0))
        
        # Parse runtime from stdout if available
        stdout = response_data.get('stdout', '')
        if 'Runtime:' in stdout:
            runtime_line = [line for line in stdout.split('\n') if 'Runtime:' in line][0]
            result['runtime'] = float(runtime_line.split(':')[1].strip().split()[0])
            
        # Parse lint score if available
        if 'lint' in response_data:
            result['lint_score'] = float(response_data['lint'])
            
    except (ValueError, IndexError, KeyError) as e:
        print(f"Error parsing Dredd response: {e}")
        
    return result

def generate_anonymous_id():
    """Generate a unique 8-character anonymous ID"""
    while True:
        anon_id = f"{secrets.token_hex(3)}"  # Creates IDs like "student_a3f"
        if not Student.query.filter_by(anonymous_id=anon_id).first():
            return anon_id

def get_or_create_student(github_id):
    """Get existing student or create new one with anonymous ID"""
    student = Student.query.filter_by(github_id=github_id).first()
    if not student:
        student = Student(
            github_id=github_id,
            anonymous_id=generate_anonymous_id()
        )
        db.session.add(student)
        db.session.commit()
    return student

@app.route('/code/<assignment>', methods=['POST'])
def proxy_code(assignment):
    """Proxy code submissions to Dredd and record metadata"""
    try:
        student_github_username = request.headers.get('X-GitHub-User')
        print(student_github_username)
        anon_student = get_or_create_student(student_github_username).anonymous_id
        print(anon_student)

        # Forward to Dredd
        source_file = request.files['source']
        response = requests.post(DREDD_CODE_URL + assignment,
                                files={'source': (source_file.filename, source_file.stream)}) 
        dredd_result = response.json()
        
        # Parse metrics from Dredd's response
        metrics = parse_dredd_response(dredd_result)
        
        # Record the submission
        submission = Submission(
            student_id=anon_student,
            assignment=assignment,
            code_score=metrics['code_score'],
            runtime=metrics['runtime'],
            lint_score=metrics['lint_score']
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

@app.route('/student/<name>')
def student_view(name):
    """View submissions for a specific student"""
    submissions = Submission.query.filter_by(student_id=name)\
                                .order_by(Submission.submission_time.desc())\
                                .all()
    
    # Calculate averages
    if submissions:
        avg_code_score = sum(s.code_score for s in submissions) / len(submissions)
        avg_runtime = sum(s.runtime for s in submissions) / len(submissions)
        avg_lint_score = sum(s.lint_score for s in submissions) / len(submissions)
    else:
        avg_code_score = avg_runtime = avg_lint_score = 0.0
        
    return render_template('student.html',
                         submissions=submissions,
                         student_id=name,
                         avg_code_score=avg_code_score,
                         avg_runtime=avg_runtime,
                         avg_lint_score=avg_lint_score)

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
            'avg_lint_score': sum(s.lint_score for s in submissions) / len(submissions),
            'fastest_runtime': min(s.runtime for s in submissions),
            'highest_code_score': max(s.code_score for s in submissions),
            'submission_count': len(submissions)
        }
    else:
        stats = {
            'avg_code_score': 0.0,
            'avg_runtime': 0.0,
            'avg_lint_score': 0.0,
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
    
    def normalize_score(value, min_val, max_val):
        """Normalize a value between 0 and 1"""
        if max_val == min_val:
            return 1.0
        return (value - min_val) / (max_val - min_val)

    # Get all assignments
    assignments = db.session.query(Submission.assignment).distinct().all()
    assignments = [a[0] for a in assignments]
    
    # Calculate scores per student per assignment
    student_scores = {}
    
    for assignment in assignments:
        # Get the latest submission for each student for this assignment
        # latest_submissions = db.session.query(Submission)\
        #     .join(Student)\
        #     .filter(Submission.assignment == assignment)\
        #     .order_by(Student.anonymous_id, Submission.submission_time.desc())\
        #     .distinct(Student.anonymous_id)\
        #     .all()
            
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
            
        # Get min/max values for normalization using only the latest submissions
        min_runtime = min(s.runtime for s in latest_submissions)
        max_runtime = max(s.runtime for s in latest_submissions)
        min_time = min(s.submission_time.timestamp() for s in latest_submissions)
        max_time = max(s.submission_time.timestamp() for s in latest_submissions)
        
        for submission in latest_submissions:
            student_id = submission.student.anonymous_id
            if student_id not in student_scores:
                student_scores[student_id] = {'total_score': 0, 'assignment_count': 0}

            # Normalize all scores between 0 and 1
            code_score = submission.code_score / 100
            time_score = 1 - normalize_score(submission.submission_time.timestamp(), min_time, max_time)
            runtime_score = 1 - normalize_score(submission.runtime, min_runtime, max_runtime)
            lint_score = submission.lint_score / 100
            
            weighted_score = (
                0.4 * runtime_score +
                0.3 * time_score +
                0.2 * lint_score +
                0.1 * code_score
            )
            
            student_scores[student_id]['total_score'] += weighted_score
            student_scores[student_id]['assignment_count'] += 1
    
    # Calculate average scores and create leaderboard
    leaderboard_data = []
    for student_id, scores in student_scores.items():
        avg_score = scores['total_score'] / scores['assignment_count']
        leaderboard_data.append({
            'student_id': student_id,
            'average_score': avg_score,
            'total_score': scores['total_score'],
            'assignments_completed': scores['assignment_count']
        })
    
    # Sort by average score
    leaderboard_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Assign bonus points
    bonus_points = {
        0: 4.0,  # First place
        1: 2.0,  # Second place
        2: 1.0,  # Third place
        3: 1.0,  # Fourth place
        4: 1.0   # Fifth place
    }
    
    # Add bonus points to entries
    for i, entry in enumerate(leaderboard_data):
        entry['bonus_points'] = bonus_points.get(i, 0.0)
    
    return render_template('leaderboard.html', 
                         leaderboard=leaderboard_data,
                         total_assignments=len(assignments))

@app.route('/admin/cutekitties', methods=['GET'])
def view_mappings():
    mappings = Student.query.all()
    return jsonify({
        student.anonymous_id: student.github_id 
        for student in mappings
    })

if __name__ == '__main__':
    app.run(debug=True)
