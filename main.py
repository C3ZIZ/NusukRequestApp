import logging
import re
from datetime import datetime
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
        setting = supabase.table('app_settings').select('value').eq('key', 'total_hajj').single()
        return int(setting['value']) if setting and setting['value'] else 0
    except (ValueError, TypeError) as e:
        logger.error(f"Error getting total hajj: {str(e)}")
        return 0

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
        return render_template('employee.html', requests=requests.data, language='ar')
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

        setting = supabase.table('app_settings').select('key').eq('key', 'total_hajj').single()
        if setting:
            supabase.table('app_settings').update({'value': str(total_hajj)}).eq('key', 'total_hajj').execute()
        else:
            supabase.table('app_settings').insert({'key': 'total_hajj', 'value': str(total_hajj)}).execute()

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating total hajj: {str(e)}")
        return jsonify({"success": False, "error": "حدث خطأ في النظام"}), 500

@app.route('/admin')
def admin():
    """Admin page to manage requests"""
    try:
        requests = supabase.table('card_requests').select('*').order('created_at', desc=True).execute()
        total_hajj = get_total_hajj()
        return render_template('admin.html', 
                            requests=requests.data, 
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
        new_request = {
            'employee_name': employee_name,
            'employee_number': employee_number,
            'hajj_name': hajj_name,
            'passport_number': passport_number,
            'visa_number': visa_number,
            'request_reason': request_reason,
            'card_returned': card_returned,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
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
        allowed_statuses = ['found', 'request sent', 'card received', 'card delivered']
        if new_status not in allowed_statuses:
            return jsonify({
                "success": False, 
                "error": "قيمة الحالة غير صالحة"
            }), 400
            
        supabase.table('card_requests').update({'status': new_status, 'updated_at': datetime.utcnow()}).eq('id', request_id).execute()
        
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
        supabase.table('card_requests').update({'is_written': is_written_bool, 'updated_at': datetime.utcnow()}).eq('id', request_id).execute()
        return jsonify({"success": True, "is_written": is_written_bool})
    except Exception as e:
        logger.error(f"Error updating written status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/statistics')
def statistics():
    """Statistics page showing various metrics"""
    try:
        total_hajj = get_total_hajj()
        total_lost = supabase.table('card_requests').select('id').eq('request_reason', "Lost Card").execute().count()
        total_uploaded = supabase.table('card_requests').select('id').eq('request_upload', True).execute().count()
        total_delivered = supabase.table('card_requests').select('id').eq('status', "card delivered").execute().count()
        total_received = supabase.table('card_requests').select('id').eq('status', "card received").execute().count()
        total_found = supabase.table('card_requests').select('id').eq('status', "found").execute().count()

        return render_template('statistics.html',
                            language='ar',
                            total_hajj=total_hajj,
                            total_lost=total_lost,
                            total_uploaded=total_uploaded,
                            total_delivered=total_delivered,
                            total_received=total_received,
                            total_found=total_found)
    except Exception as e:
        logger.error(f"Error in statistics page: {str(e)}")
        flash("حدث خطأ في النظام", "error")
        return redirect(url_for('index'))
