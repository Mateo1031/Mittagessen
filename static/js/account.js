/**
 * AccountApp: Profil-Einstellungen und Bestellübersicht.
 */
const AccountApp = {
    init: function() {
        this.initEditButton();      // NEU: Fix für den Bearbeiten-Knopf
        this.initConfirmButtons();   // Bestätigungs-Modals
        this.initCheckables();       // Abhaken-Logik
        this.initCopyOrder();        // Kopier-Logik
        this.initConfirmOrderForms();
    },

    // 1. Fix für den "Bestellung bearbeiten" Button
    initEditButton: function() {
        const targetUrlInput = document.getElementById('target-menu-url');
        const editBtn = document.getElementById('btn-edit-order');
        
        if (targetUrlInput && editBtn && targetUrlInput.value) {
            editBtn.href = targetUrlInput.value;
            console.log("✅ Bearbeiten-Link gesetzt:", editBtn.href);
        }
    },

    // 2. Dropdown für Telefonnummern (Profil)
    togglePhone: function(id) {
        const el = document.getElementById(id);
        if (!el) return;
        
        const isOpen = el.style.display === "block";
        document.querySelectorAll('.phone-dropdown').forEach(d => d.style.display = 'none');
        el.style.display = isOpen ? "none" : "block";
    },

    // 3. Modals für Löschen / Bestätigen
    initConfirmButtons: function() {
        const modal = document.getElementById('confirm-modal');
        const modalMsg = document.getElementById('modal-message');
        const confirmBtn = document.getElementById('modal-confirm-btn');
        
        if (!modal) return;

        // Links und Buttons mit der Klasse .js-confirm oder .js-confirm-btn
        document.querySelectorAll('.js-confirm, .js-confirm-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                
                if (modalMsg) modalMsg.innerText = btn.getAttribute('data-msg') || "Bist du sicher?";
                
                // Falls es ein Formular-Button ist
                if (btn.tagName === 'BUTTON' || btn.classList.contains('js-confirm-btn')) {
                    const phonePrivate = btn.getAttribute('data-phone-private') === 'true';
                    
                    if (phonePrivate) {
                        if (modalMsg) modalMsg.innerHTML = 'Wirklich bestätigen? Mail wird gesendet.<br><br>⚠️ Deine Nummer ist aktuell <strong>privat</strong> – wenn du auf "Ja" klickst wird sie automatisch auf <strong>öffentlich</strong> gesetzt.';
                    }

                    confirmBtn.onclick = async (event) => {
                        event.preventDefault();
                        if (phonePrivate) {
                            await fetch('/toggle-show-phone/', {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                                    'X-Requested-With': 'XMLHttpRequest'
                                }
                            });
                        }
                        btn.closest('form').submit();
                    };
                    confirmBtn.href = "#";
                } else {
                    // Falls es ein normaler Link ist
                    confirmBtn.href = btn.href;
                    confirmBtn.onclick = null;
                }
                
                modal.style.display = 'flex';
            });
        });
    },

    // 4. Items in der Übersicht abhaken (Visuell)
    initCheckables: function() {
        document.querySelectorAll('.order-item-data').forEach(item => {
            item.addEventListener('click', function() {
                this.classList.toggle('checked');
            });
        });
    },

    // 5. Platzhalter für die Kopier-Funktion
    initCopyOrder: function() {
        document.querySelectorAll('.js-copy-order').forEach(btn => {
            btn.addEventListener('click', function() {
                // Falls du hier noch Logik brauchst, kann sie hier rein
                console.log("Kopieren geklickt");
            });
        });
    }
};

// Funktionen für HTML-Attribute (onclick) global verfügbar machen
window.togglePhone = (id) => AccountApp.togglePhone(id);

// Starten, wenn DOM bereit ist
document.addEventListener("DOMContentLoaded", () => AccountApp.init());
