#!/usr/bin/env python3
"""
Script to add semester column to the database schema and update existing students.

This script:
1. Adds the semester column to the student table
2. Updates all existing students to have semester='sp25'
"""

from pc_flask_middleware import app, db, Student

def add_semester_column_to_db():
    """Add semester column to the student table"""
    with app.app_context():
        print("Adding semester column to student table...")
        
        # Add the semester column to the student table
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE student ADD COLUMN semester VARCHAR(20)"))
                conn.commit()
            print("✅ Successfully added semester column to student table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  Semester column already exists in student table")
            else:
                print(f"❌ Error adding semester column: {e}")
                return False
        
        return True

def update_students_with_semester():
    """Update all existing students to have semester='sp25'"""
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

def main():
    """Main function to add semester column and update students"""
    print("Adding semester column to database and updating students...")
    print("=" * 60)
    
    # Step 1: Add semester column to database
    if not add_semester_column_to_db():
        print("❌ Failed to add semester column to database")
        return
    
    print()
    
    # Step 2: Update students with semester value
    update_students_with_semester()
    
    print("\n✅ Script completed successfully!")

if __name__ == "__main__":
    main() 