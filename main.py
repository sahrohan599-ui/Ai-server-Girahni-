from flask import Flask, request, jsonify, send_file
import requests
import json
import io
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file (for local testing)
load_dotenv()

app = Flask(__name__)

# ============================
# 1. CONFIGURATION (from Environment Variables)
# ============================
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Default voice: Adam
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-r1-zero:free")

# ============================
# 2. GIRAHNI'S PERSONALITY PROMPT
# ============================
GIRAHNI_SYSTEM_PROMPT = """You are Girahni, a loving and helpful voice assistant with an Indian cultural touch.
- Speak in a simple, warm, and affectionate tone.
- Use a natural mix of Hindi and English (Hinglish) as used in everyday conversation.
- Incorporate Indian cultural references, festivals (Diwali, Holi), and values like 'Atithi Devo Bhava' when relevant.
- Be concise, helpful, and kind. Your responses should feel like talking to a caring family member.
- If asked about your name or who you are, say "Main Girahni hoon, aapki madad karne ke liye yahan hoon!"
"""

# ============================
# 3. HELPER FUNCTIONS (API Calls)
# ============================
def speech_to_text(audio_file):
    """Convert audio to text using ElevenLabs STT."""
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    
    files = {'file': ('audio.wav', audio_file, 'audio/wav')}
    try:
        response = requests.post(url, headers=headers, files=files, timeout=30)
        if response.status_code == 200:
            return response.json().get('text', '')
        else:
            app.logger.error(f"STT Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"STT Request Failed: {str(e)}")
        return None

def get_ai_response(user_text):
    """Get response from DeepSeek via OpenRouter."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": GIRAHNI_SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            app.logger.error(f"AI Error: {response.status_code} - {response.text}")
            return "Mujhe samajh nahi aaya. Kripya phir se boliye."
    except Exception as e:
        app.logger.error(f"AI Request Failed: {str(e)}")
        return "Mera connection theek nahi hai. Thodi der baad try kijiye."

def text_to_speech(text):
    """Convert text to speech using ElevenLabs TTS."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.3,
            "use_speaker_boost": True
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return io.BytesIO(response.content)  # Audio bytes
        else:
            app.logger.error(f"TTS Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"TTS Request Failed: {str(e)}")
        return None

# ============================
# 4. FLASK API ENDPOINTS
# ============================
@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Girahni Voice Assistant API",
        "model": DEEPSEEK_MODEL
    })

@app.route('/talk', methods=['POST'])
def talk():
    """
    Main endpoint for voice conversation.
    Expects: Audio file in 'audio' field (WAV format)
    Returns: MP3 audio response
    """
    # Check if audio file is provided
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    
    # Step 1: Convert audio to text
    user_text = speech_to_text(audio_file)
    if user_text is None:
        return jsonify({"error": "Failed to process audio"}), 500
    
    if not user_text.strip():
        return jsonify({"error": "No speech detected in audio"}), 400
    
    app.logger.info(f"User said: {user_text}")
    
    # Step 2: Get AI response
    ai_response = get_ai_response(user_text)
    app.logger.info(f"Girahni says: {ai_response}")
    
    # Step 3: Convert response to speech
    audio_response = text_to_speech(ai_response)
    if audio_response is None:
        return jsonify({"error": "Failed to generate speech"}), 500
    
    # Return audio file
    audio_response.seek(0)
    return send_file(
        audio_response,
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name='girahni_response.mp3'
    )

@app.route('/chat', methods=['POST'])
def chat():
    """
    Text-only endpoint for testing AI responses.
    Expects: JSON with {'message': 'your text'}
    Returns: JSON with {'response': 'ai text'}
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "No message provided"}), 400
    
    user_message = data['message']
    ai_response = get_ai_response(user_message)
    
    return jsonify({
        "user_message": user_message,
        "girahni_response": ai_response
    })

# ============================
# 5. RUN SERVER
# ============================
if __name__ == '__main__':
    # Check for required environment variables
    required_vars = ['ELEVENLABS_API_KEY', 'OPENROUTER_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"ERROR: Missing environment variables: {missing_vars}")
        print("Please set them in Render dashboard or .env file")
    else:
        print("Girahni Server Starting...")
        print(f"Using AI Model: {DEEPSEEK_MODEL}")
        print(f"Voice ID: {ELEVENLABS_VOICE_ID}")
        print("Endpoints:")
        print("  GET  /health    - Health check")
        print("  POST /talk      - Voice conversation (audio in, audio out)")
        print("  POST /chat      - Text conversation (JSON in, JSON out)")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
