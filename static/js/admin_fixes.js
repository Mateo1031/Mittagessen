/**
 * AdminFixes: Repariert jQuery-Konflikte und Autocomplete-Warnungen im Admin.
 */
const AdminFixes = {
    init: function() {
        window.$ = window.jQuery = jQuery;
        this.fixAutocomplete();
        console.log("✅ Admin-Fixes geladen.");
    },
    fixAutocomplete: function() {
        const inputs = document.querySelectorAll('input:not([autocomplete])');
        inputs.forEach(input => input.setAttribute('autocomplete', 'on'));
    }
};

document.addEventListener("DOMContentLoaded", () => AdminFixes.init());
