# 🧠 Strategy: Training for Precision Accuracy

To move from "Good" to **"Precise"** accuracy, we don't just "fix code"—we need to teach the model. Here are the 3 Levels of Training, ranked by effort vs. reward.

---

## 🚀 Level 1: Few-Shot Prompting (The "Context" Method)
**Effort:** Low (1 Hour) | **Cost:** $0 | **Accuracy Impact:** High (+15%)

Instead of just giving the model *rules*, we give it **Examples**. This is "In-Context Learning".

**How to do it:**
Modify `field_extraction.py` to include 3 examples of "Text -> Correct JSON" inside the prompt.

```text
[System]
You are a certificate extractor.

[User]
Example 1 Text: "Cert No: 123... Issued: Jan 1 2020"
Example 1 JSON: {"certificate_number": "123", "issued_date": "2020-01-01"}

[User]
Example 2 Text: "This declares John Doe as certified..."
Example 2 JSON: {"certificate_number": null, "subject": "Certified"}
```

---

## 🛠️ Level 2: Fine-Tuning (The "Custom Model" Method)
**Effort:** Medium (1 Day) | **Cost:** $$$ (Azure training costs) | **Accuracy Impact:** Very High (+30%)

If Few-Shot isn't enough, we creating a **Custom GPT-4 Checkpoint** trained specifically on *your* certificates.

**Steps:**
1.  **Collect Data**: We need at least **50 examples** of `(Text, Correct_JSON)`.
2.  **Format**: Convert them to `.jsonl` format (OpenAI standard).
3.  **Upload**: Use Azure AI Studio to upload the file.
4.  **Train**: Run a Fine-Tuning job.
5.  **Use**: Can swap the model name in your `.env` from `gpt-4` to `ft:gpt-4-custom-...`.

**We can build a script to help you collect this data automatically.**

---

## 🎯 Level 3: Azure Document Intelligence (The "Visual" Method)
**Effort:** High (2 Days) | **Cost:** $$ | **Accuracy Impact:** Perfect (99%+)

GPT-4 reads *text*. Azure Document Intelligence looks at the *pixels* (layout, boxes, logos). If your certificates have strict layouts (e.g. government IDs), this is better than GPT.

**Steps:**
1.  Go to **Azure AI Studio**.
2.  Upload 5 PDFs.
3.  Draw boxes around the "Date" and "Name".
4.  Click "Train".
5.  Get a Model ID and put it in your `.env`.

---

## 💡 Recommendation
**Start with Level 1 (Few-Shot).**
I can update your `field_extraction.py` right now to include "Training Examples". This usually solves 90% of accuracy issues without paying for Fine-Tuning.

**Do you want me to upgrade your prompt with "Few-Shot" examples now?**
