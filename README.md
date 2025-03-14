# HireAI: AI-Powered Recruitment Assistant
HireAI is a GenAI application designed to help recruiters optimize their hiring process by automating candidate screening, conducting preliminary interviews, and providing detailed assessments.

## 📋 Features

- Automated CV parsing and scoring
- AI-powered phone interviews with candidates
- Detailed interview reports with pros and cons analysis
- Web interface for managing job postings and applications
- Email notifications for both candidates and recruiters

## 🚀 Installation

### Prerequisites

- Python 3.9+
- Node.js 16+
- Twilio account
- Google Gemini API key

### Backend Setup

1. Clone the repository:
```sh
git clone https://github.com/Holy-Hack-2025/Team-9-Bomboclaat-PSI
cd Team-9-Bomboclaat-PSI
```

2. Install backend dependencies:
```sh
cd backend
pip install -r requirements.txt
```

3. Create a .env file in the backend directory with the following variables:
```
SMTP_SERVER=your_smtp_server
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_password
SENDER_EMAIL=your_email
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_phone
GEMINI_API_KEY=your_gemini_api_key
FLASK_TUNNEL_URL=your_ngrok_url_for_twilio_webhook
HR_EMAIL=recruiter_email
```

### Frontend Setup

1. Install frontend dependencies:
```sh
cd ../frontend
npm install
```

2. Update the API URL in constants.ts if needed.

## 🖥️ Running the Application

1. Start the backend server:
```sh
cd backend
python app.py
```

2. In a separate terminal, start the frontend development server:
```sh
cd frontend
npm run dev
```

3. Access the application at `http://localhost:4321`

## 📊 How It Works

### Step 0: Job Application population
- You must add your jobs via a post request to http://localhost:5001/jobs similar to this
```json
  {
    "title": "Bomboclaat Engineer",
    "location": "Leuven, BE",
    "job_type": "Full-time",
    "experience_level": "Junior",
    "description": "We are looking for a skilled bomboclaat engineer to join our team.",
    "salary": "€ 120k-300k",
    "requirements": [
        "Bachelor's degree in Computer Science or related field",
        "3+ years of experience in software development",
        "Proficiency in Patience and Sleep depravation"
    ],
    "deadline": "2025-04-01"
}
```

### Step 1: Job Application Submission
- Candidates browse available job positions on the platform
- They select a position and complete the application form
- The candidate uploads their CV (PDF format)

### Step 2: Automated CV Screening
- The system uses Google's Gemini AI to parse the CV
- Key information is extracted: education, skills, experience
- A matching score is calculated based on job requirements
- The application is stored in the system with its score

### Step 3: AI Phone Interview
- If the application meets the basic requirements, an AI agent calls the candidate
- The AI conducts a short, focused interview to assess:
  - Technical skills relevant to the position
  - Experience level
  - Notice period
  - General fit and interest in the position
- The conversation is recorded and transcribed

### Step 4: Interview Analysis and Reporting
- After the call, the AI generates a concise report including:
  - Summary of the interview
  - Pros of the candidate
  - Potential concerns or areas to explore
  - AI's general assessment
- The report is emailed to the recruiter for review

### Step 5: Human Decision Making
- The recruiter reviews the application, CV score, and interview report
- **Important**: The final hiring decision always remains with the human recruiter
- The system provides decision support, not replacement

## ⚠️ Important Notes

- Always ensure candidate consent for AI interviews
- Keep personal data secure and compliant with privacy regulations
- The system is designed to augment human recruiters, not replace them
- Regular review of AI behavior and bias detection is recommended

## 📞 Support

If you encounter any issues or have questions, please contact our support team or file an issue on GitHub.