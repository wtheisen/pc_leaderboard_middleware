#!/usr/bin/env python3
"""
Performance calculation functions for semester reset

This module provides functions to calculate student performance data
and get top students for historic preservation during semester reset.
"""

from datetime import datetime
from sqlalchemy import func
from pc_flask_middleware import db, Student, Submission, Assignment


def rank_score(value, sorted_values):
    """Assign a score between 0 and 1 based on rank"""
    if len(sorted_values) == 1:
        return 1.0
    rank = sorted_values.index(value)
    return 1 - (rank / (len(sorted_values) - 1))


def calculate_student_performance_data(student_anonymous_id):
    """
    Calculate performance data for a specific student based on their submissions.
    
    Args:
        student_anonymous_id (str): The student's anonymous ID
        
    Returns:
        dict: Performance data including scores, counts, and averages
    """
    # Get all submissions for this student
    submissions = Submission.query.filter_by(student_id=student_anonymous_id).all()
    
    if not submissions:
        return None
    
    # Get all assignments this student has submitted to
    student_assignments = db.session.query(Submission.assignment).filter_by(
        student_id=student_anonymous_id
    ).distinct().all()
    student_assignments = [a[0] for a in student_assignments]
    
    total_score = 0
    exercises_completed = 0
    challenges_completed = 0
    total_runtime = 0
    total_submission_time_rank = 0
    total_lint_errors = 0
    total_lines_of_code = 0
    tags = []
    
    # Calculate performance for each assignment
    for assignment in student_assignments:
        # Get the student's latest submission for this assignment
        latest_submission = db.session.query(Submission).filter_by(
            student_id=student_anonymous_id,
            assignment=assignment
        ).order_by(Submission.submission_time.desc()).first()
        
        if not latest_submission:
            continue
        
        # Get all submissions for this assignment to calculate ranks
        assignment_submissions = Submission.query.filter_by(assignment=assignment).all()
        
        if not assignment_submissions:
            continue
        
        # Calculate ranks
        sorted_runtimes = sorted(s.runtime for s in assignment_submissions)
        sorted_submission_times = sorted(s.submission_time.timestamp() for s in assignment_submissions)
        sorted_lint_errors = sorted(s.lint_errors for s in assignment_submissions)
        
        runtime_rank = rank_score(latest_submission.runtime, sorted_runtimes)
        time_rank = rank_score(latest_submission.submission_time.timestamp(), sorted_submission_times)
        lint_rank = rank_score(latest_submission.lint_errors, sorted_lint_errors)
        code_score = latest_submission.code_score / 100
        
        weighted_score = (
            0.4 * runtime_rank +
            0.3 * lint_rank +
            0.2 * time_rank +
            0.1 * code_score
        )
        
        if 'exercise' in assignment:
            weighted_score *= 0.25
            exercises_completed += 1
        else:
            challenges_completed += 1
        
        total_score += weighted_score
        total_runtime += latest_submission.runtime
        total_submission_time_rank += time_rank
        total_lint_errors += latest_submission.lint_errors
        
        if latest_submission.lines_of_code:
            total_lines_of_code += latest_submission.lines_of_code
        else:
            total_lines_of_code += -1
    
    # Calculate averages
    total_assignments = exercises_completed + challenges_completed
    if total_assignments > 0:
        avg_runtime = total_runtime / total_assignments
        avg_submission_time_rank = total_submission_time_rank / total_assignments
        avg_lint_errors = total_lint_errors / total_assignments
        avg_lines_of_code = total_lines_of_code / total_assignments
    else:
        avg_runtime = avg_submission_time_rank = avg_lint_errors = avg_lines_of_code = 0
    
    # Generate tags based on performance
    if exercises_completed > 0:
        tags.append("Exercise Master")
    if challenges_completed > 0:
        tags.append("Challenge Champion")
    if avg_runtime < 0.1:  # Very fast
        tags.append("Speed Demon")
    if avg_lint_errors < 0.5:  # Very clean code
        tags.append("Clean Coder")
    if total_score > 5:  # High overall score
        tags.append("High Achiever")
    
    return {
        'total_score': total_score,
        'exercises_completed': exercises_completed,
        'challenges_completed': challenges_completed,
        'avg_runtime': avg_runtime,
        'avg_submission_time_rank': avg_submission_time_rank,
        'avg_lint_errors': avg_lint_errors,
        'avg_lines_of_code': avg_lines_of_code,
        'tags': tags
    }


def get_top_students_with_performance():
    """
    Get the top 3 students with their performance data calculated from submissions.
    Excludes debug students from the calculation.
    
    Returns:
        list: List of dictionaries containing student objects and performance data
    """
    # Get all non-debug students with submissions
    students_with_submissions = db.session.query(Student).join(Submission).filter(
        Student.debug == False
    ).distinct().all()
    
    if not students_with_submissions:
        return []
    
    # Calculate performance for each student
    student_performance = []
    for student in students_with_submissions:
        performance_data = calculate_student_performance_data(student.anonymous_id)
        if performance_data:
            student_performance.append({
                'student': student,
                'performance': performance_data
            })
    
    # Sort by total score (descending) and take top 3
    student_performance.sort(key=lambda x: x['performance']['total_score'], reverse=True)
    top_students = student_performance[:3]
    
    return top_students 