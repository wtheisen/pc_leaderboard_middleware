from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Reuse app, db, and models from the main middleware
from pc_flask_middleware import app, db, Submission, is_success_status


def normalize():
    updated = 0
    total = 0
    with app.app_context():
        subs = Submission.query.all()
        for sub in subs:
            total += 1
            canonical = 'Success' if is_success_status(sub.status) else 'Failure'
            if sub.status != canonical:
                sub.status = canonical
                updated += 1
        if updated:
            db.session.commit()
    print(f"Normalized {updated} of {total} submissions.")


if __name__ == '__main__':
    normalize()

