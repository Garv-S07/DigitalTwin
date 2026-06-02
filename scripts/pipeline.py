from chunker import Chunker
from retriever import Retriever

from langchain_community.document_loaders import PyPDFLoader
import os
import shutil

script_dir = os.path.dirname(os.path.abspath(__file__))

research_path = os.path.join(script_dir, '../corpus/raw/research/')
books_path = os.path.join(script_dir, '../corpus/raw/books/')
output_path = os.path.join(script_dir, '../corpus/processed/')

class Pipeline:
    def __init__(self, txt_path, pdf_path, output_path, ensemble_retriever, query):
        self.txt_path = txt_path
        self.pdf_path = pdf_path
        self.output_path = output_path
        shutil.rmtree(self.output_path, ignore_errors=True)
        os.makedirs(self.output_path, exist_ok=True)
        self.ensemble_retriever = ensemble_retriever
        self.query = query

    def retrieve_docs(self):
        return self.ensemble_retriever.invoke(self.query)

    def parse_pdf(self, max_files=None):
        count = 0
        for filename in os.listdir(self.pdf_path):
            if max_files and count >= max_files:
                break
            if filename.endswith(".pdf"):
                curr_pdf_path = os.path.join(self.pdf_path, filename)
                try:
                    loader = PyPDFLoader(curr_pdf_path)
                    pages = loader.load()

                    extracted_text = ""
                    for page in pages:
                        extracted_text += page.page_content + "\n"

                    txt_filename = filename.replace(".pdf", ".txt")
                    txt_path = os.path.join(self.output_path, txt_filename)

                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(extracted_text)
                    count += 1
                except Exception as e:
                    print(f"Error loading {curr_pdf_path}: {e}")
            else:
                print(f"Non PDF file, skipping: {filename}")

    def parse_txt(self, max_files=None):
        count = 0
        for filename in os.listdir(self.txt_path):
            if max_files and count >= max_files:
                break
            if filename.endswith(".txt"):
                try:
                    source_path = os.path.join(self.txt_path, filename)
                    dest_path = os.path.join(self.output_path, filename)
                
                    if os.path.isfile(source_path):
                        shutil.copy2(source_path, dest_path)
                        print(f"Copied: {filename}")
                        count += 1
                    else:
                        print(f"Error processing file: {filename}")
                except Exception as e:
                    print(f"Error processing file: {filename}")
            else:
                print(f"Non txt file, skipping: {filename}")


query = "What happens when we fall into a black hole?"

pipeline = Pipeline(books_path, research_path, output_path, None, query)
pipeline.parse_pdf()
pipeline.parse_txt()

retriever_builder = Retriever(output_path)
ensemble_retriever = retriever_builder.build_retriever()
pipeline.ensemble_retriever = ensemble_retriever

retrieved_docs = pipeline.retrieve_docs()

for doc in retrieved_docs:
    print(doc.metadata)
    print(doc.page_content)


