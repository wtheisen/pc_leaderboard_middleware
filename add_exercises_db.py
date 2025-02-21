import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

# Initialize Flask app and SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
db = SQLAlchemy(app)

# Define the Assignment model
class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_open = db.Column(db.Boolean, default=True)  # Whether submissions are open
    deadline = db.Column(db.DateTime, nullable=False)  # Deadline for submissions
    description = db.Column(db.Text, nullable=True)  # Optional description

def get_exercise_templates(directory):
    """Retrieve exercise names from the directory structure."""
    exercise_templates = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == 'template.py':  # Check for template files
                exercise_name = os.path.basename(root)
                exercise_templates.append({
                    "name": exercise_name,
                    "is_open": True,
                    "deadline": datetime.now() + timedelta(days=30),
                    "description": f"Description for {exercise_name}"
                })
    return exercise_templates

def add_assignments(templates):
    """Add assignments to the database."""
    for template in templates:
        # Check if the assignment already exists
        existing_assignment = Assignment.query.filter_by(name=template["name"]).first()
        if not existing_assignment:
            # Create a new assignment record
            new_assignment = Assignment(
                name=template["name"],
                is_open=template["is_open"],
                deadline=template["deadline"],
                description=template.get("description", "")
            )
            db.session.add(new_assignment)
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        # Create the database tables if they don't exist
        db.create_all()
        # Get exercise templates from the directory
        exercise_templates = get_exercise_templates('static/exercises')
        # Add the exercise templates to the assignments table
        add_assignments(exercise_templates)