# Digital Twin: Neil deGrasse Tyson

This project is an interactive, voice-enabled AI assistant designed to act as a digital twin of Neil deGrasse Tyson. It uses Retrieval-Augmented Generation (RAG) to ground the assistant's knowledge in a provided corpus of books and texts, while employing a local vector database for fast, rate-limit-free document retrieval. 

The architecture is built on a Flask backend and a vanilla JavaScript frontend, utilizing Google's Gemini models for text generation and a remote endpoint for real-time Text-to-Speech (TTS) synthesis.

## Core Features

* **Retrieval-Augmented Generation (RAG):** Uses local HuggingFace embeddings (`all-MiniLM-L6-v2`) and a Chroma vector database to parse and retrieve relevant context from a local corpus of texts and books.
* **Real-time Streaming & TTS:** Streams the LLM response chunk-by-chunk to the frontend using Server-Sent Events (SSE). The text is simultaneously sent to a remote Colab endpoint for real-time speech synthesis, minimizing audio latency.
* **Short-Term & Long-Term Memory:**
  * **Short-Term (Session):** Maintains individual conversation histories in JSON format, allowing the model to recall context within a single session.
  * **Long-Term (Global):** The model automatically extracts new personal facts learned about the user during conversations and appends them to a global memory file. This file is injected into the context window, enabling true cross-conversation memory.
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

2. **Install Dependencies:**
   Install the required Python packages using pip or uv:
   ```bash
   pip install -r requirements.txt
   ```

3. **Prepare the Corpus:**
   Place your raw text documents (e.g., books, articles) into the `corpus/raw/books/` directory.

4. **Run the Data Pipeline:**
   Execute the pipeline script to chunk and embed your documents into the local Chroma database.
   ```bash
   python scripts/pipeline.py
   ```

5. **Start the Web Server:**
   Launch the Flask backend.
   ```bash
   python scripts/web_app.py
   ```
   The application will be accessible at `http://127.0.0.1:5000`.

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
