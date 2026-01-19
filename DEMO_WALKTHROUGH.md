# 🎓 Demo Walkthrough Script

Good luck with your demo! Here is a recommended flow to show off all the features we built.

## 1. 🏗️ Architecture (The "Hook")
*   **Show VS Code**: Open the file explorer.
*   **Point out**: "We have separated the project into a clean **Frontend** and **Backend** structure."
    *   Show `backend/` (Python logic).
    *   Show `frontend/` (UI/Templates).
*   **Mention**: "This uses Flask for the server and simulates a microservices-ready architecture."

## 2. 🚀 The Dashboard (The "Wow")
*   **Open Browser**: `http://127.0.0.1:5000`
*   **Highlight**: "Note the modern Dark Mode and Glassmorphism design. It's built to look professional and premium."

## 3. 👁️ Feature 1: Vision OCR (Image Support)
*   **Action**: Drag & Drop **`Cert8.png`** (AWS Certificate).
*   **Explain**: "This is a raw PNG image. Most systems fail here. Our system uses **GPT-4 Vision** to 'read' the image like a human."
*   **Result**: Show the Green Checkmark.

## 4. 🌍 Feature 2: External Validation (Task 7)
*   **Point to Result**: Look at the "Issuer Check" badge.
*   **Explain**: "Notice it says **'Verified via External API'**. The system detected 'AWS', checked a simulated External Registry, and validated it remotely. It didn't just rely on a static local list."

## 5. ❌ Feature 3: Expiry Detection
*   **Action**: Drag & Drop **`Cert9.png`** (The old 2018 Cert).
*   **Result**: Show the **Red 'EXPIRED'** badge.
*   **Explain**: "The system parsed the text, found the date '2018', and correctly flagged it as invalid."

## 6. 🧠 Feature 4: RAG Chat (Optional)
*   **Action**: Type in the chat box: *"Is the AWS certificate valid?"*
*   **Result**: The AI should reply based on the document you just processed.

---
**🎉 Conclusion**: "This system combines Computer Vision, Logic-based Validation, and External Verification into one seamless pipeline."
