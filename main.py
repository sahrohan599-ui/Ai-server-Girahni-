from flask import Flask, request, send_file
import requests
import json
import tempfile
import os
from datetime import datetime

app = Flask(__name__)

# ============================================
# गिरहणी का व्यक्तित्व - यहां एडिट करें
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
# स्पीच-टू-टेक्स्ट फंक्शन - एक विकल्प चुनें
# ============================================
def speech_to_text(audio_file_path):
    """
    ऑडियो को टेक्स्ट में बदलें। 
    नीचे दो विकल्पों में से सिर्फ एक का इस्तेमाल करें।
    """
    
    # विकल्प 1: गूगल स्पीच रिकग्निशन (बिल्कुल फ्री)
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="hi-IN")
            return text
    except Exception as e:
        print(f"Google STT error: {e}")
    
    # विकल्प 2: असेंबलीएआई (फ्री टियर - बेहतर सटीकता)
    # 1. पहले https://www.assemblyai.com/ से फ्री API Key लें
    # 2. Render पर ASSEMBLYAI_API_KEY नाम का Environment Variable सेट करें
    """
    try:
        api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not api_key:
            return "API Key सेट नहीं है।"
        
        headers = {"authorization": api_key}
        upload_url = "https://api.assemblyai.com/v2/upload"
        
        with open(audio_file_path, "rb") as f:
            upload_response = requests.post(upload_url, headers=headers, data=f)
        audio_url = upload_response.json()["upload_url"]
        
        transcript_url = "https://api.assemblyai.com/v2/transcript"
        transcript_request = {"audio_url": audio_url, "language_code": "hi"}
        transcript_response = requests.post(transcript_url, json=transcript_request, headers=headers)
        transcript_id = transcript_response.json()["id"]
        
        polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        while True:
            polling_response = requests.get(polling_url, headers=headers)
            status = polling_response.json()["status"]
            if status == "completed":
                return polling_response.json()["text"]
            elif status == "failed":
                return "ट्रांसक्रिप्शन फेल हो गया।"
    except Exception as e:
        print(f"AssemblyAI error: {e}")
    """
    
    return "आवाज़ समझ नहीं आई, कृपया दोबारा बोलें।"

# ============================================
# एआई और टीटीएस फंक्शन
# ============================================
def get_ai_response(user_text):
    """DeepSeek AI से जवाब लाएं"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")  # Render से लेगा
    if not api_key:
        return "DeepSeek API Key सेट नहीं है।"
    
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
        response = requests.post(url, json=data, headers=headers, timeout=30)
        return response.json()["choices"][0]["message"]["content"]
    except:
        return "माफ़ करें, जवाब देने में समस्या आ रही है।"

def text_to_speech(text):
    """ElevenLabs से आवाज़ बनाएं"""
    api_key = os.environ.get("ELEVENLABS_API_KEY")  # Render से लेगा
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # डिफ़ॉल्ट आवाज़
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(response.content)
            return tmp_file.name
    except:
        return None

# ============================================
# मुख्य एंडपॉइंट
# ============================================
@app.route('/')
def home():
    return "गिरहणी सर्वर चल रहा है! ESP32 को /talk एंडपॉइंट पर ऑडियो भेजना है।"

@app.route('/talk', methods=['POST'])
def handle_voice():
    """ESP32 यहां ऑडियो भेजेगा"""
    try:
        if 'audio' not in request.files:
            return "ऑडियो फाइल नहीं मिली", 400
        
        audio_file = request.files['audio']
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
            audio_file.save(tmp_audio.name)
            audio_path = tmp_audio.name
        
        user_text = speech_to_text(audio_path)
        os.unlink(audio_path)
        
        ai_response = get_ai_response(user_text)
        speech_file = text_to_speech(ai_response)
        
        if not speech_file:
            return "आवाज़ बनाने में त्रुटि", 500
            
        return send_file(speech_file, mimetype='audio/mpeg')
        
    except Exception as e:
        return f"सर्वर त्रुटि: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
