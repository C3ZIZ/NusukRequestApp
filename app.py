import os
from flask import Flask
from supabase import create_client
from werkzeug.middleware.proxy_fix import ProxyFix

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "hajj_card_service_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://dhbzeklvyarffuepofbw.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRoYnpla2x2eWFyZmZ1ZXBvZmJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTExMjIwNjYsImV4cCI6MjA2NjY5ODA2Nn0.TA3IZy5Nb7REGTon0XbZO7n-y_nUmWgDW4SFaSfNJ4k"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with app.app_context():
    import models  # Ensure models are loaded


