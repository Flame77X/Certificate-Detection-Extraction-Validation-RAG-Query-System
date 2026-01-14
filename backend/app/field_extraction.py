from datetime import datetime
import json
import os
from openai import AzureOpenAI

# Load env vars (already loaded by main.py)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

from collections import Counter

def _extract_single(text_content):
    """
    (Private) Single attempt to extract certificate fields using Azure OpenAI.
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
            # print(f"🧠 Sending text to Azure OpenAI ({AZURE_OPENAI_DEPLOYMENT})...") 
            # (Silenced print to avoid spamming console during ensemble)
            
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
                temperature=0.7, # Increased slightly for variety in ensemble
                timeout=30 
            )

            content = response.choices[0].message.content.strip()
            
            # Clean up markdown if present
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            if content.startswith("```"):
                content = content.replace("```", "")
            
            data = json.loads(content)
            
            # Map to our internal structure
            mapped_result = {}
            for key, val in data.items():
                mapped_result[key] = {
                    'value': val,
                    'confidence': 0.95 if val else 0.0 
                }
                
            return mapped_result

        except Exception as e:
            # print(f"❌ Azure OpenAI Error: [Securely Logged]")
            return None
    else:
        # MOCK DATA
        # print("⚠️ Using Mock Data")
        mock_response = {
            'issuer': {'value': 'ISO Authority', 'confidence': 0.96},
            'certificate_number': {'value': 'ISO-9001-2024-098', 'confidence': 0.93},
            'issued_date': {'value': '15/01/2024', 'confidence': 0.98},
            'expiry_date': {'value': '15-01-2026', 'confidence': 0.97},
            'subject': {'value': 'Quality Management System', 'confidence': 0.90}
        }
        return mock_response

def calculate_consensus(results_list):
    """
    Find the majority vote for each field across multiple results.
    Returns (consensus_dict, full_voting_log)
    """
    if not results_list:
        return {}, {}
        
    consensus_result = {}
    voting_log = {}
    
    # Get all keys from the first result
    keys = results_list[0].keys()
    
    for key in keys:
        # Collect all values for this field from all runs
        values = []
        for res in results_list:
            if res and key in res:
                # We vote on the 'value' part of the dict
                val = res[key].get('value')
                # Convert list/dict to string for hashing if needed, or keep simple
                values.append(val)
        
        # Count votes
        # We need to handle 'None' carefully
        safe_values = [str(v) if v is not None else "None" for v in values]
        counter = Counter(safe_values)
        
        # Get the winner (most common)
        most_common = counter.most_common(1)
        winner_val_str = most_common[0][0]
        vote_count = most_common[0][1]
        
        # Recover the original type (if it was None)
        final_val = None if winner_val_str == "None" else winner_val_str
        
        # If we have original values, try to find the one that matches winner string to preserve type
        # (Simple approximation for now)
        
        # Construct the detailed field object
        # We use the confidence of the first occurrence of the winner
        winner_conf = 0.0
        for res in results_list:
            if res and key in res:
                if str(res[key].get('value')) == safe_values[0] or (res[key].get('value') is None and safe_values[0] == "None"):
                   winner_conf = res[key].get('confidence', 0.0)
                   break
                   
        consensus_result[key] = {
            'value': final_val,
            'confidence': winner_conf
        }
        
        # Log details
        voting_log[key] = {
            'winner': final_val,
            'votes': dict(counter),
            'total_runs': len(results_list)
        }
        
    return consensus_result, voting_log

def extract_with_azure(text_content):
    """
    MAIN ENTRY: Performs Self-Consistency (Ensembling).
    Calls the API 3 times and returns the consensus result.
    """
    print(f"🧠 Consensus Engine: Running 3 parallel extraction attempts...")
    
    results = []
    attempts = 3
    
    for i in range(attempts):
        print(f"   🔹 Attempt {i+1}/{attempts}...", end="\r")
        res = _extract_single(text_content)
        if res:
            results.append(res)
            
    print(f"\n   ✅ Completed {len(results)} successful extractions.")
    
    if not results:
        return {} # Failed all
        
    # Calculate Majority Vote
    final_output, voting_details = calculate_consensus(results)
    
    # Inject voting details into the output so logging can find it
    final_output['_voting_debug'] = voting_details
    
    return final_output

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
