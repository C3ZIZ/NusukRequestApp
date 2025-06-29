import logging
import re
from datetime import datetime, timedelta, timezone
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from app import app, supabase

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

def get_total_hajj():
    """Get the total number of Hajj pilgrims from settings"""
    try:
        response = supabase.table('app_settings').select('value').eq('key', 'total_hajj').execute()
        if response.data and len(response.data) > 0 and 'value' in response.data[0]:
            return int(response.data[0]['value'])
        return 0
    except (ValueError, TypeError, KeyError, Exception) as e:
        logger.error(f"Error getting total hajj: {str(e)}")
        return 0

def parse_datetime_fields(requests):
    """Convert ISO datetime strings to datetime objects for created_at and updated_at fields."""
    for req in requests:
        for field in ["created_at", "updated_at"]:
            value = req.get(field)
            if isinstance(value, str):
                try:
                    req[field] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except Exception:
                    pass
        # Ensure status is always present for UI
        if not req.get('status'):
            req['status'] = 'New'
    return requests

@app.route('/')
def index():
    """Landing page with links to employee and admin portals"""
    language = get_language()
    return render_template('index.html', language=language)

@app.route('/employee')
def employee():
    """Employee page to view and submit requests"""
    try:
        requests = supabase.table('card_requests').select('*').order('created_at', desc=True).execute()
        requests_data = parse_datetime_fields(requests.data)
        return render_template('employee.html', requests=requests_data, language='ar')
    except Exception as e:
        logger.error(f"Error in employee page: {str(e)}")
        flash("حدث خطأ في النظام", "error")
        return redirect(url_for('index'))

@app.route('/update_total_hajj', methods=['POST'])
def update_total_hajj():
    """Update the total number of Hajj pilgrims"""
    try:
        total_hajj = request.form.get('total_hajj')
        if not total_hajj:
            return jsonify({"success": False, "error": "القيمة مطلوبة"}), 400

        try:
            total_hajj = int(total_hajj)
        except ValueError:
            return jsonify({"success": False, "error": "يجب أن تكون القيمة رقماً صحيحاً"}), 400

        # Try update first
        update_result = supabase.table('app_settings').update({'value': str(total_hajj)}).eq('key', 'total_hajj').execute()
        if not update_result.data or len(update_result.data) == 0:
            # If no row updated, insert new
            supabase.table('app_settings').insert({'key': 'total_hajj', 'value': str(total_hajj)}).execute()

        return jsonify({"success": True, "message": "تم تحديث إجمالي عدد الحجاج بنجاح"})
    except Exception as e:
        logger.error(f"Error updating total hajj: {str(e)}")
        return jsonify({"success": False, "error": "حدث خطأ في النظام"}), 500

@app.route('/admin')
def admin():
    """Admin page to manage requests"""
    try:
        requests = supabase.table('card_requests').select('*').order('created_at', desc=True).execute()
        total_hajj = get_total_hajj()
        requests_data = parse_datetime_fields(requests.data)
        return render_template('admin.html', 
                            requests=requests_data, 
                            language='ar',
                            total_hajj=total_hajj)
    except Exception as e:
        logger.error(f"Error in admin page: {str(e)}")
        flash("حدث خطأ في النظام", "error")
        return redirect(url_for('index'))

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

        # Check for duplicate active requests (Supabase fix)
        existing_request = supabase.table('card_requests').select('passport_number').eq('passport_number', passport_number).eq('status', 'New').execute()
        if existing_request.data and len(existing_request.data) > 0:
            flash(MESSAGES[language]['duplicate_request'].format(passport=passport_number), 'error')
            return redirect(url_for('employee'))
        
        # Create and save new request
        sa_tz = timezone(timedelta(hours=3))
        now = datetime.now(sa_tz).isoformat()
        new_request = {
            'employee_name': employee_name,
            'employee_number': employee_number,
            'hajj_name': hajj_name,
            'passport_number': passport_number,
            'visa_number': visa_number,
            'request_reason': request_reason,
            'card_returned': card_returned,
            'status': 'New',  # Ensure status is set
            'created_at': now,
            'updated_at': now
        }
        
        supabase.table('card_requests').insert(new_request).execute()
        
        flash(MESSAGES[language]['request_submitted'], 'success')
        return redirect(url_for('employee'))
    
    except Exception as e:
        logger.error(f"Error submitting request: {str(e)}", exc_info=True)
        language = get_language()
        # Show error message and code to user for debugging
        flash(f"{MESSAGES[language]['request_error']}\nError: {str(e)}", 'error')
        return redirect(url_for('employee'))

@app.route('/update_status/<int:request_id>', methods=['POST'])
def update_status(request_id):
    """Update the status of a request"""
    try:
        hajj_request = supabase.table('card_requests').select('*').eq('id', request_id).single()
        new_status = request.form.get('status')
        
        # Validate status value against allowed values
        allowed_statuses = ['New', 'found', 'request sent', 'card received', 'card delivered']
        if new_status not in allowed_statuses:
            return jsonify({
                "success": False, 
                "error": "قيمة الحالة غير صالحة"
            }), 400
            
        sa_tz = timezone(timedelta(hours=3))
        supabase.table('card_requests').update({'status': new_status, 'updated_at': datetime.now(sa_tz).isoformat()}).eq('id', request_id).execute()
        
        return jsonify({
            "success": True, 
            "status": new_status
        })
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")
        return jsonify({
            "success": False, 
            "error": "حدث خطأ في تحديث الحالة"
        }), 500

@app.route('/update_written/<int:request_id>', methods=['POST'])
def update_written(request_id):
    """Update the is_written flag of a request"""
    try:
        language = get_language()
        hajj_request = supabase.table('card_requests').select('*').eq('id', request_id).single()
        is_written = request.form.get('is_written', 'false')
        
        # Convert string to boolean
        is_written_bool = (is_written.lower() == 'true')
        sa_tz = timezone(timedelta(hours=3))
        supabase.table('card_requests').update({'is_written': is_written_bool, 'updated_at': datetime.now(sa_tz).isoformat()}).eq('id', request_id).execute()
        return jsonify({"success": True, "is_written": is_written_bool})
    except Exception as e:
        logger.error(f"Error updating written status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/statistics')
def statistics():
    """Statistics page showing various metrics"""
    try:
        total_hajj = get_total_hajj()
        total_lost = len(supabase.table('card_requests').select('id').eq('request_reason', "Lost Card").execute().data)
        total_damaged = len(supabase.table('card_requests').select('id').eq('request_reason', "Damaged Card").execute().data)
        total_uploaded = len(supabase.table('card_requests').select('id').eq('request_upload', True).execute().data)
        total_delivered = len(supabase.table('card_requests').select('id').eq('status', "card delivered").execute().data)
        total_received = len(supabase.table('card_requests').select('id').eq('status', "card received").execute().data)
        total_found = len(supabase.table('card_requests').select('id').eq('status', "found").execute().data)

        return render_template('statistics.html',
                            language='ar',
                            total_hajj=total_hajj,
                            total_lost=total_lost,
                            total_damaged=total_damaged,
                            total_uploaded=total_uploaded,
                            total_delivered=total_delivered,
                            total_received=total_received,
                            total_found=total_found)
    except Exception as e:
        logger.error(f"Error in statistics page: {str(e)}")
        flash("حدث خطأ في النظام", "error")
        return redirect(url_for('index'))
