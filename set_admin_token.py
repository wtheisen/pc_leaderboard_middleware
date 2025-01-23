import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
db = SQLAlchemy(app)

class AdminToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)

def set_admin_token(token):
    with app.app_context():
        # Check if the token already exists
        existing_token = AdminToken.query.first()
        if existing_token:
            existing_token.token = token
            print("Admin token updated.")
        else:
            new_token = AdminToken(token=token)
            db.session.add(new_token)
            print("Admin token set.")
        
        db.session.commit()

if __name__ == '__main__':
    # Get the token from an environment variable
    token = None
    if not token:
        print("Error: ADMIN_SECRET_TOKEN environment variable not set.")
    else:
        set_admin_token(token) 