from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import json
import io
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app with CORS
app = Flask(__name__)
CORS(app)  # This enables CORS for all origins

# ============================
# CONFIGURATION
# ============================
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-r1-zero:free")

# ============================
# GIRAHNI PERSONALITY
# ============================
GIRAHNI_SYSTEM_PROMPT = """You are Girahni, a loving and helpful voice assistant with an Indian cultural touch.
- Speak in a simple, warm, and affectionate tone.
- Use a natural mix of Hindi and English (Hinglish) as used in everyday conversation.
- Incorporate Indian cultural references, festivals (Diwali, Holi), and values like 'Atithi Devo Bhava' when relevant.
- Be concise, helpful, and kind. Your responses should feel like talking to a caring family member.
- If asked about your name or who you are, say "Main Girahni hoon, aapki madad karne ke liye yahan hoon!"
"""

# ============================
# HELPER FUNCTIONS
# ============================
def speech_to_text(audio_file):
    """Convert audio to text using ElevenLabs STT."""
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    
    # CRITICAL FIX: Add model_id parameter (was missing)
    params = {
        'model_id': 'scribe_v1'  # ElevenLabs STT model
    }
    
    files = {'file': ('audio.wav', audio_file, 'audio/wav')}
    
    try:
        response = requests.post(url, headers=headers, files=files, params=params, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get('text', '')
        else:
            app.logger.error(f"STT Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"STT Request Failed: {str(e)}")
        return None

def get_ai_response(user_text):
    """Get response from DeepSeek via OpenRouter."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://girahni.com",  # OpenRouter requires this
        "X-Title": "Girahni Assistant"
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
            app.logger.error(f"AI Error {response.status_code}: {response.text}")
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
            return io.BytesIO(response.content)
        else:
            app.logger.error(f"TTS Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"TTS Request Failed: {str(e)}")
        return None

# ============================
# API ENDPOINTS
# ============================
@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Girahni Voice Assistant API",
        "model": DEEPSEEK_MODEL,
        "endpoints": ["/health (GET)", "/chat (POST)", "/talk (POST)"]
    })

@app.route('/chat', methods=['POST'])
def chat():
    """
    Text-only endpoint for testing AI responses.
    Expects: JSON with {'message': 'your text'}
    Returns: JSON with {'response': 'ai text'}
    """
    try:
        # FIX: Proper JSON parsing
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided"}), 400
        
        user_message = data['message']
        ai_response = get_ai_response(user_message)
        
        return jsonify({
            "user_message": user_message,
            "girahni_response": ai_response
        })
    except Exception as e:
        app.logger.error(f"Chat endpoint error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/talk', methods=['POST'])
def talk():
    """
    Main endpoint for voice conversation.
    Expects: Audio file in 'audio' field (WAV format)
    Returns: MP3 audio response
    """
    try:
        # Check if audio file is provided
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        # Validate file
        if audio_file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
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
            as_attachment=False,
            download_name='girahni_response.mp3'
        )
        
    except Exception as e:
        app.logger.error(f"Talk endpoint error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# ============================
# RUN SERVER
# ============================
if __name__ == '__main__':
    # Check for required environment variables
    required_vars = ['ELEVENLABS_API_KEY', 'OPENROUTER_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"ERROR: Missing environment variables: {missing_vars}")
        print("Please set them in Render dashboard or .env file")
        print("\nRequired variables:")
        print("1. ELEVENLABS_API_KEY - from ElevenLabs dashboard")
        print("2. ELEVENLABS_VOICE_ID - e.g., 'pNInz6obpgDQGcFmaJgB'")
        print("3. OPENROUTER_API_KEY - from OpenRouter keys page")
        print("4. DEEPSEEK_MODEL - e.g., 'deepseek/deepseek-r1-zero:free'")
    else:
        print("=" * 50)
        print("GIRAHNI SERVER STARTING...")
        print("=" * 50)
        print(f"Server URL: https://ai-server-girahni.onrender.com")
        print(f"AI Model: {DEEPSEEK_MODEL}")
        print(f"Voice ID: {ELEVENLABS_VOICE_ID}")
        print("\nAvailable Endpoints:")
        print("  GET  /health    - Health check")
        print("  POST /chat      - Text conversation")
        print("  POST /talk      - Voice conversation")
        print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
