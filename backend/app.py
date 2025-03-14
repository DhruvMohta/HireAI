import os
import time
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client

from google import genai
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone
import json
from sendmail import sendMail
from utils.call_scheduler import schedule_calls
import csv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
TWILIO_CALLER_ID = os.getenv("TWILIO_PHONE_NUMBER", "+15551234567")
NGROK_HTTP_URL = os.getenv("FLASK_TUNNEL_URL")
HR_EMAIL = os.getenv("HR_EMAIL", "demo@gifuzzz.eu")

# Tracking call state
call_start_times = {}       # {call_sid: float}
call_conversations = {}     # {call_sid: [("user", text), ("ai", text), ...]}

# Time limit for calls (3 minutes)
TIME_LIMIT = 180  
CSV_FILE = "call_results.csv"

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Tracking state
call_start_times = {}
call_conversations = {}

# Example context
JOB_DESCRIPTION = "Seeking a Python/Flask dev with strong communication skills."
COMPANY_VALUES = "We value integrity, collaboration, and continuous learning."
HIRING_CONTEXT = f"{JOB_DESCRIPTION}\nValues: {COMPANY_VALUES}"

def ai_generate_response(user_input):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[{"role": "user", "parts": [{"text": f"{user_input}"}]}]
    )
    # Strip "AI Agent:" and return just the content
    return response.candidates[0].content.parts[0].text.strip()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///jobsite.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
db = SQLAlchemy(app)

# Models
class Applicant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))

    applications = db.relationship('Application', backref='applicant', lazy=True)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)
    experience_level = db.Column(db.String(50), nullable=False)
    salary = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.now(timezone.utc))
    deadline = db.Column(db.DateTime)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text)
    
    applications = db.relationship('Application', backref='job', lazy=True)
    
    @property
    def requirements_list(self):
        return json.loads(self.requirements) if self.requirements else []
        
    @requirements_list.setter
    def requirements_list(self, value):
        self.requirements = json.dumps(value) if value else None

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'location': self.location,
            'job_type': self.job_type,
            'experience_level': self.experience_level,
            'salary': self.salary,
            'date_posted': self.date_posted.isoformat() if self.date_posted else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'description': self.description,
            'requirements': self.requirements_list
        }

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('applicant.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    cv_path = db.Column(db.String(256), nullable=False)

    status = db.Column(db.String(20), default='Submitted')
    score = db.Column(db.Integer)
    date_applied = db.Column(db.DateTime, nullable=False, default=datetime.now(timezone.utc))

    def to_dict(self):
        job = Job.query.get(self.job_id)
        applicant = Applicant.query.get(self.applicant_id)
        return {
            'id': self.id,
            'applicant_id': self.applicant_id,
            'first_name': applicant.first_name,
            'last_name': applicant.last_name,
            'email': applicant.email,
            'phone_number': applicant.phone_number,
            'job_id': self.job_id,
            'cv_path': self.cv_path,
            'status': self.status,
            'score': self.score,
            'date_applied': self.date_applied.isoformat(),
            'job_title': job.title,
            'job_location': job.location,
            'job_type': job.job_type,
            'experience_level': job.experience_level
        }

def build_prompt_with_context(call_sid):
    conversation = call_conversations.get(call_sid, [])
    
    # Retrieve the last application
    last_application = Application.query.order_by(Application.date_applied.desc()).first()
    if last_application:
        applicant = Applicant.query.get(last_application.applicant_id)
        job = Job.query.get(last_application.job_id)
        applicant_info = f"Applican Name: {applicant.first_name} {applicant.last_name}, Email: {applicant.email}, Phone: {applicant.phone_number}"
        job_info = f"Job Title: {job.title}, Location: {job.location}, Type: {job.job_type}, Experience Level: {job.experience_level}, Description: {job.description}"
    else:
        applicant_info = "No applicant information available."
        job_info = "No job information available."
    
    print(f"Applicant: {applicant_info}")
    print(f"Job: {job_info}")

    lines = [
        "You are an AI interviewer conducting a brief phone screening.",
        "Your objective is to quickly assess the candidate by asking one or two very short, direct questions at a time.",
        "Keep your responses under 2 sentences and avoid long explanations.",
        "Focus on key points: technical skills, notice period, and problem-solving ability.",
        "If the candidate seems unresponsive or requests to end the call (e.g., says 'cut the call'), wrap up immediately.",
        "",
        f"Applicant Information: {applicant_info}",
        f"Job Information: {job_info}",
        "",
        "Conversation so far:"
    ]
    for role, text in conversation:
        lines.append(f"{'Candidate' if role == 'user' else 'AI Interviewer'}: {text}")
    lines.append("\nIf you decide the interview is complete, include <<<END_CALL>>> in your response (without reading it aloud).")
    return "\n".join(lines)

@app.route('/')
def home():
    return "eyo"

@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    speech_result = request.form.get("SpeechResult", "").strip()

    # First contact: greet the candidate.
    if call_sid not in call_start_times:
        call_start_times[call_sid] = time.time()
        call_conversations[call_sid] = []
        return gather_speech("Hello candidate! Please introduce yourself.")

    # Enforce time limit.
    elapsed = time.time() - call_start_times[call_sid]
    if elapsed > TIME_LIMIT:
        return end_call_and_save_csv(call_sid, "Your time is up. Thank you for your interest. Goodbye!")

    # If candidate doesn't speak, prompt again.
    if not speech_result:
        return gather_speech("Go ahead and continue...")

    # If candidate explicitly asks to end the call.
    if "cut the call" in speech_result.lower() or "end the call" in speech_result.lower():
        call_conversations[call_sid].append(("user", speech_result))
        return end_call_and_save_csv(call_sid, "Thank you for your time. Goodbye!")

    call_conversations[call_sid].append(("user", speech_result))
    prompt_text = build_prompt_with_context(call_sid)
    ai_reply_raw = ai_generate_response(prompt_text)
    ai_reply = ai_reply_raw.strip()

    # Check for the end marker in the AI response.
    ended = "<<<END_CALL>>>" in ai_reply
    if ended:
        ai_reply = ai_reply.replace("<<<END_CALL>>>", "").strip()

    call_conversations[call_sid].append(("ai", ai_reply))
    vr = VoiceResponse()
    vr.say(ai_reply)
    if ended:
        return end_call_and_save_csv(call_sid, "")
    else:
        vr.redirect("/voice")
    return str(vr)

def gather_speech(prompt_text):
    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        speech_timeout="auto",
        action="/voice",
        method="POST"
    )
    gather.say(prompt_text)
    vr.append(gather)
    return str(vr)

def end_call(message):
    vr = VoiceResponse()
    vr.say(message)
    vr.hangup()
    return str(vr)

# --- AI Conclusion: Generate a Beautiful Report Using Gemini ---

def generate_beautiful_report(conversation_str):
    """
    Uses Gemini to analyze the conversation and generate a beautiful, concise report in a Markdown table format.
    The table should have three sections:
    1. Introduction: A brief summary of the interview.
    2. Pros: List concise, relevant points in bullet points.
    3. Cons: List any areas of concern in bullet points.
    4. What AI thinks: A brief conclusion based on the interview.
    """
    prompt = f"""
    You are an expert HR assistant.
    Analyze the following candidate interview conversation and generate a report in a Markdown table format.
    The table should have three sections:
    1. Introduction: A brief summary of the interview.
    2. Pros: List concise, relevant points in bullet points.
    3. Cons: List any areas of concern in bullet points.
    4. What AI thinks: A brief conclusion based on the interview.

    Conversation:
    {conversation_str}

    Please output the report in Markdown format.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        return response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        print(f"[ERROR] Failed to generate beautiful report: {e}")
        return "No report generated."
    
def end_call_and_save_csv(call_sid, final_message):
    vr = VoiceResponse()
    if final_message:
        vr.say(final_message)
    vr.hangup()

    # Get the conversation string for this call.
    conversation_list = call_conversations.get(call_sid, [])
    conversation_str = "\n".join([f"{role.upper()}: {text}" for role, text in conversation_list])
    
    # Save the conversation to CSV (append this call's record)
    save_call_to_csv(call_sid)

    # Generate a beautiful report for this call using Gemini.
    report = generate_beautiful_report(conversation_str)
    
    # Save the report to pros_cons.txt (overwrite previous report).
    with open("pros_cons.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[INFO] Generated report for call {call_sid}.")

    # Send the email with the refined report.
    send_email_with_report()

    call_start_times.pop(call_sid, None)
    call_conversations.pop(call_sid, None)
    return str(vr)

def save_call_to_csv(call_sid):
    conversation_list = call_conversations.get(call_sid, [])
    conversation_str = "\n".join([f"{role.upper()}: {text}" for role, text in conversation_list])
    start_time = call_start_times.get(call_sid, time.time())
    duration_seconds = round(time.time() - start_time, 1)
    new_file = not os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["CallSid", "DurationSec", "Conversation"])
        writer.writerow([call_sid, duration_seconds, conversation_str])
    print(f"[INFO] Saved call {call_sid} to {CSV_FILE} (duration={duration_seconds}s).")

def send_email_with_report():
    report_file = "pros_cons.txt"
    if not os.path.exists(report_file):
        print("[ERROR] No pros_cons.txt file found! Skipping email.")
        return
    with open(report_file, "r", encoding="utf-8") as f:
        refined_report = f.read()
    subject = "AI-Reviewed Hiring Report - Candidate Screening Summary"
    if sendMail(HR_EMAIL, subject, refined_report):
        print(f"[INFO] HR report successfully sent to {HR_EMAIL}.")
    else:
        print("[ERROR] Failed to send HR report email.")

@app.route("/start_call", methods=["GET"])
def start_call():
    to_number = request.args.get("to")
    if not to_number:
        return "Provide ?to=+15551234567", 400
    try:
        call = twilio_client.calls.create(
            from_=TWILIO_CALLER_ID,
            to=to_number,
            url=f"{NGROK_HTTP_URL}/voice"
        )
        return f"Call initiated to {to_number}. SID: {call.sid}"
    except Exception as e:
        return f"Failed: {str(e)}", 500

@app.route('/api/applications')
def api_applications():
    applications = Application.query.all()
    application_list = [app.to_dict() for app in applications]
    return jsonify(application_list)

@app.route('/api/applications/<int:app_id>')
def api_application_detail(app_id):
    application = Application.query.get_or_404(app_id)
    return jsonify(application.to_dict())

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    application = Application.query.get_or_404(app_id)
    db.session.delete(application)
    db.session.commit()
    # Delete CV file
    if os.path.exists(application.cv_path):
        os.remove(application.cv_path)
    return jsonify({'message': 'Application deleted successfully'})


# API endpoints
@app.route('/api/jobs', methods=['POST', 'GET'])
def api_jobs():
    if request.method == 'POST':
        data = request.json
        # Validate required fields
        required_fields = ['title', 'location', 'job_type', 'experience_level', 'description']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create new job
        new_job = Job(
            title=data['title'],
            location=data['location'],
            job_type=data['job_type'],
            experience_level=data['experience_level'],
            description=data['description'],
            salary=data.get('salary')
        )
        
        # Use the property to set requirements properly (serialized to JSON)
        if 'requirements' in data and data['requirements']:
            new_job.requirements_list = data['requirements']
        
        # Handle deadline if provided
        if 'deadline' in data and data['deadline']:
            try:
                new_job.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid deadline format. Use YYYY-MM-DD'}), 400
        
        # Save to database
        db.session.add(new_job)
        db.session.commit()
        
        return jsonify({
            'message': 'Job created successfully',
            'job_id': new_job.id
        }), 201
    
    else: # GET    
        jobs = Job.query.order_by(Job.date_posted.desc()).all()
        job_list = [job.to_dict() for job in jobs]
        return jsonify(job_list)

@app.route('/api/jobs/<int:job_id>')
def api_job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return jsonify(job.to_dict())

@app.route('/apply/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Get form data
    first_name = request.form.get('firstName')
    last_name = request.form.get('lastName')
    email = request.form.get('email')
    phone_number = request.form.get('phone')
    cv = request.files.get('resume')
    # print(first_name, last_name, email, phone_number, cv)

    # Validate required fields
    if not all([first_name, last_name, email, cv]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Save CV file
    if cv and cv.filename.endswith('.pdf'):
        cv_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{cv.filename}"
        cv_path = os.path.join('uploads', cv_filename)
        cv.save(cv_path)
    else:
        return jsonify({'error': 'Invalid file format. Only PDF files are allowed'}), 400
    
    # Create new applicant if not exists
    applicant = Applicant.query.filter_by(email=email).first()
    if not applicant:
        applicant = Applicant(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number
        )
        db.session.add(applicant)
        db.session.commit()
    
    # Create new application
    application = Application(
        applicant_id=applicant.id,
        job_id=job_id,
        cv_path=cv_path
    )
    
    db.session.add(application)
    db.session.commit()

    sendMail(email, "Application Submitted", "Your application has been submitted successfully!")

    
    schedule_calls(application.cv_path, application.id, -1, db, Application, twilio_client, job.to_dict())
    
    return jsonify({'message': 'Your application has been submitted!'}), 201


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5001, debug=True)