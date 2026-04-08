from google import genai
from google.genai import types

API_KEY = "AIzaSyA6En5i8Bpr6_lPKWSMecchwRfHruHw0tU"
client = genai.Client(api_key=API_KEY)

try:
    print("Making request...")
    resp = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents="Say hello!"
    )
    print("Response:", resp.text)
except Exception as e:
    print(f"ERROR: {type(e)} - {e}")
