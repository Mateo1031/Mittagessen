document.addEventListener("DOMContentLoaded", function() {
    console.log("WelcomeApp V6: Script gestartet.");

    // --- 1. GESPERRTE KARTEN (Modal öffnen) ---
    const lockedCards = document.querySelectorAll('.js-locked');
    console.log("Gesperrte Karten gefunden:", lockedCards.length);

    lockedCards.forEach(card => {
        card.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const el = e.currentTarget;
            const targetUrl = el.getAttribute('data-target');
            const cancelUrl = el.getAttribute('data-cancel');
            // FIX: data-own-type lesen (nicht data-type, das ist der bestehende Typ)
            const ownType = el.getAttribute('data-own-type');
            const existingType = el.getAttribute('data-existing-type');

            console.log("Gesperrte Karte geklickt:", { ownType, existingType, targetUrl, cancelUrl });
            showModal(existingType, ownType, cancelUrl, targetUrl);
        });
    });

    // --- 2. OFFENE KARTEN (Loader & Redirect) ---
    const openCards = document.querySelectorAll('.js-open');
    console.log("Offene Karten gefunden:", openCards.length);

    openCards.forEach(card => {
        card.addEventListener('click', function(e) {
            e.preventDefault();

            const el = e.currentTarget;
            const targetUrl = el.getAttribute('data-target');

            const loader = document.getElementById('page-loader');
            if (loader) loader.style.display = 'flex';

            console.log("Starte Scraper für:", targetUrl);

            fetch('/trigger-all-scrapers/')
                .then(() => {
                    console.log("Scraper fertig, leite weiter...");
                    window.location.href = targetUrl;
                })
                .catch((err) => {
                    console.error("Scraper Fehler:", err);
                    window.location.href = targetUrl;
                });

            // Fallback nach 3 Sekunden
            setTimeout(() => { window.location.href = targetUrl; }, 3000);
        });
    });

    // --- 3. ROTER STORNIEREN BUTTON (Unten) ---
    const cancelBtn = document.querySelector('.js-confirm-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const el = e.currentTarget;
            const href = el.getAttribute('data-href');
            const msg = el.getAttribute('data-msg');

            const modal = document.getElementById('confirm-modal');
            const modalMsg = document.getElementById('modal-message');
            const confirmBtn = document.getElementById('modal-confirm-btn');

            if (modalMsg) modalMsg.innerText = msg;
            if (confirmBtn) confirmBtn.href = href;

            if (modal) {
                modal.style.display = 'flex';
                setupModalClose(modal);
            }
        });
    }

    // --- HILFSFUNKTIONEN ---

    function showModal(existingType, targetType, cancelUrl, targetUrl) {
        const modal = document.getElementById('confirm-modal');
        const msg = document.getElementById('modal-message');
        const confirmBtn = document.getElementById('modal-confirm-btn');

        if (!modal) {
            console.error("Modal nicht gefunden!");
            return;
        }

        // FIX: Zeigt den bestehenden Typ und den gewünschten neuen Typ an
        if (msg) {
            msg.innerHTML = `Du hast bereits für <strong>${existingType}</strong> bestellt.<br><br>
                             Möchtest du stornieren und zu <strong>${targetType}</strong> wechseln?`;
        }

        if (confirmBtn) {
            confirmBtn.href = `${cancelUrl}?next=${encodeURIComponent(targetUrl)}`;
            console.log("Confirm-URL gesetzt:", confirmBtn.href);
        }

        // FIX: Kurzer Reset damit die Animation neu startet
        modal.style.display = 'none';
        void modal.offsetWidth;
        modal.style.display = 'flex';

        setupModalClose(modal);
    }

    function setupModalClose(modal) {
        const closeBtn = document.getElementById('modal-cancel-btn');
        if (closeBtn) {
            const newCloseBtn = closeBtn.cloneNode(true);
            closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);

            newCloseBtn.addEventListener('click', (e) => {
                e.preventDefault();
                modal.style.display = 'none';
            });
        }

        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };
    }
});
