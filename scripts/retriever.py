from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from chunker import Chunker
from langchain_huggingface import HuggingFaceEmbeddings
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '../chroma_db'))

embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

vector_store = Chroma(
    collection_name="neil_knowledge",
    embedding_function=embedding_model,
    persist_directory=DB_DIR
)

class Retriever:
    def __init__(self, data_directory):
        self.data_directory = data_directory

    def build_retriever(self):
        chunker = Chunker()
        all_langchain_documents = []

        for filename in os.listdir(self.data_directory):
            if filename.endswith(".txt"):
                file_path = os.path.join(self.data_directory, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                    
                docs = chunker.build_documents(text_content, source_name=filename, source_type="txt")
                all_langchain_documents.extend(docs)

        if not all_langchain_documents:
            raise ValueError(f"No text files found in {self.data_directory}. Pipeline cannot start.")

        collection_count = 0
        try:
            collection_count = vector_store._collection.count()
        except Exception:
            pass

        if collection_count == 0:
            print("Vector store is empty. Ingesting and embedding documents...")
            import time
            batch_size = 50
            
            for i in range(0, len(all_langchain_documents), batch_size):
                batch = all_langchain_documents[i : i + batch_size]
                batch_start = time.time()
                
                # No rate limiting needed! Local embeddings process instantly!
                vector_store.add_documents(batch)
                            
                elapsed = time.time() - batch_start
                print(f"Embedded docs {min(i+batch_size, len(all_langchain_documents))}/{len(all_langchain_documents)} (batch took {elapsed:.2f}s)")
        else:
            print(f"Vector store already populated with {collection_count} documents. Skipping embedding ingestion.")
        bm25_retriever = BM25Retriever.from_documents(all_langchain_documents)
        bm25_retriever.k = 5

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_store.as_retriever(search_kwargs={"k": 5})],
            weights=[0.5, 0.5]
        )

        return ensemble_retriever
