from datetime import datetime
from app import db


class AppSettings(db.Model):
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255))


class CardRequest(db.Model):
    __tablename__ = 'card_requests'
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    employee_number = db.Column(db.String(10), nullable=False)
    hajj_name = db.Column(db.String(100), nullable=False)
    passport_number = db.Column(db.String(20), nullable=False)
    visa_number = db.Column(db.String(20), nullable=False)
    request_reason = db.Column(db.String(20), nullable=False)
    card_returned = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="found")  # Default changed to match constraint
    request_upload = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CardRequest {self.id} - {self.hajj_name}>"

    def format_date(self, date):
        """Format date safely, handling None values"""
        return date.strftime('%Y-%m-%d %H:%M') if date else ''
