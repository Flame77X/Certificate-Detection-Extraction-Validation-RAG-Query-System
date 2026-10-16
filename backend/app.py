from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from batch_processor import process_single_file
from app.rag_pipeline import CertificateRAG
from app.security import MAX_FILE_SIZE_MB

# Configure Flask to look for frontend in sibling directory
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

# Reject oversized uploads before they hit disk (Flask returns 413)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt'}

# RAG Integration (The "Memory")
try:
    rag = CertificateRAG()
    print("🧠 RAG System Initialized")
except Exception as e:
    print(f"⚠️ RAG Init Failed: {e}")
    rag = None

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    # Security: strip directory components / traversal from the client-supplied name
    filename = secure_filename(file.filename)
    if not filename or not allowed_file(filename):
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return jsonify({'success': False, 'error': f'Unsupported file type. Allowed: {allowed}'}), 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # 1. Extraction & Validation (The "Brain")
        result = process_single_file(filepath)

        if not result:
             return jsonify({'success': False, 'error': 'Document processing failed or not a certificate.'}), 400

        # 2. RAG Ingestion (The "Memory")
        if rag:
            rag.ingest_certificate(result)

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        # Log details server-side only; do not leak internals to the client
        print(f"❌ Upload processing error: {e}")
        return jsonify({'success': False, 'error': 'Internal error while processing the document.'}), 500

@app.errorhandler(413)
def file_too_large(_e):
    return jsonify({'success': False, 'error': f'File too large. Limit is {MAX_FILE_SIZE_MB}MB'}), 413

@app.route('/query', methods=['POST'])
def query_rag():
    if not rag:
        return jsonify({'answer': "RAG System is offline.", 'sources': []})
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'Field "question" is required.'}), 400
    # doc_id (optional): the document open in the UI, so 'this certificate' questions target it
    return jsonify(rag.answer_question(question, doc_id=(data.get('doc_id') or None)))

if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, port=int(os.getenv('PORT', '5000')))
