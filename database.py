from flask import request, jsonify, session
import sqlite3
import secrets
import random
from werkzeug.security import generate_password_hash
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# In-memory store for OTPs (For production, consider putting this in Redis or SQLite)
OTP_STORE = {}
SENDGRID_API_KEY = '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'

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def init_routes(app):
    app.secret_key = "super_secret_alpha_lens_key"

    # ==========================================
    # NEW SENDGRID OTP ROUTES
    # ==========================================
    @app.route('/api/send-otp', methods=['POST'])
    def send_otp():
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Generate a 6-digit OTP
        otp = str(random.randint(100000, 999999))
        OTP_STORE[email] = otp

        # Construct the SendGrid Email
        message = Mail(
            from_email='yeshwanthkumar.899@gmail.com',  # <--- CHANGE THIS TO YOUR VERIFIED SENDGRID EMAIL
            to_emails=email,
            subject='Alpha Lens - Your Authentication Code',
            html_content=f'''
                <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                    <h2>Welcome to Alpha Lens</h2>
                    <p>Your secure, one-time login code is:</p>
                    <h1 style="color: #06b6d4; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                    <p>This code will expire in 10 minutes. If you did not request this, please ignore this email.</p>
                </div>
            '''
        )

        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            sg.send(message)
            return jsonify({"message": "OTP sent successfully!"}), 200
        except Exception as e:
            print(f"SendGrid Error: {e}")
            return jsonify({"error": "Failed to send email via SendGrid. Check your Verified Sender Identity."}), 500

    @app.route('/api/verify-otp', methods=['POST'])
    def verify_otp():
        data = request.json
        email = data.get('email')
        user_otp = data.get('otp')

        # Verify the OTP matches our temporary store
        if not email or email not in OTP_STORE or OTP_STORE[email] != user_otp:
            return jsonify({"error": "Invalid or expired OTP."}), 401

        # OTP is correct! Clean it up so it can't be reused.
        del OTP_STORE[email]

        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            
            # If user doesn't exist yet, seamlessly create their account (Passwordless creation)
            if not user:
                dummy_password = generate_password_hash(secrets.token_hex(16))
                c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, dummy_password))
                conn.commit()
            
            conn.close()
            
            session['user'] = email
            return jsonify({"message": "Authentication successful", "user": email}), 200
        except Exception as e:
            return jsonify({"error": "Database error occurred."}), 500

    # ==========================================
    # EXISTING GOOGLE & SESSION ROUTES
    # ==========================================
    @app.route('/api/oauth-signin', methods=['POST'])
    def oauth_signin():
        data = request.json
        account_id = data.get('account_id') 

        if not account_id:
            return jsonify({"error": "Account ID required"}), 400

        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE email = ?", (account_id,))
            user = c.fetchone()
            
            if not user:
                dummy_password = generate_password_hash(secrets.token_hex(16))
                c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (account_id, dummy_password))
                conn.commit()
            
            conn.close()
            
            session['user'] = account_id
            return jsonify({"message": "Authentication successful", "user": account_id}), 200
        except Exception as e:
            return jsonify({"error": "Database error occurred."}), 500

    @app.route('/api/me', methods=['GET'])
    def get_current_user():
        if 'user' in session:
            return jsonify({"user": session['user']}), 200
        return jsonify({"user": None}), 200

    @app.route('/api/logout', methods=['POST'])
    def logout():
        session.pop('user', None)
        return jsonify({"message": "Logged out"}), 200