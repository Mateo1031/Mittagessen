/**
 * RestaurantHub: Roulette, Voting, Filter und Modals für die Startseite.
 */
const RestaurantHub = {
    init: function() {
        console.log("🚀 RestaurantHub wird initialisiert...");
        this.initRoulette();
        this.initVoting();
        this.initClosedToggle();
        this.initVotersModal();
        this.initModalClosing();
    },

    // --- MODAL FUNKTIONEN (Zum Öffnen und Schließen) ---
    showVoters: function(id, name) {
        const modal = document.getElementById('voters-modal');
        const list = document.getElementById('voters-list');
        const title = document.getElementById('voters-modal-title');
        
        if (title) title.innerText = "Stimmen für " + name;
        if (list) list.innerHTML = '<li style="padding:20px; text-align:center;">Lade...</li>';
        if (modal) modal.style.display = 'flex';
        
        fetch(`/api/get_voters/${id}/`)
            .then(r => r.json())
            .then(data => {
                if (list) {
                    list.innerHTML = data.voters?.map(v => `
                        <li class="voter-item">
                            <div class="voter-avatar">${v.substring(0,2).toUpperCase()}</div>
                            <span class="voter-name">${v}</span>
                        </li>
                    `).join('') || '<li style="padding:20px; text-align:center;">Keine Stimmen gefunden.</li>';
                }
            })
            .catch(err => {
                if (list) list.innerHTML = '<li style="padding:20px; color:red;">Fehler beim Laden.</li>';
            });
    },

    closeVotersModal: function() {
        const modal = document.getElementById('voters-modal');
        if (modal) modal.style.display = 'none';
    },

    closeConflictModal: function() {
        const modal = document.getElementById('conflict-modal');
        if (modal) modal.style.display = 'none';
    },

    // 1. Der Zufalls-Knopf (Roulette)
    initRoulette: function() {
        const btn = document.getElementById('btn-roulette');
        if (!btn) return;

        btn.addEventListener('click', () => {
            const cards = Array.from(document.querySelectorAll('.restaurant-card:not(.card-closed)'));
            const toast = document.getElementById('random-toast'); // Unser schicker Toast

            // PRÜFUNG: Weniger als 2 offen?
            if (cards.length < 2) {
                if (toast) {
                    toast.style.display = 'block';
                    // Nach 4 Sekunden wieder verstecken
                    setTimeout(() => {
                        toast.style.opacity = '0';
                        toast.style.transition = 'opacity 0.5s ease';
                        setTimeout(() => {
                            toast.style.display = 'none';
                            toast.style.opacity = '1';
                        }, 500);
                    }, 4000);
                } else {
                    // Fallback, falls der Toast im HTML fehlt
                    alert("Es müssen mindestens 2 Restaurants geöffnet sein!");
                }
                return;
            }

            // ROULETTE STARTET
            btn.disabled = true;
            btn.innerText = "🎲 Der Zufall entscheidet...";
            document.querySelectorAll('.restaurant-card').forEach(c => c.classList.remove('roulette-highlight', 'roulette-winner'));

            let rounds = 0;
            const maxRounds = Math.floor(Math.random() * 15) + 25;
            let currentDelay = 50;
            let currentIndex = -1;

            const jump = () => {
                if (currentIndex >= 0) cards[currentIndex].classList.remove('roulette-highlight');
                let nextIndex;
                do { nextIndex = Math.floor(Math.random() * cards.length); } while (nextIndex === currentIndex);

                currentIndex = nextIndex;
                const currentCard = cards[currentIndex];
                currentCard.classList.add('roulette-highlight');
                currentCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

                if (++rounds < maxRounds) {
                    currentDelay += 15;
                    setTimeout(jump, currentDelay);
                } else {
                    // GEWINNER GEFUNDEN
                    currentCard.classList.replace('roulette-highlight', 'roulette-winner');
                    btn.disabled = false;
                    btn.innerText = "🔄 Neues Restaurant auslosen";

                    // AUTOMATISCH ZUM MENÜ LEITEN (nach kurzer Pause)
                    setTimeout(() => {
                        const menuBtn = currentCard.querySelector('.btn-menu');
                        if (menuBtn) {
                            menuBtn.click(); // Klickt den "Zum Menü" Button des Gewinners
                        }
                    }, 1200);
                }
            };
            jump();
        });
    },

    // 2. Schalter für geschlossene Restaurants
    initClosedToggle: function() {
        const toggleSwitch = document.getElementById('toggleClosed');
        if (!toggleSwitch) return;

        const toggleVisibility = (hide) => {
            document.querySelectorAll('.card-closed').forEach(card => {
                const gridColumn = card.closest('[class*="col-"]') || card;
                gridColumn.style.display = hide ? 'none' : '';
            });
            localStorage.setItem('hideClosedRestaurants', hide);
            
            // Labels anpassen
            const lAll = document.getElementById('label-all');
            const lOpen = document.getElementById('label-open');
            if(lAll) lAll.classList.toggle('text-muted', hide);
            if(lOpen) lOpen.classList.toggle('text-muted', !hide);
        };

        const isHidden = localStorage.getItem('hideClosedRestaurants') === 'true';
        toggleSwitch.checked = isHidden;
        toggleVisibility(isHidden);
        toggleSwitch.addEventListener('change', (e) => toggleVisibility(e.target.checked));
    },

    // 3. Voting & Konflikt
    initVoting: function() {
        document.querySelectorAll('.ajax-vote-form, .menu-form-check').forEach(form => {
            form.addEventListener('submit', (e) => {
                const resId = form.getAttribute('data-res-id');
                if (this.checkConflict(resId)) {
                    e.preventDefault();
                } else if (form.classList.contains('ajax-vote-form')) {
                    e.preventDefault();
                    this.runAjaxVote(form);
                }
            });
        });
    },

    checkConflict: function(targetId) {
        const existingId = document.getElementById('current-order-res-id')?.value;
        if (!existingId || existingId === "None" || existingId == targetId) return false;

        const modal = document.getElementById('conflict-modal');
        const name = document.getElementById('current-order-res-name')?.value || "einem anderen Restaurant";
        
        const display = document.getElementById('conflict-res-name');
        if (display) display.innerText = name;
        
        const confirmBtn = document.getElementById('conflict-confirm-btn');
        if (confirmBtn) {
            const baseUrl = confirmBtn.getAttribute('data-base-url') || confirmBtn.href.split('?')[0];
            confirmBtn.href = `${baseUrl}?next=/menu/${targetId}/`;
        }
        if (modal) modal.style.display = 'flex';
        return true;
    },

    runAjaxVote: function(form) {
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.json())
        .then(data => {
            if (['success', 'added', 'removed'].includes(data.status)) location.reload();
            else if (window.GlobalCore) window.GlobalCore.showToast(data.message, 'info');
        });
    },

    // 4. Inits für die Modals
    initVotersModal: function() {
        // Diese Funktion wird über showVoters oben gesteuert
    },

    initModalClosing: function() {
        const cModal = document.getElementById('conflict-modal');
        const vModal = document.getElementById('voters-modal');
        window.addEventListener('click', (e) => {
            if (e.target === cModal) this.closeConflictModal();
            if (e.target === vModal) this.closeVotersModal();
        });
    }
};

// --- WICHTIG: EXPORT FÜR DEN BROWSER ---
// Damit onclick="closeVotersModal()" im HTML funktioniert:
window.showVoters = (id, name) => RestaurantHub.showVoters(id, name);
window.closeVotersModal = () => RestaurantHub.closeVotersModal();
window.closeConflictModal = () => RestaurantHub.closeConflictModal();

document.addEventListener("DOMContentLoaded", () => RestaurantHub.init());
