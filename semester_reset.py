#!/usr/bin/env python3
"""
Enhanced Semester Reset Program

This program performs a complete semester reset by:
1. Creating a backup of the current database
2. Clearing all submissions (student work and scores)
3. Clearing all assignments (assignment definitions and deadlines)
4. Clearing all students (net_ids, anonymous_ids, secret_tokens)
5. Repopulating with new students from students.csv
6. Providing a complete fresh start for a new semester

Usage:
    python semester_reset.py [--backup-dir backup_directory] [--confirm]

Options:
    --backup-dir: Directory to store backup files (default: ./backups)
    --confirm: Skip confirmation prompt and proceed immediately
"""

import argparse
import sys
import csv
import secrets
import os
from datetime import datetime
from pc_flask_middleware import db, Student, Submission, Assignment, AdminToken

def generate_secret_token():
    """Generate a secure token"""
    return secrets.token_hex(8)

def generate_anonymous_id():
    """Generate a unique 8-character anonymous ID"""
    while True:
        anon_id = f"{secrets.token_hex(3)}"
        if not Student.query.filter_by(anonymous_id=anon_id).first():
            return anon_id

def backup_database(backup_dir):
    """
    Create a backup of the current database.
    
    Args:
        backup_dir (str): Directory to store backup files
        
    Returns:
        tuple: (stats dict, backup directory path)
    """
    # Create output directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)
    
    # Create timestamp for backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    
    print(f"Creating backup in: {backup_path}")
    print()
    
    stats = {}
    
    # Backup students
    print("Backing up students...")
    students_file = os.path.join(backup_path, "students.csv")
    students = Student.query.all()
    with open(students_file, 'w', newline='') as csvfile:
        fieldnames = ['id', 'net_id', 'anonymous_id', 'display_net_id', 'secret_token', 'debug', 'semester']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for student in students:
            writer.writerow({
                'id': student.id,
                'net_id': student.net_id,
                'anonymous_id': student.anonymous_id,
                'display_net_id': student.display_net_id,
                'secret_token': student.secret_token,
                'debug': student.debug,
                'semester': student.semester
            })
    stats['students'] = len(students)
    
    # Backup submissions
    print("Backing up submissions...")
    submissions_file = os.path.join(backup_path, "submissions.csv")
    submissions = Submission.query.all()
    with open(submissions_file, 'w', newline='') as csvfile:
        fieldnames = ['id', 'student_id', 'status', 'assignment', 'code_score', 
                     'runtime', 'lint_errors', 'submission_time', 'lines_of_code']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for submission in submissions:
            writer.writerow({
                'id': submission.id,
                'student_id': submission.student_id,
                'status': submission.status,
                'assignment': submission.assignment,
                'code_score': submission.code_score,
                'runtime': submission.runtime,
                'lint_errors': submission.lint_errors,
                'submission_time': submission.submission_time.isoformat(),
                'lines_of_code': submission.lines_of_code
            })
    stats['submissions'] = len(submissions)
    
    # Backup assignments
    print("Backing up assignments...")
    assignments_file = os.path.join(backup_path, "assignments.csv")
    assignments = Assignment.query.all()
    with open(assignments_file, 'w', newline='') as csvfile:
        fieldnames = ['id', 'name', 'is_open', 'deadline', 'description']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for assignment in assignments:
            writer.writerow({
                'id': assignment.id,
                'name': assignment.name,
                'is_open': assignment.is_open,
                'deadline': assignment.deadline.isoformat(),
                'description': assignment.description
            })
    stats['assignments'] = len(assignments)
    
    # Create a summary file
    summary_file = os.path.join(backup_path, "backup_summary.txt")
    with open(summary_file, 'w') as f:
        f.write(f"Database Backup Summary\n")
        f.write(f"Created: {datetime.now().isoformat()}\n")
        f.write(f"Backup Directory: {backup_path}\n\n")
        f.write(f"Records backed up:\n")
        f.write(f"  - Students: {stats['students']}\n")
        f.write(f"  - Submissions: {stats['submissions']}\n")
        f.write(f"  - Assignments: {stats['assignments']}\n")
    
    return stats, backup_path

def get_top_students():
    """Get the top 3 students from the current semester for historic preservation"""
    from calculate_performance_data import get_top_students_with_performance
    
    # Get top students with performance data calculated from submissions
    top_students_data = get_top_students_with_performance()
    
    # Extract just the student objects
    top_students = [data['student'] for data in top_students_data]
    
    return top_students

def preserve_historic_students(top_students, current_semester):
    """Preserve top 3 students as historic entries with their performance data"""
    if not top_students:
        print("No top students to preserve.")
        return
    
    print(f"Preserving top {len(top_students)} students as historic entries...")
    
    # Import the HistoricStudentPerformance model and performance calculation
    from pc_flask_middleware import HistoricStudentPerformance
    from calculate_performance_data import calculate_student_performance_data
    
    for i, student in enumerate(top_students, 1):
        # Mark as historic (debug=True) and add semester tag
        student.debug = True
        student.semester = current_semester
        student.display_net_id = True  # Show names for historic students
        
        # Update anonymous_id to include historic tag
        historic_id = f"Historic{i}_{student.anonymous_id}"
        original_anonymous_id = student.anonymous_id
        student.anonymous_id = historic_id
        
        # Calculate performance data directly from submissions
        performance_data = calculate_student_performance_data(original_anonymous_id)
        
        # Save performance data to HistoricStudentPerformance table
        if performance_data:
            import json
            historic_performance = HistoricStudentPerformance(
                student_anonymous_id=historic_id,  # Use the new historic ID
                semester=current_semester,
                total_score=performance_data['total_score'],
                exercises_completed=performance_data['exercises_completed'],
                challenges_completed=performance_data['challenges_completed'],
                avg_runtime=performance_data['avg_runtime'],
                avg_lint_errors=performance_data['avg_lint_errors'],
                avg_lines_of_code=performance_data['avg_lines_of_code'],
                avg_submission_time_rank=performance_data['avg_submission_time_rank'],
                tags=json.dumps(performance_data['tags'])
            )
            db.session.add(historic_performance)
            print(f"  - Preserved: {student.net_id} (Rank {i}) as {historic_id}")
            print(f"    Performance: {performance_data['total_score']:.1f} points, {performance_data['exercises_completed'] + performance_data['challenges_completed']} assignments")
            print(f"    Tags: {performance_data['tags']}")
        else:
            print(f"  - Preserved: {student.net_id} (Rank {i}) as {historic_id} (no performance data found)")
    
    db.session.commit()
    print(f"✅ Preserved {len(top_students)} historic students with performance data")

def clear_all_tables():
    """Clear all database tables"""
    print("Clearing all database tables...")
    
    # Get counts before deletion for reporting
    submission_count = Submission.query.count()
    assignment_count = Assignment.query.count()
    student_count = Student.query.count()
    
    print(f"Current database state:")
    print(f"  - Students: {student_count}")
    print(f"  - Submissions: {submission_count}")
    print(f"  - Assignments: {assignment_count}")
    print()
    
    # Clear all submissions
    print("Clearing all submissions...")
    Submission.query.delete()
    
    # Clear all assignments
    print("Clearing all assignments...")
    Assignment.query.delete()
    
    # Clear all students (except historic ones)
    print("Clearing all current students...")
    # Clear students that are NOT historic (i.e., don't have "Historic" in their anonymous_id)
    Student.query.filter(~Student.anonymous_id.like('Historic%')).delete()
    
    # Commit all changes
    db.session.commit()
    
    # Verify the reset
    new_submission_count = Submission.query.count()
    new_assignment_count = Assignment.query.count()
    new_student_count = Student.query.count()
    historic_student_count = Student.query.filter(Student.anonymous_id.like('Historic%')).count()
    
    print(f"\nClear completed successfully!")
    print(f"New database state:")
    print(f"  - Current students: {new_student_count - historic_student_count} (cleared)")
    print(f"  - Historic students: {historic_student_count} (preserved)")
    print(f"  - Submissions: {new_submission_count} (cleared)")
    print(f"  - Assignments: {new_assignment_count} (cleared)")

def populate_new_students(semester):
    """Populate the database with new students from students.csv"""
    print(f"\nPopulating with new students from students.csv (semester: {semester})...")
    
    if not os.path.exists('students.csv'):
        print("❌ Error: students.csv file not found!")
        print("Please create a students.csv file with the new student net IDs.")
        sys.exit(1)
    
    # Read the CSV file
    with open('students.csv', newline='') as csvfile:
        student_reader = csv.reader(csvfile)
        student_count = 0
        
        for row in student_reader:
            if len(row) == 0 or row[0].strip() == '':
                continue  # Skip empty rows
                
            netid = row[0].strip()  # Assuming netid is the first column
            
            # Create a new student record
            student = Student(
                net_id=netid,
                anonymous_id=generate_anonymous_id(),
                secret_token=generate_secret_token(),
                display_net_id=False,  # Default to anonymous display
                debug=False,  # Default to non-debug mode
                semester=semester  # Set the semester for all new students
            )
            db.session.add(student)
            student_count += 1
    
    # Commit the transaction
    db.session.commit()
    
    print(f"✅ Successfully added {student_count} new students to the database with semester '{semester}'.")
    
    # Verify the population
    final_student_count = Student.query.count()
    print(f"Total students in database: {final_student_count}")

def reset_semester_data(backup_dir, semester=None):
    """
    Perform a complete semester reset.
    
    Args:
        backup_dir (str): Directory to store backup files
        semester (str): Custom semester name for historic students
    """
    print("Starting complete semester reset...")
    print()
    
    # Step 1: Create backup
    print("Step 1: Creating database backup...")
    stats, backup_path = backup_database(backup_dir)
    print(f"✅ Backup completed: {backup_path}")
    print()
    
    # Step 2: Preserve top 3 students as historic
    print("Step 2: Preserving top 3 students as historic entries...")
    top_students = get_top_students()
    
    # Determine current semester (you can customize this logic)
    if semester:
        current_semester = semester
    else:
        current_month = datetime.now().month
        current_year = datetime.now().year
        if current_month >= 8 and current_month <= 12:
            current_semester = f"Fall{current_year}"
        elif current_month >= 1 and current_month <= 5:
            current_semester = f"Spring{current_year}"
        else:
            current_semester = f"Summer{current_year}"
    
    preserve_historic_students(top_students, current_semester)
    print()
    
    # Step 3: Clear all tables
    print("Step 3: Clearing all database tables...")
    clear_all_tables()
    print()
    
    # Step 4: Populate with new students
    print("Step 4: Populating with new students...")
    populate_new_students(semester)
    print()
    
    print("✅ Complete semester reset finished successfully!")
    print()
    print("Summary:")
    print(f"  - Backup created: {backup_path}")
    print(f"  - Historic students preserved: {len(top_students)}")
    print(f"  - Database cleared: All tables reset")
    print(f"  - New students added: {Student.query.filter_by(semester=semester).count()} students")
    print()
    print("Next steps:")
    print("1. Update your assignment schedule and run populate_assignments.py")
    print("2. Set up new assignments in the admin interface")
    print("3. Verify the new student list is correct")

def main():
    parser = argparse.ArgumentParser(
        description="Perform a complete semester reset with backup and new student population",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python semester_reset.py                    # Interactive reset
  python semester_reset.py --confirm         # Reset without confirmation
  python semester_reset.py --backup-dir /path/to/backups  # Custom backup location
  python semester_reset.py --semester "Fall2024"  # Custom semester name
        """
    )
    
    parser.add_argument(
        '--backup-dir',
        default='./backups',
        help='Directory to store backup files (default: ./backups)'
    )
    
    parser.add_argument(
        '--semester',
        help='Custom semester name for historic students (e.g., "Fall2024", "Spring2025")'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Skip confirmation prompt and proceed immediately'
    )
    
    args = parser.parse_args()
    
    # Use the Flask app context to access the database
    from pc_flask_middleware import app
    
    with app.app_context():
        # Show what will be reset
        print("Enhanced Semester Reset Tool")
        print("=" * 50)
        print()
        print("This will perform a COMPLETE semester reset:")
        print("  ✓ Create a backup of the current database")
        print("  ✓ Preserve top 3 students as historic entries")
        print("  ✓ Clear all submissions (student work and scores)")
        print("  ✓ Clear all assignments (definitions and deadlines)")
        print("  ✓ Clear all current students (preserving historic students)")
        print("  ✓ Repopulate with new students from students.csv")
        print()
        
        # Check if students.csv exists
        if not os.path.exists('students.csv'):
            print("❌ Error: students.csv file not found!")
            print("Please create a students.csv file with the new student net IDs.")
            print("Format: one net ID per line, or CSV with netid as first column")
            sys.exit(1)
        
        # Get current counts for confirmation
        submission_count = Submission.query.count()
        assignment_count = Assignment.query.count()
        student_count = Student.query.count()
        
        print(f"Current data to be backed up and cleared:")
        print(f"  - {submission_count} submissions")
        print(f"  - {assignment_count} assignments")
        print(f"  - {student_count} students")
        print()
        
        # Count new students
        try:
            with open('students.csv', newline='') as csvfile:
                student_reader = csv.reader(csvfile)
                new_student_count = sum(1 for row in student_reader if row and row[0].strip())
            print(f"New students to be added: {new_student_count}")
            print()
        except Exception as e:
            print(f"⚠️  Warning: Could not count students in students.csv: {e}")
            print()
        
        # Confirmation prompt
        if not args.confirm:
            print("⚠️  WARNING: This action will completely reset the database!")
            print("⚠️  A backup will be created, but this action cannot be undone!")
            response = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
            
            if response not in ['yes', 'y']:
                print("Reset cancelled.")
                sys.exit(0)
        
        # Get semester if not provided
        if not args.semester:
            print("Enter the semester for the new students (e.g., 'fa25', 'sp26', 'su25'):")
            semester = input("Semester: ").strip()
            if not semester:
                print("❌ Error: Semester is required!")
                sys.exit(1)
        else:
            semester = args.semester
        
        # Perform the reset
        try:
            reset_semester_data(args.backup_dir, semester)
            
        except Exception as e:
            print(f"\n❌ Error during reset: {e}")
            print("The database may be in an inconsistent state.")
            print("Check the backup files for recovery options.")
            sys.exit(1)

if __name__ == "__main__":
    main() 