#!/usr/bin/env python3
"""
Database Migration: Add semester column to student table

This migration adds a semester column to the student table and sets
all existing students to have semester='sp25'.

Usage:
    python migrations/add_semester_column_migration.py

This script is safe to run multiple times - it will only add the column
if it doesn't already exist.
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import pc_flask_middleware
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc_flask_middleware import app, db, Student

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    with app.app_context():
        with db.engine.connect() as conn:
            # Get table info
            result = conn.execute(db.text(f"PRAGMA table_info({table_name})"))
            columns = result.fetchall()
            
            # Check if column exists
            for column in columns:
                if column[1] == column_name:  # column[1] is the column name
                    return True
            return False

def add_semester_column():
    """Add semester column to student table if it doesn't exist"""
    with app.app_context():
        print("Checking if semester column exists...")
        
        if check_column_exists('student', 'semester'):
            print("ℹ️  Semester column already exists in student table")
            return True
        
        print("Adding semester column to student table...")
        
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE student ADD COLUMN semester VARCHAR(20)"))
                conn.commit()
            print("✅ Successfully added semester column to student table")
            return True
        except Exception as e:
            print(f"❌ Error adding semester column: {e}")
            return False

def update_existing_students():
    """Update all existing students to have semester='fa25' (current semester)"""
    with app.app_context():
        # Get all students without semester set (excluding historic students)
        students = Student.query.filter(
            Student.semester.is_(None),
            Student.debug == False  # Don't update historic students
        ).all()
        
        if not students:
            print("ℹ️  No current students found without semester value")
            return
        
        print(f"Found {len(students)} current students without semester value.")
        print("Setting semester='fa25' for current students...")
        
        # Update each current student
        updated_count = 0
        for student in students:
            student.semester = 'fa25'
            updated_count += 1
            print(f"  - Updated {student.net_id} ({student.anonymous_id})")
        
        # Commit the changes
        db.session.commit()
        
        print(f"\n✅ Successfully updated {updated_count} current students with semester='fa25'")

def verify_migration():
    """Verify that the migration was successful"""
    with app.app_context():
        total_students = Student.query.count()
        students_with_semester = Student.query.filter(Student.semester.isnot(None)).count()
        current_students_fa25 = Student.query.filter_by(semester='fa25', debug=False).count()
        historic_students_sp25 = Student.query.filter_by(semester='sp25', debug=True).count()
        
        print(f"\nMigration Verification:")
        print(f"  - Total students: {total_students}")
        print(f"  - Students with semester: {students_with_semester}")
        print(f"  - Current students (fa25): {current_students_fa25}")
        print(f"  - Historic students (sp25): {historic_students_sp25}")
        
        if students_with_semester == total_students:
            print("✅ All students have semester values")
        else:
            print(f"⚠️  {total_students - students_with_semester} students still missing semester values")

def main():
    """Main migration function"""
    print("=" * 60)
    print("Database Migration: Add Semester Column")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Add semester column
    if not add_semester_column():
        print("❌ Migration failed: Could not add semester column")
        sys.exit(1)
    
    print()
    
    # Step 2: Update existing students
    update_existing_students()
    
    print()
    
    # Step 3: Verify migration
    verify_migration()
    
    print()
    print("=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main() 