from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

class Chunker:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " "]
        )

    def chunk(self, text):
        return self.splitter.split_text(text)

    def build_documents(self, text, source_name, source_type=None):
        chunks = self.chunk(text)
        documents = []
        
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": source_name,
                    "type": source_type,
                    "chunk_id": i
                }
            )
            documents.append(doc)
            
        return documents