// Common script for Hajj Card Request Management System

document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-close alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Table Sorting Functionality
function sortTable(table, column, asc = true) {
    const dirModifier = asc ? 1 : -1;
    const tBody = table.tBodies[0];
    const rows = Array.from(tBody.querySelectorAll('tr'));
    
    // Sort each row
    const sortedRows = rows.sort((a, b) => {
        const aColText = a.querySelector(`td:nth-child(${column + 1})`).textContent.trim();
        const bColText = b.querySelector(`td:nth-child(${column + 1})`).textContent.trim();
        
        return aColText > bColText ? (1 * dirModifier) : (-1 * dirModifier);
    });
    
    // Remove all existing TRs from the table
    while (tBody.firstChild) {
        tBody.removeChild(tBody.firstChild);
    }
    
    // Re-add the newly sorted rows
    tBody.append(...sortedRows);
    
    // Remember how the column is currently sorted
    table.querySelectorAll('th').forEach(th => th.classList.remove('th-sort-asc', 'th-sort-desc'));
    table.querySelector(`th:nth-child(${column + 1})`).classList.toggle('th-sort-asc', asc);
    table.querySelector(`th:nth-child(${column + 1})`).classList.toggle('th-sort-desc', !asc);
}

// Table search/filter functionality
function filterTable(tableId, searchInput) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const input = document.getElementById(searchInput);
    if (!input) return;
    
    input.addEventListener('keyup', function() {
        const filter = this.value.toUpperCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            let txtValue = row.textContent;
            if (txtValue.toUpperCase().indexOf(filter) > -1) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}
