import os
from flask import Flask
from supabase import create_client
from werkzeug.middleware.proxy_fix import ProxyFix

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "hajj_card_service_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with app.app_context():
    import models  # Ensure models are loaded


