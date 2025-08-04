#!/usr/bin/env python3
"""
Script to add semester column to existing students in the database.

This script updates all existing students to have semester='sp25'.
"""

from pc_flask_middleware import app, db, Student

def add_semester_to_students():
    """Add semester='sp25' to all existing students"""
    with app.app_context():
        # Get all students
        students = Student.query.all()
        
        if not students:
            print("No students found in the database.")
            return
        
        print(f"Found {len(students)} students in the database.")
        print("Adding semester='sp25' to all students...")
        
        # Update each student
        updated_count = 0
        for student in students:
            if student.semester is None:
                student.semester = 'sp25'
                updated_count += 1
                print(f"  - Updated {student.net_id} ({student.anonymous_id})")
            else:
                print(f"  - Skipped {student.net_id} ({student.anonymous_id}) - already has semester: {student.semester}")
        
        # Commit the changes
        db.session.commit()
        
        print(f"\n✅ Successfully updated {updated_count} students with semester='sp25'")
        print(f"Total students in database: {len(students)}")

if __name__ == "__main__":
    add_semester_to_students() 