import os
from flask import Flask
from twilio.rest import Client
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Database Configuration (Update with your actual database URL)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobsite.db'  # Change if using PostgreSQL/MySQL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Database
db = SQLAlchemy(app)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_CALLER_ID = os.getenv("TWILIO_PHONE_NUMBER")
NGROK_HTTP_URL = os.getenv("FLASK_TUNNEL_URL")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Database Models
class Applicant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    applications = db.relationship('Application', backref='applicant', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('applicant.id'), nullable=False)
    cv = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=False)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    applications = db.relationship('Application', backref='job', lazy=True)

def schedule_calls(job_id, min_score):
    """
    Fetches top applicants based on score and schedules calls.
    """
    print(f"Fetching applicants for Job ID: {job_id} with a minimum score of {min_score}...")

    with app.app_context():
        top_applicants = (
            db.session.query(Applicant.phone_number)
            .join(Application)
            .filter(Application.job_id == job_id, Application.score >= min_score)
            .all()
        )

        if not top_applicants:
            print("No applicants meet the criteria.")
            return

        successful_calls = []
        failed_calls = []

        for applicant in top_applicants:
            try:
                call = twilio_client.calls.create(
                    from_=TWILIO_CALLER_ID,
                    to=applicant.phone_number,
                    url=f"{NGROK_HTTP_URL}/voice"
                )
                successful_calls.append(applicant.phone_number)
                print(f"✅ Call scheduled for: {applicant.phone_number} (Call SID: {call.sid})")
            except Exception as e:
                failed_calls.append({"number": applicant.phone_number, "error": str(e)})
                print(f"❌ Failed to schedule call for: {applicant.phone_number}. Error: {e}")

        print("\n--- Summary ---")
        print(f"Successful Calls: {successful_calls}")
        print(f"Failed Calls: {failed_calls}")

if __name__ == "__main__":
    # Example usage: Schedule calls for job ID 1, min score 80
    schedule_calls(job_id=1, min_score=70)
