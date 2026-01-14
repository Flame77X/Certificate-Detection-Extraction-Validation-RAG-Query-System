# 🎯 Implementing Custom Document Intelligence
**Goal:** Train a custom model in Azure Studio to recognize *your specific* certificate layouts (e.g. "Certificate Number" is always top-right).

---

## 🏗️ Step 1: Train the Model (In Browser)
You cannot do this step in VS Code. You must use the Azure Portal.

1.  **Go to:** [Azure Document Intelligence Studio](https://documentintelligence.ai.azure.com/studio)
2.  **Select:** `Custom extraction model`
3.  **Create Project:** Name it "MyCertificateModel"
4.  **Upload Data:** Upload 5-10 sample PDFs of your certifictes.
5.  **Label:** Draw boxes around the text you want:
    *   Label "John Doe" as `Recipient_Name`
    *   Label "ISO-9001" as `Certificate_ID`
    *   Label "Jan 1, 2024" as `Issue_Date`
6.  **Train:** Click the "Train" button. Choose **"Neural"** (slower but smarter) or "Template" (faster).
7.  **Get Model ID:** Once trained, copy the **Model ID** (e.g. `Cert_Model_v1`).

---

## 💻 Step 2: Connect Code (VS Code)

We need to update `app/ocr_module.py` and `.env` to use this new Model ID.

### 1. Update `.env`
```ini
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-resource.cognitiveservices.azure.com/"
AZURE_DOCUMENT_INTELLIGENCE_KEY="your-key-here"
AZURE_CUSTOM_MODEL_ID="Cert_Model_v1"  # <--- YOUR NEW MODEL ID
```

### 2. Update `app/ocr_module.py`
We will replace the generic "Read" call with an "Analyze" call using your model.

```python
# CODE SNIPPET FOR ocr_module.py

def analyze_custom_model(file_path):
    model_id = os.getenv("AZURE_CUSTOM_MODEL_ID")
    client = DocumentIntelligenceClient(...)
    
    with open(file_path, "rb") as f:
        # Use our custom trained model!
        poller = client.begin_analyze_document(model_id, document=f)
        
    result = poller.result()
    
    # The result is STRUCTERED now!
    # e.g. result.documents[0].fields['Recipient_Name'].content
    return result
```

---

## 🚀 Why this is better?
*   **Precision:** It knows exactly where to look. It won't accidentally read the "Issued By" signature as the "Recipient Name".
*   **Accuracy:** 99% accuracy for fixed layouts.

**Shall I update `ocr_module.py` to support this "Custom Model" mode?**
