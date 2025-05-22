from datetime import datetime
from app import db


class HajjCardRequest(db.Model):
    __tablename__ = 'hajj_card_request_log'
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    employee_number = db.Column(db.String(10), nullable=False)
    hajj_name = db.Column(db.String(100), nullable=False)
    passport_number = db.Column(db.String(20), nullable=False)
    visa_number = db.Column(db.String(20), nullable=False)
    request_reason = db.Column(db.String(20), nullable=False)
    card_returned = db.Column(db.Boolean)
    status = db.Column(db.String(20), default="new_request")
    request_upload = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HajjCardRequest {self.id} - {self.hajj_name}>"
