# Enhanced Semester Reset Process

This document describes the enhanced semester reset process that provides a complete fresh start for each new semester.

## Overview

The enhanced semester reset program (`semester_reset.py`) performs a complete database reset by:

1. **Creating a backup** of the current database state
2. **Preserving top 3 students** as historic entries on the leaderboard
3. **Clearing all tables** (submissions, assignments, current students)
4. **Repopulating** with new students from `students.csv`
5. **Providing a complete fresh start** for the new semester

## Prerequisites

Before running the semester reset:

1. **Update `students.csv`** with the new student net IDs for the upcoming semester
2. **Ensure you have the latest assignment schedule** ready for the new semester
3. **Backup any important data** (the program will also create a backup, but it's good practice)

## File Format

### students.csv
The `students.csv` file should contain the net IDs of all students for the new semester:

```csv
netid
student1
student2
student3
student4
student5
```

**Format:**
- One net ID per line
- First line can be a header (e.g., "netid")
- Empty lines are ignored
- No additional columns needed

## Usage

### Basic Usage
```bash
python semester_reset.py
```
This will run interactively with confirmation prompts.

### Non-Interactive Usage
```bash
python semester_reset.py --confirm
```
This will skip confirmation prompts and proceed immediately.

### Custom Backup Directory
```bash
python semester_reset.py --backup-dir /path/to/backups
```
This will store backup files in the specified directory.

## What the Program Does

### Step 1: Database Backup
- Creates a timestamped backup directory (e.g., `backup_20241201_143022/`)
- Exports all data to CSV files:
  - `students.csv` - Current student data
  - `submissions.csv` - All submission records
  - `assignments.csv` - All assignment definitions
  - `backup_summary.txt` - Summary of backup contents

### Step 2: Preserve Top Students
- Identifies the top 3 performing students from the current semester
- Marks them as historic entries (debug=True) with semester tags
- Updates their anonymous IDs to include "Historic" prefix
- Preserves them for display on the historic leaderboard

### Step 3: Clear All Tables
- Deletes all submissions (student work and scores)
- Deletes all assignments (definitions and deadlines)
- Deletes all current students (net_ids, tokens, etc.)
- Preserves historic students for the leaderboard

### Step 4: Populate New Students
- Reads `students.csv` for new student net IDs
- Generates new anonymous IDs and secret tokens for each student
- Sets default preferences (anonymous display, non-debug mode)
- Adds all new students to the database

## Backup Files

The backup includes:
- **students.csv** - Complete student records with all fields
- **submissions.csv** - All submission data with timestamps
- **assignments.csv** - All assignment definitions and deadlines
- **backup_summary.txt** - Summary of backup contents and statistics

## After Reset

After running the semester reset:

1. **Verify the new student list** is correct
2. **Check the historic leaderboard** to see preserved top students
3. **Update your assignment schedule** and run `populate_assignments.py`
4. **Set up new assignments** in the admin interface
5. **Test the system** with a few sample submissions

## Historic Leaderboard

The enhanced reset preserves the top 3 students from each semester as historic entries:

- **Historic students** are marked with debug=True to separate them from current students
- **Semester tags** (e.g., "🏆 Fall2024") are added to their display names
- **Anonymous IDs** are updated to include "Historic" prefix (e.g., "Historic1_abc123")
- **Display names** are set to show their actual net IDs for recognition
- **Leaderboard position** shows them with special formatting to distinguish from current students

This creates a "hall of fame" effect where top performers from previous semesters remain visible on the leaderboard, providing motivation and recognition for exceptional performance.

## Recovery

If you need to recover data from a backup:

1. **Locate the backup directory** (e.g., `./backups/backup_20241201_143022/`)
2. **Review the backup files** to understand what was backed up
3. **Use the backup data** to restore specific records if needed

## Safety Features

- **Automatic backup creation** before any destructive operations
- **Confirmation prompts** (unless `--confirm` is used)
- **Error handling** with rollback capabilities
- **Detailed logging** of all operations
- **Verification steps** to confirm successful operations

## Example Workflow

```bash
# 1. Update students.csv with new semester's student list
# 2. Run the semester reset
python semester_reset.py

# 3. Verify the reset was successful
# 4. Update assignment schedule and run populate_assignments.py
python populate_assignments.py

# 5. Set up new assignments in the admin interface
# 6. Test the system
```

## Troubleshooting

### Common Issues

1. **students.csv not found**
   - Ensure the file exists in the current directory
   - Check file permissions

2. **Database errors**
   - Check that the Flask app can access the database
   - Verify database file permissions

3. **Backup directory issues**
   - Ensure the backup directory is writable
   - Check available disk space

### Error Recovery

If the reset fails partway through:

1. **Check the backup files** - they should contain the original data
2. **Review error messages** for specific issues
3. **Restore from backup** if necessary
4. **Re-run the reset** after fixing the issue

## Migration from Old Process

If you were previously using the old semester reset process:

1. **The new process is more comprehensive** - it clears everything and starts fresh
2. **Backup creation is automatic** - no need to run separate backup scripts
3. **Student population is integrated** - no need to run `initialize_student_table.py` separately
4. **The workflow is streamlined** - one command does everything

## File Structure

```
pc_leaderboard/
├── semester_reset.py          # Enhanced reset program
├── students.csv               # New student list
├── backup_database.py         # Legacy backup utility (still available)
├── initialize_student_table.py # Legacy student initialization (still available)
└── backups/                  # Backup directory (created automatically)
    └── backup_YYYYMMDD_HHMMSS/
        ├── students.csv
        ├── submissions.csv
        ├── assignments.csv
        └── backup_summary.txt
``` 