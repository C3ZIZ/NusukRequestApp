from datetime import datetime
from app import supabase

# Create a test record for statistics
now = datetime.utcnow().isoformat()
test_request = {
    'employee_name': 'اختبار',
    'employee_number': '0512345678',
    'hajj_name': 'حاج اختبار',
    'passport_number': 'TST123456',
    'visa_number': 'VISA123456',
    'request_reason': 'Lost Card',
    'card_returned': False,
    'status': 'New',
    'created_at': now,
    'updated_at': now
}

result = supabase.table('card_requests').insert(test_request).execute()
print('Test record inserted:', result.data)
