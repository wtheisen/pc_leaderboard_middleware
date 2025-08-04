# Database Migrations

This directory contains database migration scripts for the PC Leaderboard application.

## Available Migrations

### 1. Add Semester Column Migration

**File:** `add_semester_column_migration.py`

**Purpose:** Adds a `semester` column to the `student` table and sets current students to have `semester='fa25'` while preserving historic students' original semesters.

**Usage:**
```bash
python migrations/add_semester_column_migration.py
```

**What it does:**
1. Checks if the `semester` column already exists in the `student` table
2. Adds the column if it doesn't exist
3. Updates current students (debug=False) to have `semester='fa25'`
4. Preserves historic students' (debug=True) original semesters
5. Verifies the migration was successful

**Safety:** This script is safe to run multiple times - it will only add the column if it doesn't already exist.

## Running Migrations

1. **Backup your database first:**
   ```bash
   cp your_database.db your_database_backup.db
   ```

2. **Run the migration:**
   ```bash
   python migrations/add_semester_column_migration.py
   ```

3. **Verify the migration:**
   The script will output verification information showing how many students were updated.

## Migration Log

- **2025-01-XX:** Added semester column migration for Fall 2025 semester
  - Added `semester` VARCHAR(20) column to `student` table
  - Set current students to `semester='fa25'` (Fall 2025)
  - Preserved historic students' original semesters (e.g., `sp25` for Spring 2025)

## Notes

- All migrations are designed to be idempotent (safe to run multiple times)
- Migrations include verification steps to ensure they completed successfully
- Always backup your database before running migrations in production 