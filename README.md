# Digital Twin: Neil deGrasse Tyson

This project is an interactive, voice-enabled AI assistant designed to act as a digital twin of Neil deGrasse Tyson. It uses Retrieval-Augmented Generation (RAG) to ground the assistant's knowledge in a provided corpus of books and texts, while employing a local vector database for fast, rate-limit-free document retrieval. 

The architecture is built on a Flask backend and a vanilla JavaScript frontend, utilizing Google's Gemini models for text generation and a remote endpoint for real-time Text-to-Speech (TTS) synthesis.

## Core Features

* **Retrieval-Augmented Generation (RAG):** Uses local HuggingFace embeddings (`all-MiniLM-L6-v2`) and a Chroma vector database to parse and retrieve relevant context from a local corpus of texts and books.
* **Real-time Streaming & TTS:** Streams the LLM response chunk-by-chunk to the frontend using Server-Sent Events (SSE). The text is simultaneously sent to a remote Colab endpoint for real-time speech synthesis, minimizing audio latency.
* **Short-Term & Long-Term Memory:**
  * **Short-Term (Session):** Maintains individual conversation histories in JSON format, allowing the model to recall context within a single session.
  * **Long-Term (Global):** The model automatically extracts new personal facts learned about the user during conversations and appends them to a structured `global_memory.json` file. This preserves timelines and session data, and is seamlessly injected into the context window for true cross-conversation memory.
* **Context Window Visualizer:** The frontend features a dynamic progress bar that extracts precise token usage metadata from the Gemini API, visually displaying the current utilization of the model's context window.
* **Document Citations:** The model is strictly prompted to cite its source materials when answering technical questions based on the retrieved context. These citations are parsed and displayed in the UI without being spoken aloud by the TTS engine.

## Prerequisites

* Python 3.9+
* A valid Gemini API Key.
* A running TTS Colab endpoint (for voice synthesis).

## Setup Instructions

1. **Environment Variables:**
   Create a `.env` file in the root directory and add your API key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. **Virtual Environment (Recommended):**
   It is highly recommended to create and activate a virtual environment before installing dependencies.
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Dependencies:**
   Install the required Python packages using pip:
   ```bash
   pip install -r requirements.txt
   ```

4. **Prepare the Corpus:**
   The data pipeline is configured to process specific file types from distinct directories:
   - Place your `.txt` files (e.g., raw books) into the `corpus/raw/books/` directory.
   - Place your `.pdf` files (e.g., research papers) into the `corpus/raw/research/` directory.

5. **Run the Data Pipeline:**
   Execute the pipeline script to extract text from PDFs, chunk the documents, and embed them into the local Chroma database.
   ```bash
   python scripts/pipeline.py
   ```

6. **Start the Web Server:**
   Launch the Flask backend.
   ```bash
   python scripts/web_app.py
   ```
   The application will be accessible at `http://127.0.0.1:5000`.

7. **Configure Text-to-Speech (TTS):**
   Once the web interface is open, click the **Settings** (gear) icon in the top right. Paste your Google Colab ngrok URL in the configuration modal to enable the real-time voice synthesis feature.

## Directory Structure

* `/corpus` - Contains the raw, processed, and chunked text files.
* `/chroma_db` - The local vector database storing document embeddings.
* `/scripts` - Contains the core backend logic.
  * `web_app.py` - The main Flask server handling API routes and streaming.
  * `pipeline.py` - Orchestrates the ingestion, chunking, and embedding of documents.
  * `retriever.py` - Manages the vector store and BM25 ensemble retrieval.
  * `chunker.py` - Handles document parsing and text splitting.
  * `/memory` - Stores session-specific JSON files and the global cross-conversation memory file.
  * `/static` - Frontend JavaScript (`app.js`) and CSS (`styles.css`).
  * `/templates` - Frontend HTML (`index.html`).

## Architecture Notes

To preserve API quotas, the system relies on local HuggingFace embeddings rather than cloud-based embedding APIs. Furthermore, the long-term memory summary generation is handled within the same LLM inference call as the standard response, avoiding the need for secondary background API requests.
