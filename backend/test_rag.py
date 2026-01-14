from app.rag_pipeline import CertificateRAG
import os

def test_rag():
    print("🧪 Initializing RAG Pipeline...")
    rag = CertificateRAG()
    
    # 1. Ingest specific sample data
    print("📥 Ingesting Sample Certificate...")
    sample_cert = {
        "doc_id": "TEST_CERT_001",
        "final_status": "Verified",
        "fields": {
            "issuer": "PramAnA AyurTech Solutions Pvt Ltd",
            "subject": "Internship Completion",
            "issued_date": "2025-12-01",
            "expiry_date": None,
            "certificate_number": "PRA-2025-001"
        }
    }
    rag.ingest_certificate(sample_cert)
    print("✅ Ingestion Complete.")
    
    # 2. Query
    question = "Is the certificate for PramAnA AyurTech valid?"
    print(f"\n❓ Asking Question: '{question}'")
    
    answer = rag.answer_question(question)
    print(f"\n🤖 RAG Answer:\n{answer}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_rag()
