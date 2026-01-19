import chromadb
from openai import AzureOpenAI
import os
import json
from datetime import datetime

class CertificateRAG:
    def __init__(self):
        """Initialize RAG pipeline with Chroma vector DB"""
        
        # Initialize Chroma (Persistent Storage)
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="certificates",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize Azure OpenAI - check for sanitized keys
        raw_key = os.getenv('AZURE_OPENAI_API_KEY')
        if not raw_key or "your-key" in str(raw_key):
             print("⚠️  RAG Warning: Valid Azure API Key not found. RAG will not function correctly.")
             self.client = None
        else:
            self.client = AzureOpenAI(
                api_key=raw_key,
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', "2024-02-15-preview"),
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
            )
            
        self.deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4') 
        # Ideally use text-embedding-3-small, but checking availability. 
        # Fallback to simple deterministic embeddings if no model.
    
    def get_embeddings(self, text):
        """Generate embeddings using Azure OpenAI"""
        if not self.client:
             # Fallback: simple hash vector for demo without keys
             return [0.1] * 1536
             
        try:
            # Note: You need an embedding deployment. 
            # If not available, we can't use vector search effectively.
            # Assuming 'text-embedding-3-small' or similar is deployed.
            # If not, let's try to use the chat model as a hack or just fail gracefully.
            # For now, we assume a deployment named 'text-embedding-ada-002' or similar exists
            # often typically deployed as same name.
            
            # Using a common default or Env variable would be best.
            embedding_model = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
            
            response = self.client.embeddings.create(
                input=text,
                model=embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"⚠️ Embedding error: {e}")
            print("   (Ensure you have an embedding model deployed and AZURE_EMBEDDING_DEPLOYMENT set)")
            return [0.0] * 1536
    
    def ingest_certificate(self, cert_data):
        """
        Add extracted certificate to vector database.
        Idempotent: Overwrites if ID exists.
        """
        doc_id = cert_data.get('doc_id', 'unknown')
        
        # Create searchable text representation
        fields = cert_data.get('fields', {})
        searchable_text = f"""
        Certificate ID: {doc_id}
        Issuer: {fields.get('issuer', 'Unknown')}
        Subject: {fields.get('subject', 'Unknown')}
        Issued Date: {fields.get('issued_date', 'Unknown')}
        Expiry Date: {fields.get('expiry_date', 'Unknown')}
        Certificate Number: {fields.get('certificate_number', 'N/A')}
        Validation Status: {cert_data.get('final_status', 'Unknown')}
        """
        
        embedding = self.get_embeddings(searchable_text)
        
        # Metadata must be flat dict
        metadata = {
            "status": str(cert_data.get('final_status')),
            "issuer": str(fields.get('issuer')),
            "ingested_at": datetime.now().isoformat()
        }
        
        self.collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[searchable_text],
            metadatas=[metadata]
        )
        
        return {"success": True, "doc_id": doc_id}
    
    def query(self, question, n_results=3):
        """Query certificates using natural language"""
        q_embedding = self.get_embeddings(question)
        
        results = self.collection.query(
            query_embeddings=[q_embedding],
            n_results=n_results
        )
        
        return results
    
    def answer_question(self, question):
        """Generate answer to user question based on RAG context"""
        # 1. Retrieve
        results = self.query(question)
        
        if not results or not results['documents'] or not results['documents'][0]:
            return "No relevant certificates found in the database."
        
        # 2. Contextualize
        context_docs = results['documents'][0] # List of strings
        context_text = "\n---\n".join(context_docs)
        
        if not self.client:
            return "Answer generation disabled (No API Key). Context found: " + context_text[:100] + "..."

        # 3. Generate
        try:
            prompt = f"""
            You are a secure Certificate Verification Assistant.
            Answer the user question using ONLY the context provided below.
            If the answer is not in the context, say "I cannot find that information in the certificate records."
            
            Context:
            {context_text}
            
            User Question: {question}
            """
            
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating answer: {str(e)}"
