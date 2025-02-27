from datetime import datetime
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pc_flask_middleware import Assignment

# Define the EST timezone
EST = pytz.timezone("America/New_York")

# Update with your actual database URI
DATABASE_URI = "sqlite:///submissions.db"
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)

def close_expired_assignments():
    session = Session()

    # Get the current time in EST
    now_est = datetime.now(EST)

    # Query assignments that have passed the deadline and are still open
    expired_assignments = session.query(Assignment).filter(
        Assignment.deadline < now_est, Assignment.is_open == True
    ).all()

    for assignment in expired_assignments:
        assignment.is_open = False
        print(f"Closed assignment: {assignment.name}")

    if expired_assignments:
        session.commit()
    session.close()

if __name__ == "__main__":
    close_expired_assignments()