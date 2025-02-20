import json
from datetime import datetime
from pc_flask_middleware import db, Assignment  # Adjust the import to match your app structure

def populate_assignments_from_json(json_file_path):
    with open(json_file_path, 'r') as file:
        data = json.load(file)

    for entry in data:
        due_date_str = entry['date']
        due_date = datetime.strptime(due_date_str, 'Sun %m/%d')  # Adjust format if needed

        # Set the year for the due date
        due_date = due_date.replace(year=datetime.now().year)

        for assignment_name in entry['assignments']:
            # Check if the assignment already exists
            existing_assignment = Assignment.query.filter_by(name=assignment_name).first()
            if not existing_assignment:
                # Create a new assignment record
                new_assignment = Assignment(
                    name=assignment_name,
                    is_open=True,  # Default to open, adjust as needed
                    deadline=due_date
                )
                db.session.add(new_assignment)

    # Commit the changes to the database
    db.session.commit()

if __name__ == '__main__':
    # Ensure the app context is available
    from pc_flask_middleware import app  # Adjust the import to match your app structure
    with app.app_context():
        populate_assignments_from_json('static/json/challenge_due_dates.json') 