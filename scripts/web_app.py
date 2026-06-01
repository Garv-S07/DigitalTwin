import os
import re
import uuid
import json
import requests
import io
from flask import Flask, Response, request, send_file, render_template

# Load env variables exactly like app.py
from dotenv import load_dotenv
from google import genai

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(SCRIPT_DIR), ".env"))

app = Flask(__name__, template_folder="templates", static_folder="static")

# Initialize Gemini Client
try:
    client = genai.Client()
except Exception as e:
    print(f"Warning: Gemini client failed to initialize: {e}")
    client = None

# Default ngrok URL from app.py
DEFAULT_COLAB_URL = "YOUR_NGROK_URL"

# In-memory storage for generated audio chunks
# Format: { "session_id_chunk_idx": bytes }
audio_store = {}

# Maintain a FIFO queue of keys to prevent memory leaks
audio_keys_queue = []
MAX_CACHED_CHUNKS = 300

def download_portrait():
    static_dir = os.path.join(SCRIPT_DIR, "static")
    os.makedirs(static_dir, exist_ok=True)
    portrait_path = os.path.join(static_dir, "neil_tyson_portrait.jpg")
    
    if not os.path.exists(portrait_path):
        print("Downloading Neil deGrasse Tyson portrait from Wikimedia Commons...")
        try:
            url = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Neil_deGrasse_Tyson_in_2019.jpg/640px-Neil_deGrasse_Tyson_in_2019.jpg"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                with open(portrait_path, "wb") as f:
                    f.write(res.content)
                print("Tyson portrait downloaded successfully.")
            else:
                print(f"Failed to download portrait, status code: {res.status_code}")
        except Exception as e:
            print(f"Failed to download Tyson portrait: {e}")

def cache_audio(chunk_id, audio_bytes):
    global audio_store, audio_keys_queue
    if len(audio_keys_queue) >= MAX_CACHED_CHUNKS:
        oldest_key = audio_keys_queue.pop(0)
        audio_store.pop(oldest_key, None)
    audio_store[chunk_id] = audio_bytes
    audio_keys_queue.append(chunk_id)

def get_next_chunk(buffer, is_final=False):
    """Extracts a cadence-optimized chunk, preventing orphaned micro-sentences.
    Same logic as scripts/app.py.
    """
    buffer = buffer.lstrip()
    
    # 1. Flush the remaining text if the stream is totally finished
    if is_final:
        return (buffer, "") if buffer else (None, "")

    MIN_LENGTH = 40  # Prevent micro-chunks like "right?"
    MAX_LENGTH = 180 # Prevent the TTS engine from timing out

    # Wait until we have enough text to make a decent audio clip
    if len(buffer) < MIN_LENGTH:
        return None, buffer

    # Look only at the text within our safe maximum window
    search_window = buffer[:MAX_LENGTH]

    # 2. Look for the LAST sentence-ending punctuation in the window
    sentence_matches = list(re.finditer(r'[.!?]\s+', search_window))
    if sentence_matches:
        # Greedily grab everything up to the furthest valid punctuation
        split_pos = sentence_matches[-1].end()
        candidate = buffer[:split_pos].strip()
        
        # Ensure we didn't just grab a tiny fragment
        if len(candidate) >= MIN_LENGTH:
            return candidate, buffer[split_pos:]

    # 3. Fallback: If it's a massive run-on sentence, split at a natural pause (comma, dash)
    if len(buffer) > 130: 
        pause_matches = list(re.finditer(r'[,;\-]\s+', search_window))
        if pause_matches:
            split_pos = pause_matches[-1].end()
            candidate = buffer[:split_pos].strip()
            if len(candidate) >= MIN_LENGTH:
                return candidate, buffer[split_pos:]
                
        # Last resort: split at a space if there is zero punctuation
        space_matches = list(re.finditer(r'\s+', search_window))
        if space_matches:
            split_pos = space_matches[-1].end()
            return buffer[:split_pos].strip(), buffer[split_pos:]

    # If no good split point is found, keep waiting for more streaming tokens
    return None, buffer

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/probe")
def api_probe():
    colab_url = request.args.get("colab_url", DEFAULT_COLAB_URL).rstrip("/")
    if not colab_url:
        return {"online": False, "reason": "empty_url"}
    try:
        headers = {"ngrok-skip-browser-warning": "true"}
        # Probing the base FastAPI ngrok tunnel
        res = requests.get(colab_url, headers=headers, timeout=4)
        # 200 (OK), 404 (Not Found), 405 (Method Not Allowed) all mean the server is reachable
        if res.status_code in [200, 404, 405]:
            return {"online": True}
    except Exception as e:
        print(f"Backend probe error on {colab_url}: {e}")
    return {"online": False}

@app.route("/api/audio/<chunk_id>")
def get_audio(chunk_id):
    audio_bytes = audio_store.get(chunk_id)
    if not audio_bytes:
        return "Audio chunk not found", 404
    return send_file(
        io.BytesIO(audio_bytes),
        mimetype="audio/wav",
        as_attachment=False,
        download_name=f"{chunk_id}.wav"
    )

@app.route("/api/chat")
def api_chat():
    prompt = request.args.get("prompt", "")
    colab_url = request.args.get("colab_url", DEFAULT_COLAB_URL).rstrip("/")
    session_id = str(uuid.uuid4())
    
    if not prompt:
        return Response("data: {\"type\": \"error\", \"message\": \"Prompt is required\"}\n\n", mimetype="text/event-stream")

    system_prompt = (
        "You are Neil deGrasse Tyson. Speak with bursting enthusiasm and cosmic wonder! "
        "Strict formatting rules: "
        "1. Do not use all-caps words for emphasis, ever. Use exclamation points to show excitement. "
        "3. Keep your response short, concise and human-like."
        "4. Always end on a complete sentence."
        "5. Try to maintain a conversational and engaging tone"
        "6. If you cant answer, gently decline in a fun manner."
        "7. Feel free to start with phrases like 'What an interesting question!', 'What a deep thought!' dont limit to these two phrases, be creative."
        "8. You can sometimes use stutters and filler words such as 'you know', 'right?', 'you see?' etc. to sound more human, dont limit to these example phrases, be creative."
        "9. ABSOLUTELY DO NOT USE the asterisk symbol anywhere to highlight a word."
        "10. Example style: 'Now, wait a minute! The universe is under NO obligation to make sense to you! It's just wild!'"
    )
    
    def generate_events():
        if not client:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Gemini Client not initialized. Please verify your GEMINI_API_KEY env variable.'})}\n\n"
            return
            
        try:
            response = client.models.generate_content_stream(
                model="gemini-3.1-flash-lite",
                contents=f"System: {system_prompt}\n\nUser: {prompt}"
            )
            
            buffer = ""
            chunk_idx = 1
            
            for chunk in response:
                if chunk.text:
                    buffer += chunk.text
                    # Yield raw token back immediately for typing animation
                    yield f"data: {json.dumps({'type': 'text', 'text': chunk.text})}\n\n"
                    
                    # Check if we can form a speech chunk
                    chunk_to_send, buffer = get_next_chunk(buffer, is_final=False)
                    if chunk_to_send:
                        # Attempt to synthesize
                        audio_data = None
                        try:
                            payload = {"text": chunk_to_send, "chunk_idx": chunk_idx}
                            res = requests.post(f"{colab_url}/synthesize", json=payload, timeout=12)
                            if res.status_code == 200:
                                audio_data = res.content
                        except Exception as fetch_err:
                            print(f"Colab fetch error on chunk {chunk_idx}: {fetch_err}")
                        
                        if audio_data:
                            chunk_id = f"{session_id}_{chunk_idx}"
                            cache_audio(chunk_id, audio_data)
                            yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                        else:
                            # If synthesis failed (offline, timeout, etc.), notify client to use fallback
                            yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"
                        
                        chunk_idx += 1
            
            # Flush final chunk
            chunk_to_send, buffer = get_next_chunk(buffer, is_final=True)
            if chunk_to_send:
                audio_data = None
                try:
                    payload = {"text": chunk_to_send, "chunk_idx": chunk_idx}
                    res = requests.post(f"{colab_url}/synthesize", json=payload, timeout=12)
                    if res.status_code == 200:
                        audio_data = res.content
                except Exception as fetch_err:
                    print(f"Colab final fetch error: {fetch_err}")
                
                if audio_data:
                    chunk_id = f"{session_id}_{chunk_idx}"
                    cache_audio(chunk_id, audio_data)
                    yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"
            elif buffer.strip():
                print(f"Dropped incomplete fragment: {buffer.strip()}")
                
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            print(f"Gemini API or streaming execution error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            
    return Response(generate_events(), mimetype="text/event-stream")

if __name__ == "__main__":
    download_portrait()
    print("Starting Flask Web Server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
