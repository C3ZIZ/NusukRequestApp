import logging
import re
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session

from app import app, db
from models import HajjCardRequest

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Flash message translations
MESSAGES = {
    'ar': {
        'employee_number_invalid': 'يجب أن يكون رقم الموظف 10 أرقام ويبدأ بـ "05"',
        'all_fields_required': 'جميع الحقول مطلوبة',
        'duplicate_request': 'يوجد طلب نشط بالفعل لرقم جواز السفر {passport}',
        'request_submitted': 'تم تقديم الطلب بنجاح!',
        'request_error': 'حدث خطأ أثناء تقديم طلبك.'
    }
}

def get_language():
    return 'ar'

@app.route('/')
def index():
    """Landing page with links to employee and admin portals"""
    language = get_language()
    return render_template('index.html', language=language)

@app.route('/employee')
def employee():
    """Employee page to view and submit requests"""
    language = get_language()
    requests = HajjCardRequest.query.order_by(HajjCardRequest.created_at.desc()).all()
    return render_template('employee.html', requests=requests, language=language)

@app.route('/admin')
def admin():
    """Admin page to manage requests"""
    language = get_language()
    requests = HajjCardRequest.query.order_by(HajjCardRequest.created_at.desc()).all()
    return render_template('admin.html', requests=requests, language=language)

@app.route('/submit_request', methods=['POST'])
def submit_request():
    """Handle new request submissions"""
    try:
        employee_name = request.form.get('employee_name')
        employee_number = request.form.get('employee_number')
        hajj_name = request.form.get('hajj_name')
        passport_number = request.form.get('passport_number')
        visa_number = request.form.get('visa_number')
        request_reason = request.form.get('request_reason')
        card_returned = False

        # Get current language
        language = get_language()
        
        # Validate employee number format
        if not employee_number or not re.match(r'^05\d{8}$', employee_number):
            flash(MESSAGES[language]['employee_number_invalid'], 'error')
            return redirect(url_for('employee'))

        # Check required fields
        if not all([employee_name, employee_number, hajj_name, passport_number, visa_number, request_reason]):
            flash(MESSAGES[language]['all_fields_required'], 'error')
            return redirect(url_for('employee'))
            
        # Check for card returned if request reason is "Damaged Card"
        if request_reason == "Damaged Card":
            card_returned = 'card_returned' in request.form

        # Check for duplicate active requests
        existing_request = HajjCardRequest.query.filter_by(
            passport_number=passport_number, 
            status="New"
        ).first()
        
        if existing_request:
            flash(MESSAGES[language]['duplicate_request'].format(passport=passport_number), 'error')
            return redirect(url_for('employee'))
        
        # Create and save new request
        new_request = HajjCardRequest()
        new_request.employee_name = employee_name
        new_request.employee_number = employee_number
        new_request.hajj_name = hajj_name
        new_request.passport_number = passport_number
        new_request.visa_number = visa_number
        new_request.request_reason = request_reason
        new_request.card_returned = card_returned
        new_request.created_at = datetime.utcnow()
        
        db.session.add(new_request)
        db.session.commit()
        
        flash(MESSAGES[language]['request_submitted'], 'success')
        return redirect(url_for('employee'))
    
    except Exception as e:
        logger.error(f"Error submitting request: {str(e)}")
        db.session.rollback()
        # Define language in case it's not defined in the exception path
        language = get_language()
        flash(MESSAGES[language]['request_error'], 'error')
        return redirect(url_for('employee'))

@app.route('/update_status/<int:request_id>', methods=['POST'])
def update_status(request_id):
    """Update the status of a request (Processed/New)"""
    try:
        language = get_language()
        hajj_request = HajjCardRequest.query.get_or_404(request_id)
        new_status = request.form.get('status')
        
        if new_status in ["Processed", "New"]:
            hajj_request.status = new_status
            hajj_request.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"success": True, "status": new_status})
        else:
            return jsonify({"success": False, "error": "Invalid status value"}), 400
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/update_written/<int:request_id>', methods=['POST'])
def update_written(request_id):
    """Update the is_written flag of a request"""
    try:
        language = get_language()
        hajj_request = HajjCardRequest.query.get_or_404(request_id)
        is_written = request.form.get('is_written', 'false')
        
        # Convert string to boolean
        hajj_request.is_written = (is_written.lower() == 'true')
        hajj_request.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": True, "is_written": hajj_request.is_written})
    except Exception as e:
        logger.error(f"Error updating written status: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
