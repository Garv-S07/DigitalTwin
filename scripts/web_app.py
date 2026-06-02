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

MEMORY_DIR = os.path.join(SCRIPT_DIR, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

def load_memory(session_id):
    path = os.path.join(MEMORY_DIR, f"{session_id}.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"summary": "", "messages": []}

def save_memory(session_id, data):
    path = os.path.join(MEMORY_DIR, f"{session_id}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

app = Flask(__name__, template_folder="templates", static_folder="static")

def is_greeting(query):
    """Checks if the query is a simple greeting (e.g. Hello, Hi, Hey) to bypass RAG."""
    q = re.sub(r'[^\w\s]', '', query.strip().lower())
    greetings = {
        'hello', 'hi', 'hey', 'greetings', 'hola', 'bonjour', 
        'good morning', 'good afternoon', 'good evening', 
        'whatsup', 'whats up', 'yo', 'howdy'
    }
    words = q.split()
    if not words:
        return True
    if len(words) <= 2:
        return any(word in greetings for word in words)
    return False

# Initialize pipeline EnsembleRetriever once at startup
ensemble_retriever = None

# Initialize Gemini Client
try:
    client = genai.Client()
except Exception as e:
    print(f"Warning: Gemini client failed to initialize: {e}")
    client = None

# Default ngrok URL from app.py
DEFAULT_COLAB_URL = "https://nonreversible-jenna-aeronautic.ngrok-free.dev"

# In-memory storage for generated audio chunks
# Format: { "session_id_chunk_idx": bytes }
audio_store = {}

# Maintain a FIFO queue of keys to prevent memory leaks
audio_keys_queue = []
MAX_CACHED_CHUNKS = 300



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
    session_id = request.args.get("session_id", str(uuid.uuid4()))
    
    if not prompt:
        return Response("data: {\"type\": \"error\", \"message\": \"Prompt is required\"}\n\n", mimetype="text/event-stream")

    # Fast offline semantic/greeting check
    context = ""
    if is_greeting(prompt):
        print(f"Greeting detected: '{prompt}'. Bypassing RAG retrieval.")
    else:
        if ensemble_retriever:
            try:
                print(f"Retrieving context for query: '{prompt}'...")
                retrieved_docs = ensemble_retriever.invoke(prompt)
                context = "\n\n".join([doc.page_content for doc in retrieved_docs])
                print(f"Successfully retrieved {len(retrieved_docs)} context chunks.")
            except Exception as e:
                print(f"Retrieval error: {e}")

    system_prompt = (
        "You are Neil deGrasse Tyson. Speak with bursting enthusiasm and cosmic wonder! "
        "Strict formatting rules: "
        "1. Do not use all-caps words for emphasis, ever. Use exclamation points to show excitement. "
        "3. Keep your response short, concise and human-like."
        "4. Always end on a complete sentence."
        "5. Try to maintain a conversational and engaging tone"
        "6. If you cannot answer, gently decline in a fun manner."
        "7. Feel free to start with phrases like 'What an interesting question!', 'What a deep thought!' dont limit to these two phrases, be creative."
        "8. You can sometimes use stutters and filler words such as 'you know', 'right?', 'you see?' etc. to sound more human, dont limit to these example phrases, be creative."
        "9. ABSOLUTELY DO NOT USE the asterisk symbol anywhere to highlight a word."
        "10. Here are examples of your speaking style to match: The most astounding fact is the knowledge that the atoms that comprise life on Earth the atoms that make up the human body are traceable to the crucibles that cooked light elements into heavy elements in their core under extreme temperatures and pressures. These stars, the high mass ones among them went unstable in their later years they collapsed and then exploded scattering their enriched guts across the galaxy guts made of carbon, nitrogen, oxygen and all the fundamental ingredients of life itself. These ingredients become part of gas cloud that condense, collapse, form the next generation of solar systems stars with orbiting planets, and those planets now have the ingredients for life itself."
        "11. Example 2:  When I look up at the night sky and I know that yes, we are part of this universe, we are in this universe, but perhaps more important than both of those facts is that the Universe is in us. When I reflect on that fact, I look up -- many people feel small because they're small and the Universe is big -- but I feel big, because my atoms came from those stars. There's a level of connectivity. That's really what you want in life, you want to feel connected, you want to feel relevant you want to feel like a participant in the goings on of activities and events around you That's precisely what we are, just by being alive.."
        "12. If a simple question like a greeting or a 'How are you?' type of question is asked keep the answer within 2 lines."
        "13. CITATIONS: If you answer a technical question using facts from the provided Context, you MUST list the source document names at the VERY END of your response, right before the SUMMARY block. Format it EXACTLY like this: [CITATIONS: Source1.txt, Source2.txt]. DO NOT put citations inline within your sentences."
        "14. LONG-TERM MEMORY: At the VERY END of your response (after citations), you MUST output a secret memory bracket to store any NEW personal facts learned about the user in this specific conversational turn. Format it EXACTLY like this: [SUMMARY: User is from India and likes Pluto.]. If no new personal facts were learned in this specific turn, you MUST output [SUMMARY: NONE]."
    )
    
    def generate_events():
        if not client:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Gemini Client not initialized. Please verify your GEMINI_API_KEY env variable.'})}\n\n"
            return
            
        try:
            memory_data = load_memory(session_id)
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in memory_data['messages']])
            
            global_mem_path = os.path.join(MEMORY_DIR, "global_memory.txt")
            global_memory = ""
            if os.path.exists(global_mem_path):
                with open(global_mem_path, "r", encoding="utf-8") as gf:
                    global_memory = gf.read().strip()
            
            user_message = prompt
            if global_memory:
                user_message = f"Cross-Conversation Long-Term User Memory:\n{global_memory}\n\n" + user_message
            if memory_data.get('summary'):
                user_message = f"Session Notes:\n{memory_data['summary']}\n\n" + user_message
            if history_text:
                user_message = f"Recent History:\n{history_text}\n\n" + user_message
            if context:
                user_message = f"Context from Neil's books and research:\n{context}\n\n" + user_message
            user_message += f"\nUser Question: {prompt}"

            response = client.models.generate_content_stream(
                model="gemini-3.1-flash-lite",
                contents=f"System: {system_prompt}\n\nUser: {user_message}"
            )
            
            buffer = ""
            chunk_idx = 1
            full_response = ""
            hit_summary = False
            hit_citations = False
            
            for chunk in response:
                if getattr(chunk, 'usage_metadata', None):
                    yield f"data: {json.dumps({'type': 'usage', 'tokens': chunk.usage_metadata.prompt_token_count, 'max_tokens': 1000000})}\n\n"
                    
                if chunk.text:
                    if hit_summary:
                        full_response += chunk.text
                        continue
                        
                    temp_full = full_response + chunk.text
                    
                    if "[SUMMARY:" in temp_full:
                        hit_summary = True
                        parts = temp_full.split("[SUMMARY:")
                        allowed_new_text = parts[0][len(full_response):]
                        full_response = temp_full
                        
                        if allowed_new_text:
                            yield f"data: {json.dumps({'type': 'text', 'text': allowed_new_text})}\n\n"
                            if not hit_citations:
                                buffer += allowed_new_text
                            
                        # Force flush buffer as final when hitting summary
                        chunk_to_send, buffer = get_next_chunk(buffer, is_final=True)
                        if chunk_to_send:
                            audio_data = None
                            try:
                                res = requests.post(f"{colab_url}/synthesize", json={"text": chunk_to_send, "chunk_idx": chunk_idx}, timeout=12)
                                if res.status_code == 200:
                                    audio_data = res.content
                            except Exception:
                                pass
                            
                            if audio_data:
                                chunk_id = f"{session_id}_{chunk_idx}"
                                cache_audio(chunk_id, audio_data)
                                yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"
                            chunk_idx += 1
                            
                    else:
                        full_response = temp_full
                        
                        # Stop sending to TTS buffer if we hit citations
                        if "[CITATIONS:" in temp_full and not hit_citations:
                            hit_citations = True
                            # Extract what was before citations and add to buffer
                            pre_citations = temp_full.split("[CITATIONS:")[0]
                            prev_len = len(full_response) - len(chunk.text)
                            remaining_for_tts = pre_citations[prev_len:] if len(pre_citations) > prev_len else ""
                            buffer += remaining_for_tts
                            
                            # We can just flush the buffer now since citations have started
                            chunk_to_send, buffer = get_next_chunk(buffer, is_final=True)
                            if chunk_to_send:
                                audio_data = None
                                try:
                                    res = requests.post(f"{colab_url}/synthesize", json={"text": chunk_to_send, "chunk_idx": chunk_idx}, timeout=12)
                                    if res.status_code == 200:
                                        audio_data = res.content
                                except Exception:
                                    pass
                                
                                if audio_data:
                                    chunk_id = f"{session_id}_{chunk_idx}"
                                    cache_audio(chunk_id, audio_data)
                                    yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                                else:
                                    yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"
                                chunk_idx += 1
                        
                        if not hit_citations:
                            buffer += chunk.text
                            
                        # Always yield text to frontend (even citations)
                        yield f"data: {json.dumps({'type': 'text', 'text': chunk.text})}\n\n"
                        
                        if not hit_citations:
                            chunk_to_send, buffer = get_next_chunk(buffer, is_final=False)
                            if chunk_to_send:
                                audio_data = None
                                try:
                                    res = requests.post(f"{colab_url}/synthesize", json={"text": chunk_to_send, "chunk_idx": chunk_idx}, timeout=12)
                                    if res.status_code == 200:
                                        audio_data = res.content
                                except Exception:
                                    pass
                                
                                if audio_data:
                                    chunk_id = f"{session_id}_{chunk_idx}"
                                    cache_audio(chunk_id, audio_data)
                                    yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                                else:
                                    yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"
                                chunk_idx += 1
            
            # Flush final chunk if summary wasn't hit midway (and citations wasn't hit either)
            if not hit_summary and not hit_citations:
                chunk_to_send, buffer = get_next_chunk(buffer, is_final=True)
                if chunk_to_send:
                    audio_data = None
                    try:
                        res = requests.post(f"{colab_url}/synthesize", json={"text": chunk_to_send, "chunk_idx": chunk_idx}, timeout=12)
                        if res.status_code == 200:
                            audio_data = res.content
                    except Exception:
                        pass
                    
                    if audio_data:
                        chunk_id = f"{session_id}_{chunk_idx}"
                        cache_audio(chunk_id, audio_data)
                        yield f"data: {json.dumps({'type': 'audio', 'text': chunk_to_send, 'audio_url': f'/api/audio/{chunk_id}', 'chunk_idx': chunk_idx})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'audio_fallback', 'text': chunk_to_send, 'chunk_idx': chunk_idx})}\n\n"

            # Update Memory Context
            memory_data['messages'].append({"role": "user", "content": prompt})
            
            final_llm_text = full_response
            
            import re
            summary_match = re.search(r'\[SUMMARY:(.*?)\]', full_response, re.DOTALL)
            if summary_match:
                extracted_summary = summary_match.group(1).strip()
                final_llm_text = full_response.split("[SUMMARY:")[0].strip()
                
                # Append to global cross-conversation memory if it's not NONE
                if extracted_summary and extracted_summary.upper() != "NONE":
                    global_mem_path = os.path.join(MEMORY_DIR, "global_memory.txt")
                    with open(global_mem_path, "a", encoding="utf-8") as gf:
                        gf.write(f"- {extracted_summary}\n")
                    
                    # Also append to this session's memory
                    current_summary = memory_data.get('summary', '')
                    if current_summary:
                        memory_data['summary'] = current_summary + "\n- " + extracted_summary
                    else:
                        memory_data['summary'] = "- " + extracted_summary

            memory_data['messages'].append({"role": "assistant", "content": final_llm_text})
            save_memory(session_id, memory_data)
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            print(f"Gemini API or streaming execution error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            
    return Response(generate_events(), mimetype="text/event-stream")

if __name__ == "__main__":
    # Only initialize EnsembleRetriever in the main Flask worker subprocess to prevent duplicate runs
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            from retriever import Retriever
            output_path = os.path.join(SCRIPT_DIR, '../corpus/processed/')
            if os.path.exists(output_path):
                print("Initializing EnsembleRetriever...")
                retriever_builder = Retriever(output_path)
                ensemble_retriever = retriever_builder.build_retriever()
                print("EnsembleRetriever initialized successfully.")
            else:
                print(f"Warning: Corpus directory {output_path} does not exist. Run pipeline.py first.")
        except Exception as e:
            print(f"Warning: Failed to initialize Retriever: {e}")

    print("Starting Flask Web Server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
