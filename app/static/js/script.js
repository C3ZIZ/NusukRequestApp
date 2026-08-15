// Shared behaviour for every page. Table sorting and filtering live in the
// page templates, since each table has its own column layout.

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (element) {
        new bootstrap.Tooltip(element);
    });

    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (element) {
        new bootstrap.Popover(element);
    });

    // Dismiss server-rendered flash messages after five seconds. Transient
    // alerts raised by AJAX handlers manage their own lifetime.
    setTimeout(function () {
        document.querySelectorAll('.alert:not(.custom-alert)').forEach(function (alert) {
            if (alert.parentNode) {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        });
    }, 5000);
});
