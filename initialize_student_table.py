import csv
import secrets
from pc_flask_middleware import app, db, Student  # Import app, db and Student model from your Flask app

def generate_secret_token():
    # Generate a secure token
    return secrets.token_hex(8)

def generate_anonymous_id():
    """Generate a unique 8-character anonymous ID"""
    while True:
        anon_id = f"{secrets.token_hex(3)}"
        if not Student.query.filter_by(anonymous_id=anon_id).first():
            return anon_id

def insert_student(netid, token):
    # Create a new student record
    student = Student(
        net_id=netid,
        anonymous_id=generate_anonymous_id(),
        secret_token=token
    )
    db.session.add(student)

def main():
    # Use the Flask app context to access the database
    with app.app_context():
        # Read the CSV file
        with open('students.csv', newline='') as csvfile:
            student_reader = csv.reader(csvfile)
            for row in student_reader:
                if len(row) == 0 or row[0].strip() == '':
                    continue  # Skip empty rows
                netid = row[0].strip()  # Assuming netid is the first column
                token = generate_secret_token()
                insert_student(netid, token)

        # Commit the transaction
        db.session.commit()

if __name__ == "__main__":
    main()
