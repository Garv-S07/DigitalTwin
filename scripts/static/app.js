// ==========================================================================
// Cosmic Neil deGrasse Tyson Web Interface Logic (Hologram & Cross-Fade UI)
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatMessages = document.getElementById("chat-messages");
    const typingIndicator = document.getElementById("typing-indicator");
    
    // Selecting the avatar container
    const avatarPanel = document.querySelector(".avatar-panel");
    const subtitleBox = document.getElementById("subtitle-box");
    const subtitleText = document.getElementById("subtitle-text");
    
    // UI Control Buttons
    const settingsToggle = document.getElementById("settings-toggle");
    const settingsModal = document.getElementById("settings-modal");
    const modalClose = document.getElementById("modal-close");
    const colabUrlInput = document.getElementById("colab-url-input");
    const fallbackToggle = document.getElementById("fallback-toggle");
    const settingsSaveBtn = document.getElementById("settings-save-btn");
    const colabStatus = document.getElementById("colab-status");
    
    const ambientToggle = document.getElementById("ambient-toggle");
    const clearChatBtn = document.getElementById("clear-chat");
    
    // History Modal DOM Elements
    const historyToggle = document.getElementById("history-toggle");
    const historyModal = document.getElementById("history-modal");
    const historyClose = document.getElementById("history-close");
    const historyList = document.getElementById("history-list");
    const historyEmpty = document.getElementById("history-empty");
    const historyClearAll = document.getElementById("history-clear-all");

    // Audio Visualizer Canvas Elements
    const canvas = document.getElementById("visualizer-canvas");
    const canvasCtx = canvas.getContext("2d");
    
    // Set Canvas standard dimensions
    canvas.width = 380;
    canvas.height = 380;
    
    // Default configuration matching backend
    const DEFAULT_COLAB_URL = "https://nonreversible-jenna-aeronautic.ngrok-free.dev";
    
    // Uuid generator helper
    function generateUuid() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // State Variables
    let colabUrl = localStorage.getItem("tyson_colab_url") || DEFAULT_COLAB_URL;
    let enableFallback = localStorage.getItem("tyson_enable_fallback") !== "false"; // Default true
    
    let activeEventSource = null;
    let activeAssistantMessageBubble = null;
    
    // Conversation State Tracker
    let currentConversation = {
        id: generateUuid(),
        timestamp: Date.now(),
        summary: "",
        messages: []
    };
    
    // Push the initial welcome message from HTML to the active conversation history
    currentConversation.messages.push({
        sender: "assistant",
        text: "Welcome, traveler! Ask me anything about the vast cosmos, quantum mechanics, stellar evolution, or black holes. Let us explore the wonders of the universe together!",
        time: "Just now"
    });

    // Audio Queue & State
    const audioQueue = [];
    let isPlayingAudio = false;
    let currentAudioElement = null;
    let currentSpeechUtterance = null;
    
    // Procedural Ambient Cosmic Hum Variables
    let ambientAudioCtx = null;
    let ambientGainNode = null;
    let isAmbientPlaying = false;

    // Web Audio Visualizer API Elements
    let visualizerAudioCtx = null;
    let analyser = null;
    const audioSourceMap = new WeakMap(); // Maps HTML5 Audio -> MediaElementSourceNode

    // --------------------------------------------------------------------------
    // Floating Space Dust Particle System
    // --------------------------------------------------------------------------
    class CosmicParticle {
        constructor(w, h) {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.size = 0.8 + Math.random() * 2.2;
            this.speedY = -(0.15 + Math.random() * 0.45); // Constant upward drift
            this.speedX = (Math.random() - 0.5) * 0.2; // Gentle horizontal sway
            this.opacity = 0.15 + Math.random() * 0.5;
            
            // Nebula dust colors: Cyber Cyan or Galactic Violet
            this.color = Math.random() > 0.5 ? "0, 200, 151" : "110, 68, 255";
        }
        update(w, h, speaking) {
            const speedMultiplier = speaking ? 2.5 : 1.0;
            this.y += this.speedY * speedMultiplier;
            this.x += this.speedX * speedMultiplier;
            
            // Loop particles back to bottom
            if (this.y < -10) {
                this.y = h + 10;
                this.x = Math.random() * w;
            }
            if (this.x < -10 || this.x > w + 10) {
                this.x = Math.random() * w;
            }
        }
        draw(ctx, speaking) {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${this.color}, ${this.opacity * (speaking ? 1.5 : 0.65)})`;
            if (speaking) {
                ctx.shadowBlur = 6;
                ctx.shadowColor = `rgba(${this.color}, 0.85)`;
            } else {
                ctx.shadowBlur = 0;
            }
            ctx.fill();
        }
    }

    const particles = [];
    const maxParticles = 35;
    for (let i = 0; i < maxParticles; i++) {
        particles.push(new CosmicParticle(canvas.width, canvas.height));
    }

    // Set initial configuration values in inputs
    colabUrlInput.value = colabUrl;
    fallbackToggle.checked = enableFallback;

    // Check Colab connection status on startup
    checkColabConnection();

    // Start Visualizer & Particle Rendering Loop
    startVisualizerLoop();

    /* ==========================================================================
       Ambient Cosmic Sound Synthesizer (Pure Web Audio API)
       ========================================================================== */
    // --------------------------------------------------------------------------
    // Procedural Ambient Cosmic Music Synthesizer (Web Audio API)
    // Plays beautiful, slowly cross-fading major/minor 7th pads in infinite loops
    // --------------------------------------------------------------------------
    let ambientInterval = null;
    let chordIndex = 0;
    const chords = [
        [130.81, 155.56, 196.00, 233.08], // Cmin7 (Warm space depth)
        [103.83, 130.81, 155.56, 196.00], // Abmaj7 (Luminous expansion)
        [87.31, 130.81, 174.61, 207.65],  // Fm7 (Mysterious distance)
        [98.00, 146.83, 174.61, 233.08]   // G7sus4 (Suspended starlight)
    ];
    let activeOscillators = [];
    let activeGains = [];

    function playCosmicChord(frequencies) {
        if (!ambientAudioCtx) return;
        
        const fadeTime = 3.5; // Smooth 3.5-second cross-fade
        const now = ambientAudioCtx.currentTime;
        
        // 1. Gently fade out previous chord oscillators
        activeGains.forEach(gainNode => {
            gainNode.gain.cancelScheduledValues(now);
            gainNode.gain.setValueAtTime(gainNode.gain.value, now);
            gainNode.gain.exponentialRampToValueAtTime(0.0001, now + fadeTime);
        });
        
        const oldOscillators = [...activeOscillators];
        const oldGains = [...activeGains];
        setTimeout(() => {
            oldOscillators.forEach(osc => { try { osc.stop(); } catch(e){} });
            oldGains.forEach(g => g.disconnect());
        }, fadeTime * 1000);
        
        activeOscillators = [];
        activeGains = [];
        
        // 2. Play new chord pad frequencies
        frequencies.forEach((freq, idx) => {
            const osc = ambientAudioCtx.createOscillator();
            const gainNode = ambientAudioCtx.createGain();
            
            // Soft sine wave for a lush, digital-pad feel
            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now);
            
            // Subtle frequency modulation to create a slow warm stereo-chorus movement
            if (idx % 2 === 0) {
                osc.frequency.setValueAtTime(freq + 0.15, now);
            } else {
                osc.frequency.setValueAtTime(freq - 0.15, now);
            }
            
            // Attack phase: slow 4-second linear gain fade-in to maintain pad texture
            gainNode.gain.setValueAtTime(0.0, now);
            gainNode.gain.linearRampToValueAtTime(0.015, now + 4.0);
            
            // Warm lowpass filter to sweep out any potential harshness
            const filter = ambientAudioCtx.createBiquadFilter();
            filter.type = "lowpass";
            filter.frequency.setValueAtTime(220, now);
            
            osc.connect(filter);
            filter.connect(gainNode);
            gainNode.connect(ambientGainNode);
            
            osc.start(now);
            
            activeOscillators.push(osc);
            activeGains.push(gainNode);
        });
    }

    function initAmbientHum() {
        try {
            ambientAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            
            // Master ambient gain node
            ambientGainNode = ambientAudioCtx.createGain();
            ambientGainNode.gain.setValueAtTime(0.0, ambientAudioCtx.currentTime);
            ambientGainNode.connect(ambientAudioCtx.destination);
            
            console.log("Procedural space music synthesizer initialized.");
        } catch (e) {
            console.error("Failed to initialize Web Audio Synthesizer:", e);
        }
    }

    function toggleAmbientSound() {
        if (!ambientAudioCtx) {
            initAmbientHum();
        }
        
        if (ambientAudioCtx.state === "suspended") {
            ambientAudioCtx.resume();
        }
        
        if (!isAmbientPlaying) {
            // Fade-in master
            ambientGainNode.gain.setValueAtTime(0.0, ambientAudioCtx.currentTime);
            ambientGainNode.gain.linearRampToValueAtTime(1.0, ambientAudioCtx.currentTime + 1.5);
            
            // Play initial chord
            chordIndex = 0;
            playCosmicChord(chords[chordIndex]);
            
            // Schedule endless ambient chord loop (every 9.5 seconds)
            ambientInterval = setInterval(() => {
                chordIndex = (chordIndex + 1) % chords.length;
                playCosmicChord(chords[chordIndex]);
            }, 9500);
            
            ambientToggle.classList.add("active");
            isAmbientPlaying = true;
        } else {
            // Fade-out master
            ambientGainNode.gain.linearRampToValueAtTime(0.0, ambientAudioCtx.currentTime + 2.0);
            
            if (ambientInterval) {
                clearInterval(ambientInterval);
                ambientInterval = null;
            }
            
            // Disconnect and clean up active oscillators
            setTimeout(() => {
                activeOscillators.forEach(osc => { try { osc.stop(); } catch(e){} });
                activeGains.forEach(g => g.disconnect());
                activeOscillators = [];
                activeGains = [];
            }, 2200);
            
            ambientToggle.classList.remove("active");
            isAmbientPlaying = false;
        }
    }

    /* ==========================================================================
       Web Audio API Visualizer Setup & Particle Loops
       ========================================================================== */
    function initVisualizerAudio() {
        if (visualizerAudioCtx) return;
        try {
            visualizerAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyser = visualizerAudioCtx.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.75;
            console.log("Audio visualizer context created.");
        } catch (e) {
            console.error("Failed to initialize visualizer AudioContext:", e);
        }
    }

    function startVisualizerLoop() {
        function draw(time) {
            requestAnimationFrame(draw);
            
            // Clear canvas completely to keep image clean and unobstructed
            canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
        }
        requestAnimationFrame(draw);
    }

    function drawVoiceWaves(ctx, time, amplitude) {
        const cy = canvas.height - 45; // Baseline at the bottom 15% of the card
        const w = canvas.width;
        
        // Layer 1: Dark Indigo Wave (Base)
        drawWaveLayer(ctx, time, amplitude, cy, w, 0.015, 0, "rgba(110, 68, 255, 0.8)", 3.0);
        // Layer 2: Cyber Emerald Wave (Middle)
        drawWaveLayer(ctx, time + 80, amplitude * 0.75, cy, w, 0.026, Math.PI / 3.2, "rgba(0, 200, 151, 0.85)", 2.0);
        // Layer 3: Nova Gold Wave (Tip)
        drawWaveLayer(ctx, time + 160, amplitude * 0.45, cy, w, 0.040, Math.PI / 1.5, "rgba(255, 201, 60, 0.75)", 1.2);
    }

    function drawWaveLayer(ctx, time, amplitude, cy, w, freq, phase, color, lineWidth) {
        ctx.beginPath();
        ctx.lineWidth = lineWidth;
        ctx.strokeStyle = color;
        ctx.lineCap = "round";
        
        // Dynamic drop shadow glow when sound is active
        ctx.shadowBlur = amplitude > 15 ? 12 : 0;
        ctx.shadowColor = color;
        
        // Baseline height is 3.5px when silent, expands to 48px during speaking envelopes
        const ampFactor = amplitude > 5 ? (amplitude / 255) * 48 : 3.5;
        
        for (let x = 0; x < w; x++) {
            // Fade wave completely out at left & right borders to prevent hard clipping
            const edgeFade = Math.sin((x / w) * Math.PI);
            const y = cy + Math.sin(x * freq + time * 0.007 + phase) * ampFactor * edgeFade;
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
    }

    /* ==========================================================================
       Cross-Fade Portrait State Coordination
       ========================================================================== */
    // Keywords triggering the Explaining (Deep Thought) state
    const explainingKeywords = [
        "think", "thought", "ponder", "universe", "cosmos", "galaxy", "galaxies",
        "quantum", "understand", "obligation", "obligate", "wait", "look", "see",
        "wonder", "imagine", "science", "physics", "black hole", "astrophysics",
        "dimension", "space", "time", "stars", "gravity"
    ];

    function getSpeakingStateForText(text) {
        const lowerText = text.toLowerCase();
        return explainingKeywords.some(keyword => lowerText.includes(keyword)) ? 'explaining' : 'speaking';
    }

    function setPortraitState(state) {
        const portraits = {
            'idle': 'portrait-idle',
            'thinking': 'portrait-thinking',
            'speaking': 'portrait-speaking',
            'explaining': 'portrait-explaining'
        };
        
        Object.entries(portraits).forEach(([key, id]) => {
            const img = document.getElementById(id);
            if (img) {
                img.classList.toggle("active", key === state);
            }
        });

        // Set state class on avatar panel for custom premium styling glows
        if (avatarPanel) {
            avatarPanel.classList.remove("idle", "thinking", "speaking", "explaining");
            avatarPanel.classList.add(state);
        }
    }

    /* ==========================================================================
       Colab Status Checker
       ========================================================================== */
    async function checkColabConnection() {
        colabStatus.textContent = "Verifying connection...";
        colabStatus.className = "";
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 4500);
            
            // Backend secure server-to-server CORS-bypass probe API
            const probeUrl = `/api/probe?colab_url=${encodeURIComponent(colabUrl)}`;
            const response = await fetch(probeUrl, { 
                method: "GET",
                signal: controller.signal
            }).catch(() => null);
            
            clearTimeout(timeoutId);
            
            if (response && response.ok) {
                const data = await response.json().catch(() => ({}));
                if (data.online) {
                    colabStatus.textContent = "Online / Reachable";
                    colabStatus.className = "status-online";
                    return;
                }
            }
            colabStatus.textContent = "Offline or Incorrect URL";
            colabStatus.className = "status-offline";
        } catch (e) {
            colabStatus.textContent = "Offline";
            colabStatus.className = "status-offline";
        }
    }

    /* ==========================================================================
       Queue & Audio Coordination System
       ========================================================================== */
    function enqueueAudio(item) {
        audioQueue.push(item);
        if (!isPlayingAudio) {
            processAudioQueue();
        }
    }

    function processAudioQueue() {
        if (audioQueue.length === 0) {
            isPlayingAudio = false;
            // Stop speaking state and return to idle pose
            setPortraitState('idle');
            subtitleBox.classList.add("hidden");
            currentSpeechUtterance = null;
            return;
        }
        
        isPlayingAudio = true;
        const currentItem = audioQueue.shift();
        
        // Update subtitle text
        subtitleText.textContent = currentItem.text;
        subtitleBox.classList.remove("hidden");
        
        // Determine whether standard speaking or explaining state should be used
        const targetState = getSpeakingStateForText(currentItem.text);
        setPortraitState(targetState);
        
        // Initialize Web Audio visualizer context if needed
        initVisualizerAudio();
        if (visualizerAudioCtx && visualizerAudioCtx.state === "suspended") {
            visualizerAudioCtx.resume();
        }
        
        if (currentItem.type === "url") {
            currentSpeechUtterance = null;
            
            if (currentAudioElement) {
                currentAudioElement.pause();
            }
            
            currentAudioElement = new Audio(currentItem.url);
            
            // Connect to real-time Web Audio analyser
            if (visualizerAudioCtx && analyser) {
                try {
                    if (!audioSourceMap.has(currentAudioElement)) {
                        const source = visualizerAudioCtx.createMediaElementSource(currentAudioElement);
                        source.connect(analyser);
                        analyser.connect(visualizerAudioCtx.destination);
                        audioSourceMap.set(currentAudioElement, source);
                    }
                } catch (err) {
                    console.warn("Audio element Web Audio routing skipped:", err);
                }
            }
            
            currentAudioElement.onended = () => {
                processAudioQueue();
            };
            
            currentAudioElement.onerror = () => {
                console.warn("WAV playback failed, falling back to local speech synthesis...");
                if (enableFallback) {
                    speakBrowserFallback(currentItem.text);
                } else {
                    processAudioQueue();
                }
            };
            
            currentAudioElement.play().catch(err => {
                console.error("Audio playback error:", err);
                if (enableFallback) {
                    speakBrowserFallback(currentItem.text);
                } else {
                    processAudioQueue();
                }
            });
        } else {
            // Local Web Speech Fallback Mode
            speakBrowserFallback(currentItem.text);
        }
    }

    function speakBrowserFallback(text) {
        if (!window.speechSynthesis) {
            console.error("Speech Synthesis API not supported.");
            processAudioQueue();
            return;
        }
        
        window.speechSynthesis.cancel();
        
        currentSpeechUtterance = new SpeechSynthesisUtterance(text);
        
        // Select a deep male voice from the English voices list
        const voices = window.speechSynthesis.getVoices();
        const englishVoices = voices.filter(v => v.lang.startsWith("en") || v.lang.includes("en-"));
        
        // List of known male voice keywords ordered by voice quality/realism
        const maleKeywords = ["guy", "david", "christopher", "eric", "ryan", "george", "male", "alex", "daniel", "fred", "mark", "thomas", "james", "steven"];
        let selectedVoice = null;
        
        // 1. Try to find a premium natural/online male voice first
        for (const kw of maleKeywords) {
            selectedVoice = englishVoices.find(v => {
                const nameLower = v.name.toLowerCase();
                return nameLower.includes(kw) && (nameLower.includes("natural") || nameLower.includes("online"));
            });
            if (selectedVoice) break;
        }
        
        // 2. Try to find any male voice by keyword
        if (!selectedVoice) {
            for (const kw of maleKeywords) {
                selectedVoice = englishVoices.find(v => v.name.toLowerCase().includes(kw));
                if (selectedVoice) break;
            }
        }
        
        // 3. Fallback: try standard natural/online voice
        if (!selectedVoice) {
            selectedVoice = englishVoices.find(v => v.name.toLowerCase().includes("natural") || v.name.toLowerCase().includes("online"));
        }
        
        // 4. Ultimate fallback: pick any English voice
        if (!selectedVoice && englishVoices.length > 0) {
            selectedVoice = englishVoices[0];
        }
        
        if (selectedVoice) {
            currentSpeechUtterance.voice = selectedVoice;
        }
        
        // Speech configurations optimized for Neil deGrasse Tyson tone
        currentSpeechUtterance.rate = 1.02;
        currentSpeechUtterance.pitch = 0.82; // Lowered pitch to create a deeper male resonance
        
        currentSpeechUtterance.onend = () => {
            processAudioQueue();
        };
        
        currentSpeechUtterance.onerror = (e) => {
            console.error("Speech Synthesis error:", e);
            processAudioQueue();
        };
        
        window.speechSynthesis.speak(currentSpeechUtterance);
    }

    function stopAllSpeech() {
        audioQueue.length = 0;
        isPlayingAudio = false;
        currentSpeechUtterance = null;
        
        if (currentAudioElement) {
            currentAudioElement.pause();
            currentAudioElement = null;
        }
        
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
        
        setPortraitState('idle');
        subtitleBox.classList.add("hidden");
    }

    /* ==========================================================================
       SSE Real-time Chat Integration
       ========================================================================== */
    function appendMessage(sender, text, timeText = null) {
        const messageWrapper = document.createElement("div");
        messageWrapper.classList.add("message-wrapper", sender);
        
        const avatar = document.createElement("div");
        avatar.classList.add("message-avatar");
        avatar.textContent = sender === "user" ? "🙋" : "🌌";
        
        const container = document.createElement("div");
        container.classList.add("message-bubble-container");
        
        const bubble = document.createElement("div");
        bubble.classList.add("message-bubble");
        bubble.textContent = text;
        
        const time = document.createElement("span");
        time.classList.add("message-time");
        time.textContent = timeText || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        container.appendChild(bubble);
        container.appendChild(time);
        messageWrapper.appendChild(avatar);
        messageWrapper.appendChild(container);
        
        chatMessages.appendChild(messageWrapper);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return bubble;
    }

    async function sendPrompt(promptText) {
        stopAllSpeech();
        
        // Append user bubble
        appendMessage("user", promptText);
        
        // Record user message
        currentConversation.messages.push({
            sender: "user",
            text: promptText,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
        
        // Set first user prompt as conversation summary if empty
        if (!currentConversation.summary) {
            currentConversation.summary = promptText.length > 45 ? promptText.substring(0, 42) + "..." : promptText;
        }
        
        // Show typing indicator
        typingIndicator.classList.remove("hidden");
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Set portrait state to thinking during generation wait
        setPortraitState('thinking');
        
        // Do NOT append the assistant message bubble yet! Keep it null
        activeAssistantMessageBubble = null;
        
        // Warm up / initialize visualizer context
        initVisualizerAudio();
        
        const sseUrl = `/api/chat?prompt=${encodeURIComponent(promptText)}&colab_url=${encodeURIComponent(colabUrl)}&session_id=${encodeURIComponent(currentConversation.id)}`;
        
        activeEventSource = new EventSource(sseUrl);
        
        activeEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === "usage") {
                    updateContextProgressBar(data.tokens, data.max_tokens);
                }
                else if (data.type === "text") {
                    // Create the assistant bubble ONLY on the first token received
                    if (!activeAssistantMessageBubble) {
                        typingIndicator.classList.add("hidden");
                        activeAssistantMessageBubble = appendMessage("assistant", "");
                    }
                    
                    activeAssistantMessageBubble.textContent += data.text;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                } 
                else if (data.type === "audio") {
                    enqueueAudio({
                        type: "url",
                        url: data.audio_url,
                        text: data.text
                    });
                } 
                else if (data.type === "audio_fallback") {
                    if (enableFallback) {
                        enqueueAudio({
                            type: "fallback",
                            text: data.text
                        });
                    }
                } 
                else if (data.type === "done") {
                    activeEventSource.close();
                    typingIndicator.classList.add("hidden");
                    // If no response bubble was created, append a notice
                    if (!activeAssistantMessageBubble) {
                        activeAssistantMessageBubble = appendMessage("assistant", "We got no response from the cosmos. Please try again.");
                    }
                    
                    // Record assistant message
                    currentConversation.messages.push({
                        sender: "assistant",
                        text: activeAssistantMessageBubble.textContent,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    });
                    
                    // Auto persist conversation session to history list
                    saveCurrentConversation();
                } 
                else if (data.type === "citations") {
                    if (activeAssistantMessageBubble) {
                        const citDiv = document.createElement("div");
                        citDiv.className = "citation-box";
                        citDiv.innerHTML = `<strong>Sources:</strong> ${data.text}`;
                        activeAssistantMessageBubble.appendChild(citDiv);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                } 
                else if (data.type === "error") {
                    activeEventSource.close();
                    typingIndicator.classList.add("hidden");
                    if (!activeAssistantMessageBubble) {
                        activeAssistantMessageBubble = appendMessage("assistant", "");
                    }
                    activeAssistantMessageBubble.textContent = "Error: " + data.message;
                    activeAssistantMessageBubble.style.color = "#f05454";
                }
            } catch (err) {
                console.error("Error parsing SSE message stream:", err);
            }
        };
        
        activeEventSource.onerror = (err) => {
            console.error("SSE stream connection error:", err);
            activeEventSource.close();
            typingIndicator.classList.add("hidden");
        };
    }

    function updateContextProgressBar(tokens, maxTokens) {
        const barFill = document.getElementById('context-bar-fill');
        const numbers = document.getElementById('context-numbers');
        if (barFill && numbers) {
            // Calculate percentage, capping at 100% just in case
            const percent = Math.min((tokens / maxTokens) * 100, 100);
            barFill.style.width = `${percent}%`;
            
            // Format numbers with commas
            numbers.textContent = `${tokens.toLocaleString()} / ${maxTokens.toLocaleString()}`;
            
            // Turn red if getting dangerously close
            if (percent > 90) {
                barFill.style.backgroundColor = '#f05454';
                barFill.style.boxShadow = '0 0 15px rgba(240, 84, 84, 0.8)';
            } else {
                barFill.style.backgroundColor = '#00c897';
                barFill.style.boxShadow = '0 0 10px rgba(0, 200, 151, 0.5)';
            }
        }
    }

    /* ==========================================================================
       Event Listeners & Form Controls
       ========================================================================== */
    
    // Handle Chat Form Submission
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;
        
        userInput.value = "";
        sendPrompt(text);
    });

    // Toggle Ambient Cosmic Sound
    ambientToggle.addEventListener("click", () => {
        toggleAmbientSound();
    });
    
    // Clear Chat / Start New Conversation
    clearChatBtn.addEventListener("click", () => {
        if (confirm("Are you sure you want to start a new cosmic journey? This will clear the current screen.")) {
            startNewConversation();
        }
    });

    // History Persistence and Loading Core Logic
    function saveCurrentConversation() {
        if (currentConversation.messages.length <= 1) return; // Only contains welcome greeting, don't save
        
        let histories = JSON.parse(localStorage.getItem("tyson_chat_histories") || "[]");
        const index = histories.findIndex(h => h.id === currentConversation.id);
        
        if (index !== -1) {
            histories[index] = currentConversation;
        } else {
            histories.unshift(currentConversation); // Add new dialog to the front
        }
        
        localStorage.setItem("tyson_chat_histories", JSON.stringify(histories));
    }

    function startNewConversation() {
        stopAllSpeech();
        chatMessages.innerHTML = "";
        
        currentConversation = {
            id: generateUuid(),
            timestamp: Date.now(),
            summary: "",
            messages: []
        };
        
        // Reset the context visualizer to 0 tokens
        updateContextProgressBar(0, 1000000);
        
        const welcomeText = "Welcome, traveler! Ask me anything about the vast cosmos, quantum mechanics, stellar evolution, or black holes. Let us explore the wonders of the universe together!";
        appendMessage("assistant", welcomeText);
        
        currentConversation.messages.push({
            sender: "assistant",
            text: welcomeText,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
    }

    function renderHistoryList() {
        historyList.innerHTML = "";
        let histories = JSON.parse(localStorage.getItem("tyson_chat_histories") || "[]");
        
        if (histories.length === 0) {
            historyEmpty.classList.remove("hidden");
            historyList.classList.add("hidden");
            return;
        }
        
        historyEmpty.classList.add("hidden");
        historyList.classList.remove("hidden");
        
        histories.forEach(conv => {
            const dateStr = new Date(conv.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            
            const item = document.createElement("div");
            item.classList.add("history-item");
            item.setAttribute("data-id", conv.id);
            
            const details = document.createElement("div");
            details.classList.add("history-item-details");
            
            const time = document.createElement("span");
            time.classList.add("history-item-time");
            time.textContent = dateStr;
            
            const summary = document.createElement("span");
            summary.classList.add("history-item-summary");
            summary.textContent = conv.summary || "Dialogue Session";
            
            details.appendChild(time);
            details.appendChild(summary);
            
            // Delete button for specific history conversation
            const deleteBtn = document.createElement("button");
            deleteBtn.classList.add("btn-delete-history");
            deleteBtn.title = "Delete dialogue session";
            deleteBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
            
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                if (confirm("Delete this dialogue from history?")) {
                    deleteConversation(conv.id);
                }
            });
            
            item.appendChild(details);
            item.appendChild(deleteBtn);
            
            // Click to load conversation
            item.addEventListener("click", () => {
                loadConversation(conv.id);
            });
            
            historyList.appendChild(item);
        });
    }

    function deleteConversation(id) {
        let histories = JSON.parse(localStorage.getItem("tyson_chat_histories") || "[]");
        histories = histories.filter(h => h.id !== id);
        localStorage.setItem("tyson_chat_histories", JSON.stringify(histories));
        
        if (currentConversation.id === id) {
            startNewConversation();
        }
        renderHistoryList();
    }

    function loadConversation(id) {
        let histories = JSON.parse(localStorage.getItem("tyson_chat_histories") || "[]");
        const conv = histories.find(h => h.id === id);
        if (!conv) return;
        
        stopAllSpeech();
        chatMessages.innerHTML = "";
        
        currentConversation = conv;
        
        // Re-append loaded dialogue messages
        currentConversation.messages.forEach(msg => {
            appendMessage(msg.sender, msg.text, msg.time);
        });
        
        historyModal.classList.add("hidden");
    }

    // Clear Chat & Save current session first
    clearChatBtn.addEventListener("click", () => {
        if (confirm("Start a new dialogue session? Your current conversation will be saved to history.")) {
            saveCurrentConversation();
            startNewConversation();
        }
    });

    // History Modal Event Listeners
    historyToggle.addEventListener("click", () => {
        renderHistoryList();
        historyModal.classList.remove("hidden");
    });

    historyClose.addEventListener("click", () => {
        historyModal.classList.add("hidden");
    });

    historyClearAll.addEventListener("click", () => {
        if (confirm("Clear all dialogue history permanently? This cannot be undone.")) {
            localStorage.removeItem("tyson_chat_histories");
            startNewConversation();
            renderHistoryList();
        }
    });

    // Settings Modal Toggles
    settingsToggle.addEventListener("click", () => {
        checkColabConnection();
        settingsModal.classList.remove("hidden");
    });

    modalClose.addEventListener("click", () => {
        settingsModal.classList.add("hidden");
    });

    window.addEventListener("click", (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.add("hidden");
        }
        if (e.target === historyModal) {
            historyModal.classList.add("hidden");
        }
    });

    // Save Configuration
    settingsSaveBtn.addEventListener("click", () => {
        const inputUrl = colabUrlInput.value.trim().replace(/\/$/, "");
        if (inputUrl) {
            colabUrl = inputUrl;
            localStorage.setItem("tyson_colab_url", colabUrl);
        }
        
        enableFallback = fallbackToggle.checked;
        localStorage.setItem("tyson_enable_fallback", enableFallback);
        
        settingsModal.classList.add("hidden");
        checkColabConnection();
    });

    // Allow voices to load
    if (window.speechSynthesis) {
        window.speechSynthesis.getVoices();
    }
});
