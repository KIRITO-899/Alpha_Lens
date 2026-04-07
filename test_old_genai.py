import google.generativeai as genai
import time

API_KEY = "AIzaSyA6En5i8Bpr6_lPKWSMecchwRfHruHw0tU"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

try:
    print("Making request with OLD SDK...")
    resp = model.generate_content("Say hello!", generation_config={"response_mime_type": "application/json"})
    print("Response:", resp.text)
except Exception as e:
    print(f"ERROR: {type(e)} - {e}")
