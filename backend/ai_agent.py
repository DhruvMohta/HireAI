import os
import time
import csv
import re
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
from sendmail import sendMail  # Import email sending function from sendmail.py
from google import genai

# Load environment variables
load_dotenv()

# Twilio & SMTP Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
TWILIO_CALLER_ID = os.getenv("TWILIO_PHONE_NUMBER", "+15551234567")
NGROK_HTTP_URL = os.getenv("FLASK_TUNNEL_URL")
HR_EMAIL = os.getenv("HR_EMAIL", "demo@gifuzzz.eu")

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# AI Model Initialization
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)

# Tracking call state
call_start_times = {}       # {call_sid: float}
call_conversations = {}     # {call_sid: [("user", text), ("ai", text), ...]}

# Time limit for calls (3 minutes)
TIME_LIMIT = 180  
CSV_FILE = "call_results.csv"

# Job description context
JOB_DESCRIPTION = "Seeking a Python/Flask developer with strong communication skills."
COMPANY_VALUES = "We value integrity, collaboration, and continuous learning."
HIRING_CONTEXT = f"{JOB_DESCRIPTION}\nValues: {COMPANY_VALUES}"


# --- Conversational Agent Functions (Core Logic Unchanged) ---

def ai_generate_response(user_input):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[{"role": "user", "parts": [{"text": f"{user_input}"}]}]
    )
    # Strip "AI Agent:" and return just the content
    return response.candidates[0].content.parts[0].text.strip()


def build_prompt_with_context(call_sid):
    conversation = call_conversations.get(call_sid, [])
    lines = [
        "You are an AI interviewer conducting a brief phone screening for a Python/Flask developer role.",
        "Your objective is to quickly assess the candidate by asking one or two very short, direct questions at a time.",
        "Keep your responses under 2 sentences and avoid long explanations.",
        "Focus on key points: technical skills, notice period, and problem-solving ability.",
        "If the candidate seems unresponsive or requests to end the call (e.g., says 'cut the call'), wrap up immediately.",
        "",
        f"Job Description: {HIRING_CONTEXT}",
        "",
        "Conversation so far:"
    ]
    for role, text in conversation:
        lines.append(f"{'Candidate' if role == 'user' else 'AI Interviewer'}: {text}")
    lines.append("\nIf you decide the interview is complete, include <<<END_CALL>>> in your response (without reading it aloud).")
    return "\n".join(lines)


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
        return "Provide ?to=+1234567890", 400
    try:
        call = twilio_client.calls.create(
            from_=TWILIO_CALLER_ID,
            to=to_number,
            url=f"{NGROK_HTTP_URL}/voice"
        )
        return f"Call initiated to {to_number}. SID: {call.sid}"
    except Exception as e:
        return f"Failed: {str(e)}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
