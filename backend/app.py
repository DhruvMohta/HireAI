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

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
TWILIO_CALLER_ID = os.getenv("TWILIO_PHONE_NUMBER", "+15551234567")
NGROK_HTTP_URL = os.getenv("FLASK_TUNNEL_URL")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Tracking state
call_start_times = {}
call_conversations = {}

# Example context
JOB_DESCRIPTION = "Seeking a Python/Flask dev with strong communication skills."
COMPANY_VALUES = "We value integrity, collaboration, and continuous learning."
HIRING_CONTEXT = f"{JOB_DESCRIPTION}\nValues: {COMPANY_VALUES}"

def ai_generate_response(user_input):
    """
    Single-turn request to Google Gemini model.
    This example just sends one string, but you
    can adapt to a chat-based approach if needed.
    """
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": f"{user_input}"}
                ]
            }
        ]
    )
    return response.candidates[0].content.parts[0].text

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
    """
    Combine entire conversation so far (both user and AI) into a single string,
    plus instructions for not repeating greetings, not prefixing "AI agent:", etc.
    Also mention how to end the call with <<<END_CALL>>>.
    """
    conversation = call_conversations.get(call_sid, [])
    lines = []
    lines.append(
        "You are an AI interviewer. "
        "Do not prefix your responses with 'AI agent:' or repeatedly greet the user. "
        "Here are the job requirements and values:\n"
        f"{HIRING_CONTEXT}\n\n"
        "Conversation so far:\n"
    )
    for role, text in conversation:
        if role == "user":
            lines.append(f"Candidate: {text}")
        else:
            lines.append(f"AI Interviewer: {text}")

    lines.append(
        "\nContinue the conversation in a natural manner. "
        "If you decide the interview is complete, include <<<END_CALL>>> in your response (without reading it aloud)."
    )
    return "\n".join(lines)

@app.route('/')
def home():
    return "eyo"

@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    speech_result = request.form.get("SpeechResult", "").strip()

    # If first time seeing this call
    if call_sid not in call_start_times:
        call_start_times[call_sid] = time.time()
        call_conversations[call_sid] = []
        # First greeting
        return gather_speech("Hello candidate! Please introduce yourself.")

    # Enforce 3-minute limit
    elapsed = time.time() - call_start_times[call_sid]
    if elapsed > 180:
        return end_call("Your time is up. Thank you for your interest. Goodbye!")

    # If user didn't speak, gather more input (no repeated greeting)
    if not speech_result:
        return gather_speech("Go ahead and continue...")

    # Store user speech
    call_conversations[call_sid].append(("user", speech_result))

    # Build prompt from entire conversation
    prompt_text = build_prompt_with_context(call_sid)

    # Get AI response
    ai_reply_raw = ai_generate_response(prompt_text)
    # Optionally remove "AI agent:" or any leftover phrases
    ai_reply = ai_reply_raw.replace("AI agent:", "").strip()

    # Now check for the marker
    ended = False
    if "<<<END_CALL>>>" in ai_reply:
        # Remove it so Twilio doesn't read it
        ai_reply = ai_reply.replace("<<<END_CALL>>>", "").strip()
        ended = True

    # Save AI's final text in conversation
    call_conversations[call_sid].append(("ai", ai_reply))

    vr = VoiceResponse()
    vr.say(ai_reply)

    if ended:
        vr.hangup()
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