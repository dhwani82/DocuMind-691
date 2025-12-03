"""Test script to verify the generate-docs endpoint works."""
import requests
import json

# Simple test code
test_code = """
def hello(name):
    return f"Hello, {name}!"

class Greeter:
    def __init__(self, greeting):
        self.greeting = greeting
    
    def greet(self, name):
        return f"{self.greeting}, {name}!"
"""

try:
    response = requests.post(
        'http://localhost:5001/api/generate-docs',
        json={'code': test_code},
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    
    if response.headers.get('content-type', '').startswith('application/json'):
        data = response.json()
        print("Success! Response:")
        print(json.dumps(data, indent=2)[:500])  # First 500 chars
    else:
        print("Error: Server returned non-JSON response")
        print("Response (first 500 chars):")
        print(response.text[:500])
        
except requests.exceptions.ConnectionError:
    print("Error: Could not connect to server. Is it running?")
except Exception as e:
    print(f"Error: {e}")

