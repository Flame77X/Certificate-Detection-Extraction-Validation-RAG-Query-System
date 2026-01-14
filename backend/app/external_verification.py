import requests
import time

def verify_external_issuer(issuer_name, fields):
    """
    Task 7: External Verification Logic.
    
    1. Check if issuer has an API.
    2. If yes, call it (Simulated here).
    3. If no, return Manual Verification.
    """
    if not issuer_name:
        return {
            "status": "Manual Review Required",
            "reason": "Issuer name missing"
        }

    # Registry of Issuers with APIs
    # In a real app, this would be a database column 'verification_endpoint'
    API_REGISTRY = {
        "AWS": {
            "api_url": "https://aws.amazon.com/verification",
            "type": "public_web"
        },
        "Microsoft": {
            "api_url": "https://learn.microsoft.com/api/verify",
            "type": "rest_api"
        },
        "Coursera": {
            "api_url": "https://coursera.org/verify",
            "type": "public_web"
        }
    }

    # Normalize name
    normalized_issuer = None
    for known_issuer in API_REGISTRY:
        if known_issuer.lower() in issuer_name.lower():
            normalized_issuer = known_issuer
            break
    
    if normalized_issuer:
        # API Available - Step 7a: Call the third-party verification API
        print(f"🌍 External API found for {normalized_issuer}. Verifying...")
        
        # Simulation of API Call (Real call requires Captcha/Auth usually)
        # We check specific fields to simulate a "Hit"
        cert_num = fields.get('certificate_number')
        
        if cert_num and len(cert_num) > 5:
            # Simulate Success
            return {
                "status": "Verified (External API)",
                "reason": f"Validated against {normalized_issuer} Registry",
                "api_used": API_REGISTRY[normalized_issuer]['api_url']
            }
        else:
            return {
                "status": "Failed (External API)",
                "reason": "Certificate Number missing for API check"
            }

    else:
        # No API exists - Step 7b: Mark for Manual Verification
        return {
            "status": "Manual Verification Required",
            "reason": "No verification API available for this issuer"
        }
