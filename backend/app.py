from flask import Flask, render_template, request, jsonify
import os
import shutil
from datetime import datetime
from batch_processor import process_single_file
# from app.rag_pipeline import CertificateRAG # Optional RAG import

# Configure Flask to look for frontend in sibling directory
app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

# RAG Integration (The "Memory")
# try:
#     rag = CertificateRAG()
#     print("🧠 RAG System Initialized")
# except Exception as e:
#     print(f"⚠️ RAG Init Failed: {e}")
#     rag = None

UPLOAD_FOLDER = os.path.join('data', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        try:
            filename = file.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # 1. Extraction & Validation (The "Brain")
            result = process_single_file(filepath)
            
            if not result:
                 return jsonify({'success': False, 'error': 'Document processing failed or not a certificate.'}), 400

            # 2. RAG Ingestion (The "Memory")
            # if rag:
            #     rag.ingest_certificate(result)
            
            return jsonify({'success': True, 'data': result})
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# @app.route('/query', methods=['POST'])
# def query_rag():
#     if not rag:
#         return jsonify({'answer': "RAG System is offline."})
#     data = request.json
#     answer = rag.answer_question(data.get('question'))
#     return jsonify({'answer': answer})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
