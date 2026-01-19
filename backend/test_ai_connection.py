import requests
import json
import time

questions = [
    "Hello", 
]

url = "http://127.0.0.1:5000/query"
headers = {'Content-Type': 'application/json'}

print("🤖 Testing AI Chat with Safe Prompt...\n")

for q in questions:
    print(f"❓ Q: {q}")
    try:
        payload = {"question": q}
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"🤖 A: {data.get('answer')}")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    
    print("-" * 40)
    time.sleep(1)
