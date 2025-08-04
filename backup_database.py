#!/usr/bin/env python3
"""
Database Backup Utility

This program creates a backup of the current database state before performing
a semester reset. It exports all data to CSV files for safekeeping.

Usage:
    python backup_database.py [--output-dir backup_directory]
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pc_flask_middleware import db, Student, Submission, Assignment, AdminToken

def backup_students(output_file):
    """Backup student data to CSV"""
    students = Student.query.all()
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['id', 'net_id', 'anonymous_id', 'display_net_id', 'secret_token', 'debug']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students:
            writer.writerow({
                'id': student.id,
                'net_id': student.net_id,
                'anonymous_id': student.anonymous_id,
                'display_net_id': student.display_net_id,
                'secret_token': student.secret_token,
                'debug': student.debug
            })
    
    return len(students)

def backup_submissions(output_file):
    """Backup submission data to CSV"""
    submissions = Submission.query.all()
    
    with open(output_file, 'w', newline='') as csvfile:
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
    
    return len(submissions)

def backup_assignments(output_file):
    """Backup assignment data to CSV"""
    assignments = Assignment.query.all()
    
    with open(output_file, 'w', newline='') as csvfile:
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
    
    return len(assignments)

def backup_admin_tokens(output_file):
    """Backup admin token data to CSV"""
    tokens = AdminToken.query.all()
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['id', 'token']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for token in tokens:
            writer.writerow({
                'id': token.id,
                'token': token.token
            })
    
    return len(tokens)

def create_backup(output_dir):
    """
    Create a complete backup of the database.
    
    Args:
        output_dir (str): Directory to store backup files
        
    Returns:
        dict: Summary of backup statistics
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create timestamp for backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(output_dir, f"backup_{timestamp}")
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"Creating backup in: {backup_dir}")
    print()
    
    # Backup each table
    stats = {}
    
    print("Backing up students...")
    students_file = os.path.join(backup_dir, "students.csv")
    stats['students'] = backup_students(students_file)
    
    print("Backing up submissions...")
    submissions_file = os.path.join(backup_dir, "submissions.csv")
    stats['submissions'] = backup_submissions(submissions_file)
    
    print("Backing up assignments...")
    assignments_file = os.path.join(backup_dir, "assignments.csv")
    stats['assignments'] = backup_assignments(assignments_file)
    
    print("Backing up admin tokens...")
    tokens_file = os.path.join(backup_dir, "admin_tokens.csv")
    stats['admin_tokens'] = backup_admin_tokens(tokens_file)
    
    # Create a summary file
    summary_file = os.path.join(backup_dir, "backup_summary.txt")
    with open(summary_file, 'w') as f:
        f.write(f"Database Backup Summary\n")
        f.write(f"Created: {datetime.now().isoformat()}\n")
        f.write(f"Backup Directory: {backup_dir}\n\n")
        f.write(f"Records backed up:\n")
        f.write(f"  - Students: {stats['students']}\n")
        f.write(f"  - Submissions: {stats['submissions']}\n")
        f.write(f"  - Assignments: {stats['assignments']}\n")
        f.write(f"  - Admin Tokens: {stats['admin_tokens']}\n")
    
    return stats, backup_dir

def main():
    parser = argparse.ArgumentParser(
        description="Create a backup of the database before semester reset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backup_database.py                    # Backup to ./backups/
  python backup_database.py --output-dir /path/to/backups
        """
    )
    
    parser.add_argument(
        '--output-dir',
        default='./backups',
        help='Directory to store backup files (default: ./backups)'
    )
    
    args = parser.parse_args()
    
    # Use the Flask app context to access the database
    from pc_flask_middleware import app
    
    with app.app_context():
        print("Database Backup Utility")
        print("=" * 50)
        print()
        
        # Check if database has data
        student_count = Student.query.count()
        submission_count = Submission.query.count()
        assignment_count = Assignment.query.count()
        
        if student_count == 0 and submission_count == 0 and assignment_count == 0:
            print("⚠️  Warning: Database appears to be empty!")
            print("No data to backup.")
            sys.exit(0)
        
        print(f"Current database state:")
        print(f"  - Students: {student_count}")
        print(f"  - Submissions: {submission_count}")
        print(f"  - Assignments: {assignment_count}")
        print()
        
        # Create backup
        try:
            stats, backup_dir = create_backup(args.output_dir)
            
            print("\n✅ Backup completed successfully!")
            print(f"Backup location: {backup_dir}")
            print()
            print("Backup summary:")
            print(f"  - Students: {stats['students']}")
            print(f"  - Submissions: {stats['submissions']}")
            print(f"  - Assignments: {stats['assignments']}")
            print(f"  - Admin Tokens: {stats['admin_tokens']}")
            print()
            print("Files created:")
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                size = os.path.getsize(filepath)
                print(f"  - {filename} ({size:,} bytes)")
            
        except Exception as e:
            print(f"\n❌ Error during backup: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main() 