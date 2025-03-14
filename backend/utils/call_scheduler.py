import os
from .cv_screening import assign_candidate_score

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
TWILIO_CALLER_ID = os.getenv("TWILIO_PHONE_NUMBER", "+15551234567")
NGROK_HTTP_URL = os.getenv("FLASK_TUNNEL_URL")

def schedule_calls(cv_path, application_id, min_score, db, Application, twilio_client, job_details):
    score = assign_candidate_score(cv_path, job_details)
    application = Application.query.get(application_id)
    application.score = score
    db.session.commit()

    if score >= min_score:
        try:
            call = twilio_client.calls.create(
                from_=TWILIO_CALLER_ID,
                to=application.applicant.phone_number,
                url=f"{NGROK_HTTP_URL}/voice"
            )
            print(f"✅ Call scheduled for: {application.applicant.phone_number} (Call SID: {call.sid})")
        except Exception as e:
            print(f"❌ Failed to schedule call for: {application.applicant.phone_number}. Error: {e}")

if __name__ == "__main__":
    # Example usage: Schedule calls for job ID 1, min score 80
    schedule_calls(job_id=1, min_score=70)
