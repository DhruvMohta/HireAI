from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from datetime import datetime, timezone
import json
from sendmail import sendMail

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///jobsite.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS for API endpoints
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

# Routes
@app.route('/')
def home():
    return "eyo"

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
    
    return jsonify({'message': 'Your application has been submitted!'}), 201

@app.route('/api/jobs', methods=['POST'])
def add_job():
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

# API endpoints
@app.route('/api/jobs')
def api_jobs():
    jobs = Job.query.order_by(Job.date_posted.desc()).all()
    job_list = [job.to_dict() for job in jobs]
    return jsonify(job_list)

@app.route('/api/jobs/<int:job_id>')
def api_job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return jsonify(job.to_dict())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
