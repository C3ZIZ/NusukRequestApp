"""Domain vocabulary: statuses, reasons, settings keys and Arabic strings.

Kept in one place so the database CHECK constraints, the route validation and
the Jinja templates can never drift apart.
"""

STATUS_NEW = "New"
STATUS_FOUND = "found"
STATUS_REQUEST_SENT = "request sent"
STATUS_CARD_RECEIVED = "card received"
STATUS_CARD_DELIVERED = "card delivered"

# Order matters: this is the order the options appear in the admin dropdown.
STATUSES = (
    STATUS_NEW,
    STATUS_FOUND,
    STATUS_REQUEST_SENT,
    STATUS_CARD_RECEIVED,
    STATUS_CARD_DELIVERED,
)

STATUS_LABELS_AR = {
    STATUS_NEW: "جديد",
    STATUS_FOUND: "تم العثور عليها",
    STATUS_REQUEST_SENT: "تم إرسال الطلب",
    STATUS_CARD_RECEIVED: "تم استلام البطاقة",
    STATUS_CARD_DELIVERED: "تم تسليم البطاقة",
}

# Bootstrap contextual class used for each status badge.
STATUS_BADGE_CLASSES = {
    STATUS_NEW: "bg-success",
    STATUS_FOUND: "bg-secondary",
    STATUS_REQUEST_SENT: "bg-info",
    STATUS_CARD_RECEIVED: "bg-primary",
    STATUS_CARD_DELIVERED: "bg-warning",
}

REASON_LOST = "Lost Card"
REASON_DAMAGED = "Damaged Card"

REASONS = (REASON_LOST, REASON_DAMAGED)

REASON_LABELS_AR = {
    REASON_LOST: "بطاقة مفقودة",
    REASON_DAMAGED: "بطاقة تالفة",
}

SETTING_TOTAL_HAJJ = "total_hajj"

# Employee numbers are Saudi mobile numbers: ten digits beginning with 05.
# Spelled [0-9] rather than \d, which in Python also matches Arabic-Indic
# digits and would store a number nobody can dial or search for.
EMPLOYEE_NUMBER_PATTERN = r"^05[0-9]{8}$"

MESSAGES_AR = {
    "employee_number_invalid": 'يجب أن يكون رقم الموظف 10 أرقام ويبدأ بـ "05"',
    "all_fields_required": "جميع الحقول مطلوبة",
    "reason_invalid": "سبب الطلب غير صالح",
    "duplicate_request": "يوجد بلاغ نشط بالفعل لرقم جواز السفر {passport}",
    "request_submitted": "تم تقديم البلاغ بنجاح!",
    "request_error": "حدث خطأ أثناء تقديم بلاغك.",
    "system_error": "حدث خطأ في النظام",
    "status_invalid": "قيمة الحالة غير صالحة",
    "request_not_found": "البلاغ غير موجود",
    "status_updated": "تم تحديث الحالة بنجاح",
    "total_hajj_required": "القيمة مطلوبة",
    "total_hajj_invalid": "يجب أن تكون القيمة رقماً صحيحاً موجباً",
    "total_hajj_updated": "تم تحديث إجمالي عدد الحجاج بنجاح",
}
