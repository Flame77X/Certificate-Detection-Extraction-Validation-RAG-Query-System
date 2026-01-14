# 🏗️ Project Architecture (For Jacob)

Welcome! The project has been restructured into a clean **Frontend vs Backend** separation.

## 📂 File Structure

### 1️⃣ `frontend/`
*   **What's inside?**: All the visual stuff.
*   `templates/index.html`: The main web page (HTML).
*   `static/style.css`: The styling (Colors, Glassmorphism, Layout).
*   **Purpose**: This is what the user *sees*.

### 2️⃣ `backend/`
*   **What's inside?**: The brain of the operation (Python).
*   `app.py`: The Main Server (Flask). It serves the frontend and handles API calls.
*   `app/`: Core Data Processing Logic.
    *   `ocr_module.py`: GPT-4 Vision OCR.
    *   `certificate_identification.py`: Smart classification logic.
    *   `external_verification.py`: Task 7 (API Verify) logic.
*   `data/`: Uploaded files and Vector Database.

## 🚀 How to Run
1.  Open Terminal in the root folder.
2.  Run the backend server:
    ```bash
    python backend/app.py
    ```
3.  Open Browser: `http://127.0.0.1:5000`

## 🔄 Interaction Flow
1.  User drags file on **Frontend**.
2.  **Frontend** sends file to **Backend** (`/upload` API).
3.  **Backend** processes it (OCR -> ID -> Verify).
4.  **Backend** returns JSON results.
5.  **Frontend** updates the Dashboard.
