import sqlite3
from datetime import datetime
import pytz

# Define the path to your SQLite database
DATABASE_PATH = "instance/submissions.db"

# Define EST timezone
EST = pytz.timezone("America/New_York")

def close_expired_assignments():
    # Get the current time in EST
    now_est = datetime.now(EST).strftime("%Y-%m-%d %H:%M:%S")

    # Connect to the SQLite database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Update assignments that are past due and still open
    cursor.execute(
        "UPDATE Assignment SET is_open = 0 WHERE deadline < ? AND is_open = 1",
        (now_est,),
    )

    # Commit changes and close connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    close_expired_assignments()