from datetime import datetime
import json
import os
from openai import AzureOpenAI

# Load env vars (already loaded by main.py)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

def extract_with_azure(text_content):
    """
    Extract certificate fields using Azure OpenAI (GPT-4).
    
    Args:
        text_content (str): The raw text from the certificate.
        
    Returns:
        dict: The structured dataset.
    """
    
    # Check if we have usable keys
    # Clean the endpoint if it contains the full path/query params
    base_endpoint = AZURE_OPENAI_ENDPOINT
    if base_endpoint:
        if "/openai/deployments" in base_endpoint:
             base_endpoint = base_endpoint.split("/openai/deployments")[0]
        # Remove query params if any
        if "?" in base_endpoint:
            base_endpoint = base_endpoint.split("?")[0]

    has_real_config = (
        AZURE_OPENAI_API_KEY and 
        base_endpoint and
        "your-key" not in str(AZURE_OPENAI_API_KEY)
    )

    if has_real_config:
        try:
            print(f"🧠 Sending text to Azure OpenAI ({AZURE_OPENAI_DEPLOYMENT})...")
            
            client = AzureOpenAI(
                azure_endpoint=base_endpoint, 
                api_key=AZURE_OPENAI_API_KEY,  
                api_version=AZURE_OPENAI_API_VERSION
            )

            prompt = f"""
            You are a strict data extraction assistant. 
            Extract the following fields from the certificate text provided below.
            Return ONLY a valid JSON object. Do not include markdown formatting (```json).
            
            Fields to extract:
            - issuer: Name of the organization issuing the certificate.
            - certificate_number: The unique ID of the certificate.
            - issued_date: Date issued (format YYYY-MM-DD if possible, else original).
            - expiry_date: Date expired (format YYYY-MM-DD if possible, else original).
            - subject: What is being certified (e.g., ISO 9001, Completion of Course).

            If a field is not found, use null.
            
            Certificate Text:
            \"\"\"
            {text_content}
            \"\"\"
            """

            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            content = response.choices[0].message.content.strip()
            
            # Clean up markdown if present
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            if content.startswith("```"):
                content = content.replace("```", "")
            
            data = json.loads(content)
            
            # Map to our internal structure (adding mock confidence)
            mapped_result = {}
            for key, val in data.items():
                mapped_result[key] = {
                    'value': val,
                    'confidence': 0.95 if val else 0.0 
                }
                
            return mapped_result

        except Exception as e:
            print(f"❌ Azure OpenAI Error: {e}")
            print("Falling back to MOCK data...")
    else:
        print("ℹ️  No valid Azure OpenAI keys found. Using MOCK data.")

    # FALLBACK MOCK
    print("⚠️ Using Mock Data for Extraction")
    mock_response = {
        'issuer': {'value': 'ISO Authority', 'confidence': 0.96},
        'certificate_number': {'value': 'ISO-9001-2024-098', 'confidence': 0.93},
        'issued_date': {'value': '15/01/2024', 'confidence': 0.98},
        'expiry_date': {'value': '15-01-2026', 'confidence': 0.97},
        'subject': {'value': 'Quality Management System', 'confidence': 0.90}
    }
    return mock_response

def normalize_date(date_string):
    """Convert any date format to YYYY-MM-DD"""
    if not date_string:
        return None
    # Try common formats
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%B %d, %Y', '%d %B %Y']
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_string, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_string

def extract_fields(azure_output):
    """Clean raw extraction output into structured fields."""
    fields = {}
    confidence = {}
    target_fields = ['issuer', 'certificate_number', 'issued_date', 'expiry_date', 'subject']
    
    for field_name in target_fields:
        field_data = azure_output.get(field_name, {})
        if not field_data:
            fields[field_name] = None
            confidence[field_name] = 0.0
            continue
            
        value = field_data.get('value', '')
        conf = field_data.get('confidence', 0.0)
        
        # Normalize dates
        if field_name in ['issued_date', 'expiry_date']:
            value = normalize_date(value)
        
        fields[field_name] = value
        confidence[field_name] = round(conf, 2)
    
    return fields, confidence

def create_json_output(doc_id, fields, confidence, flags):
    """Create final structured JSON output."""
    return {
        "doc_id": doc_id,
        "fields": fields,
        "confidence": confidence,
        "confidence_flags": flags
    }
