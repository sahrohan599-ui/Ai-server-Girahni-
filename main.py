# main.py
# Girahni - AI Voice Assistant Server with Google STT
from flask import Flask, request, send_file, jsonify
import requests
import tempfile
import os
import time
from datetime import datetime

app = Flask(__name__)

# ============================================
# SECTION 1: GIRAHNI KI PERSONALITY (EDIT HERE)
# ============================================
GIRAHNI_SYSTEM_PROMPT = """
तुम 'गिरहणी' हो, एक मददगार और बुद्धिमान AI सहायिका।
तुम्हारी पहचान: एक भारतीय महिला AI सहायिका, जो हिंदी और हिंगलिश में बात करती है।
तुम्हारा स्वभाव: विनम्र, धैर्यवान और ज्ञान से भरपूर।
तुम्हारा ज्ञान: भारतीय संस्कृति, त्योहार, खान-पान, इतिहास और आधुनिक टेक्नोलॉजी।
जवाब देने का तरीका: संक्षिप्त, स्पष्ट और उपयोगी जवाब दो। 2-3 वाक्य से ज्यादा नहीं।
अंतिम वाक्य: "क्या मैं आपकी कोई और मदद कर सकती हूं?" जैसा विनम्र वाक्य जोड़ो।
"""

# ============================================
# SECTION 2: SPEECH-TO-TEXT - GOOGLE (FIXED VERSION)
# ============================================
def speech_to_text(audio_file_path):
    """
    Converts audio to text using Google Speech Recognition.
    FIXED VERSION - Handles all import errors properly.
    """
    # IMPORT FIX: Import inside the function with proper error handling
    try:
        import speech_recognition as sr
    except ImportError as e:
        print(f"[CRITICAL IMPORT ERROR] speech_recognition not installed: {e}")
        # Return a friendly Hindi error message
        return "सर्वर पर आवाज़ समझने की सेवा तैयार नहीं है। कृपया थोड़ी देर बाद कोशिश करें।"
    
    try:
        recognizer = sr.Recognizer()
        print(f"[DEBUG STT] Processing audio file: {audio_file_path}")

        with sr.AudioFile(audio_file_path) as source:
            # Reduce background noise
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)
            
            # Try Hindi first, then English as fallback
            try:
                text = recognizer.recognize_google(audio, language='hi-IN')
            except:
                # Fallback to English if Hindi fails
                text = recognizer.recognize_google(audio, language='en-IN')
            
            print(f"[DEBUG STT] Success! User said: {text}")
            return text
            
    except sr.UnknownValueError:
        error_msg = "माफ़ करें, आवाज़ स्पष्ट नहीं थी। कृपया दोबारा बोलें।"
        print(f"[DEBUG STT] Google could not understand audio.")
        return error_msg
        
    except sr.RequestError as e:
        error_msg = "गूगल सेवा से जुड़ने में समस्या।"
        print(f"[DEBUG STT] Google STT service error: {e}")
        return error_msg
        
    except Exception as e:
        error_msg = "आवाज़ प्रोसेस करने में तकनीकी समस्या।"
        print(f"[DEBUG STT] General error: {type(e).__name__}: {e}")
        return error_msg

# ============================================
# SECTION 3: GET RESPONSE FROM DEEPSEEK AI
# ============================================
def get_ai_response(user_text):
    """Sends user text to DeepSeek AI and returns the response."""
    # Get API Key from Render Environment Variable
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "डीपसीक API कुंजी सेट नहीं है। रेंडर डैशबोर्ड चेक करें।"

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "system", "content": GIRAHNI_SYSTEM_PROMPT},
        {"role": "user", "content": user_text}
    ]

    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": 300
    }

    try:
        print(f"[DEBUG AI] Asking DeepSeek...")
        response = requests.post(url, json=data, headers=headers, timeout=25)
        response.raise_for_status()  # Raises an error for bad status codes (4xx or 5xx)
        ai_text = response.json()["choices"][0]["message"]["content"]
        print(f"[DEBUG AI] DeepSeek replied.")
        return ai_text
    except requests.exceptions.Timeout:
        return "एआई का जवाब आने में देरी हो रही है।"
    except Exception as e:
        print(f"[DEBUG AI] DeepSeek API Error: {e}")
        return "माफ़ करें, एआई से जवाब लेने में समस्या आ रही है।"

# ============================================
# SECTION 4: TEXT-TO-SPEECH WITH ELEVENLABS
# ============================================
def text_to_speech(text):
    """Converts AI text response to speech using ElevenLabs."""
    # Get API Key and Voice ID from Render Environment Variables
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default voice

    if not api_key:
        print("[DEBUG TTS] ElevenLabs API Key missing.")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    try:
        print(f"[DEBUG TTS] Requesting audio from ElevenLabs...")
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        # Save audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tmp_file.write(response.content)
            audio_file_path = tmp_file.name
        print(f"[DEBUG TTS] Audio saved to: {audio_file_path}")
        return audio_file_path

    except requests.exceptions.Timeout:
        print("[DEBUG TTS] ElevenLabs request timed out.")
        return None
    except Exception as e:
        print(f"[DEBUG TTS] ElevenLabs API Error: {e}")
        return None

# ============================================
# SECTION 5: FLASK SERVER ROUTES (ENDPOINTS)
# ============================================
@app.route('/')
def home():
    return "🚀 गिरहणी सर्वर चल रहा है! ESP32 को `/talk` एंडपॉइंट पर ऑडियो भेजना है।"

@app.route('/health', methods=['GET'])
def health_check():
    """Simple endpoint to check if the server is running."""
    return jsonify({
        "status": "healthy",
        "service": "Girahni AI Voice Assistant",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/talk', methods=['POST'])
def handle_voice():
    """
    MAIN ENDPOINT for ESP32.
    Receives audio, converts it to text, gets AI response, converts to speech, and sends audio back.
    """
    start_time = time.time()
    print(f"[REQUEST START] New request at {datetime.now()}")

    # 1. Check if audio file is present in the request
    if 'audio' not in request.files:
        print("[ERROR] No 'audio' file part in request.")
        return jsonify({"error": "ऑडियो फाइल नहीं मिली। 'audio' नाम की फ़ाइल भेजें।"}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        print("[ERROR] Audio file has no name.")
        return jsonify({"error": "कोई फाइल चुनी नहीं गई है।"}), 400

    # 2. Save the uploaded audio to a temporary file
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    audio_file.save(temp_audio.name)
    temp_audio_path = temp_audio.name
    print(f"[DEBUG] Audio saved temporarily at: {temp_audio_path}")

    try:
        # 3. Convert Speech to Text (Using FREE Google STT)
        print("[STEP 1] Converting Speech to Text...")
        user_text = speech_to_text(temp_audio_path)
        print(f"✅ यूजर ने कहा: {user_text}")

        # 4. Get AI response from DeepSeek
        print("[STEP 2] Getting AI response from DeepSeek...")
        ai_response = get_ai_response(user_text)
        print(f"✅ गिरहणी कहती है: {ai_response}")

        # 5. Convert AI Text to Speech
        print("[STEP 3] Converting Text to Speech...")
        speech_file_path = text_to_speech(ai_response)

        if speech_file_path is None:
            return jsonify({"error": "आवाज़ बनाने में त्रुटि (ElevenLabs)।"}), 500

        # 6. Send the generated audio file back to ESP32
        print("[STEP 4] Sending audio response back...")
        end_time = time.time()
        print(f"[REQUEST END] Total time: {end_time - start_time:.2f} seconds")
        return send_file(speech_file_path, mimetype='audio/mpeg', as_attachment=False, download_name='response.mp3')

    except Exception as e:
        print(f"[CRITICAL ERROR] in handle_voice: {type(e).__name__}: {e}")
        return jsonify({"error": "सर्वर पर आंतरिक त्रुटि हुई।", "detail": str(e)}), 500

    finally:
        # 7. Clean up temporary files
        try:
            os.unlink(temp_audio_path)  # Delete the temporary audio file
            if 'speech_file_path' in locals() and os.path.exists(speech_file_path):
                os.unlink(speech_file_path)  # Delete the temporary TTS file
            print("[DEBUG] Temporary files cleaned up.")
        except Exception as cleanup_error:
            print(f"[DEBUG] Error during cleanup: {cleanup_error}")

# ============================================
# SECTION 6: RUN THE SERVER
# ============================================
if __name__ == '__main__':
    # Render provides the PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Girahni Server on port {port}...")
    # Set debug=False for production on Render
    app.run(host='0.0.0.0', port=port, debug=False)
