import os
import time
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client

from google import genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
