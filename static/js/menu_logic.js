/**
 * MenuApp: Vollständige Logik für Warenkorb, Progress-Bar, Favoriten und Optionen.
 */
const MenuApp = {
    orderForm: null,
    favOnly: false,

    init: function() {
        console.log("🛒 MenuApp wird initialisiert...");
        this.orderForm = document.getElementById('order-form');
        
        this.initOrderLogic();
        this.initSubmitButtons();
        this.initFavs();         // Herz-Icons
        this.initFavFilter();    // Favoriten-Filter-Button
        this.initSearch();       // Suchfeld
        this.initStickyScroll(); // Obere Sticky-Bar
        
        // Einmal beim Laden alles berechnen
        this.updateTotal();
    },

    // --- BERECHNUNG & BARS (Inkl. Franken & Prozent Anzeige) ---
    updateTotal: function() {
        let currentSelectionTotal = 0;
        const checkboxes = document.querySelectorAll('.gericht-checkbox:checked');
        
        checkboxes.forEach(cb => {
            let dishPrice = parseFloat(cb.dataset.price.replace(',', '.'));
            currentSelectionTotal += dishPrice;
            
            const optionsContainer = document.querySelector(`#options-data-${cb.value}`);
            if (optionsContainer) {
                optionsContainer.querySelectorAll('input:checked').forEach(opt => {
                    let optPrice = parseFloat(opt.dataset.price?.replace(',', '.') || 0);
                    currentSelectionTotal += optPrice;
                });
                optionsContainer.querySelectorAll('input[type="number"]').forEach(opt => {
                    let qty = parseInt(opt.value || 0);
                    if (qty > 0) {
                        let optPrice = parseFloat(opt.dataset.price?.replace(',', '.') || 0);
                        currentSelectionTotal += (qty * optPrice);
                    }
                });
            }
        });

        // 1. Untere Sticky-Bar
        const stickyTotal = document.getElementById('sticky-total');
        const stickyBar = document.getElementById('sticky-order-bar');
        if (stickyTotal) stickyTotal.innerText = currentSelectionTotal.toFixed(2) + " CHF";
        if (stickyBar) stickyBar.classList.toggle('visible', currentSelectionTotal > 0);

        // 2. Progress-Bar & Status-Text
        const mindestwertInput = document.getElementById('mindestwert-val');
        const totalOthersInput = document.getElementById('total-others-val');

        if (mindestwertInput) {
            const mindestwert = parseFloat(mindestwertInput.value.replace(',', '.')) || 0;
            const totalOthers = totalOthersInput ? parseFloat(totalOthersInput.value.replace(',', '.')) : 0;
            const totalAll = totalOthers + currentSelectionTotal;

            let percent = mindestwert > 0 ? Math.min((totalAll / mindestwert) * 100, 100) : 100;
            let color = (totalAll >= mindestwert) ? "#10b981" : "#f59e0b";
            let missing = (mindestwert - totalAll).toFixed(2);

            // Elemente für die Zahlen-Anzeige (Franken & Prozent)
            const displayTotal = document.getElementById('display-total');
            const displayPercent = document.getElementById('display-percent');
            if (displayTotal) displayTotal.innerText = totalAll.toFixed(2);
            if (displayPercent) displayPercent.innerText = Math.round(percent) + "%";

            // Haupt-Progressbar Farbe & Breite
            const progressBar = document.getElementById('progress-bar');
            const statusText = document.getElementById('status-text');
            if (progressBar) {
                progressBar.style.width = percent + "%";
                progressBar.style.backgroundColor = color;
            }
            if (statusText) {
                statusText.style.color = (totalAll >= mindestwert) ? "#10b981" : "#64748b";
                statusText.innerHTML = (totalAll >= mindestwert) ? 
                    "✅ Mindestbestellwert erreicht!" : 
                    `Es fehlen noch <strong>${missing} CHF</strong>`;
            }

            // Sticky-Top-Progressbar (beim Scrollen)
            const stickyTopFill = document.getElementById('sticky-progress-fill');
            const stickyTopStatus = document.getElementById('sticky-top-status-text');
            const stickyTopValues = document.getElementById('sticky-top-values');
            
            if (stickyTopFill) {
                stickyTopFill.style.width = percent + "%";
                stickyTopFill.style.backgroundColor = color;
            }
            if (stickyTopStatus) {
                stickyTopStatus.innerText = (totalAll >= mindestwert) ? "✅ Ziel erreicht!" : "Fehlt: " + missing + " CHF";
                stickyTopStatus.style.color = color;
            }
            if (stickyTopValues) {
                stickyTopValues.innerText = totalAll.toFixed(2) + " / " + mindestwert.toFixed(2) + " CHF";
            }
        }
    },

    // --- MENGEN UND WARENKORB-LOGIK ---
    updateQty: function(btn, change) {
        const input = btn.parentElement.querySelector('input');
        if (input) {
            let newVal = (parseInt(input.value) || 0) + change;
            if (newVal >= 0 && newVal <= 15) {
                input.value = newVal;
                input.dispatchEvent(new Event('change'));
                this.updateTotal();
            }
        }
    },

    toggleNote: function(checkbox) {
        const container = checkbox.closest('tr').querySelector('.note-container');
        if(container) container.style.display = checkbox.checked ? 'block' : 'none';
    },

    initOrderLogic: function() {
        document.querySelectorAll('.selectable-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (['INPUT', 'BUTTON', 'A'].includes(e.target.tagName) || e.target.closest('.fav-icon') || e.target.closest('.note-container')) return;
                
                const cb = row.querySelector('.gericht-checkbox');
                if (cb) {
                    if (row.dataset.hasOptions === 'true' && !cb.checked) {
                        this.openOptions(cb, row.querySelector('[id^="options-data-"]'));
                    } else {
                        cb.checked = !cb.checked;
                        this.toggleNote(cb);
                        this.updateTotal();
                    }
                }
            });
        });
        document.querySelectorAll('.gericht-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                this.toggleNote(cb);
                this.updateTotal();
            });
        });
    },

    initSubmitButtons: function() {
        document.querySelectorAll('.btn-submit, .btn-sticky-submit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.orderForm) this.orderForm.submit();
            });
        });
    },

    // --- FAVORITEN & SUCHE ---
    initFavs: function() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        document.querySelectorAll('.fav-icon').forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.stopPropagation();
                const url = icon.dataset.url;
                const row = icon.closest('tr');

                fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'added') {
                        icon.innerText = '❤️';
                        if (row) row.dataset.isFav = 'true';
                    } else if (data.status === 'removed') {
                        icon.innerText = '🤍';
                        if (row) row.dataset.isFav = 'false';
                    }
                    if (this.favOnly) this.filterMenu();
                })
                .catch(err => console.error("Favoriten-Fehler:", err));
            });
        });
    },

    initFavFilter: function() {
        const favBtn = document.getElementById('fav-filter-btn');
        if (!favBtn) return;
        favBtn.addEventListener('click', () => {
            this.favOnly = !this.favOnly;
            if (this.favOnly) {
                favBtn.style.background = '#fef2f2';
                favBtn.style.color = '#ef4444';
                favBtn.style.borderColor = '#fecaca';
            } else {
                favBtn.style.background = 'white';
                favBtn.style.color = '#64748b';
                favBtn.style.borderColor = '#e2e8f0';
            }
            this.filterMenu();
        });
    },

    filterMenu: function() {
        const searchInput = document.getElementById('menu-search');
        const term = searchInput ? searchInput.value.toLowerCase() : "";
        let totalVisible = 0;

        document.querySelectorAll('.dish-row').forEach(row => {
            const dishName = row.querySelector('.dish-text')?.innerText.toLowerCase() || "";
            const categoryName = row.dataset.category ? row.dataset.category.toLowerCase() : "";
            const isFav = row.dataset.isFav === 'true';

            const matchesSearch = dishName.includes(term) || categoryName.includes(term);
            let show = matchesSearch;

            if (this.favOnly && !isFav) show = false;

            row.style.display = show ? '' : 'none';
            if (show) totalVisible++;
        });

        document.querySelectorAll('.category-row').forEach(catRow => {
            const catName = catRow.innerText.trim().replace(/"/g, '\\"');
            const children = document.querySelectorAll(`.dish-row[data-category="${catName}"]`);
            let hasVisible = false;
            children.forEach(c => { if(c.style.display !== 'none') hasVisible = true; });
            catRow.style.display = hasVisible ? '' : 'none';
        });

        const noResults = document.getElementById('no-results-message');
        if (noResults) noResults.style.display = totalVisible > 0 ? 'none' : 'table-row';
    },

    initSearch: function() {
        const input = document.getElementById('menu-search');
        if (input) input.addEventListener('keyup', () => this.filterMenu());
    },

    initStickyScroll: function() {
        window.addEventListener('scroll', () => {
            const bar = document.getElementById('sticky-top-progress');
            const card = document.getElementById('main-progress-card');
            if (bar && card) bar.classList.toggle('visible', card.getBoundingClientRect().bottom < 80);
        });
    },

    // --- OPTIONEN MODAL ---
    openOptions: function(checkbox, dataDiv) {
        const modal = document.getElementById('option-modal');
        const placeholder = document.getElementById('modal-content-placeholder');
        if (!modal || !placeholder) return;
        
        placeholder.innerHTML = '';
        const clone = dataDiv.cloneNode(true);
        clone.style.display = 'block';
        clone.id = ""; 
        placeholder.appendChild(clone);
        modal.style.display = 'flex';

        const btnSave = document.getElementById('btn-save-options');
        const btnCancel = document.getElementById('btn-cancel-options');

        if (btnSave) {
            btnSave.onclick = () => {
                // Check ob Pflichtfelder gewählt wurden
                const steps = placeholder.querySelectorAll('.step-card');
                let allValid = true;
                steps.forEach(step => {
                    if (step.querySelector('.req-star')) {
                        const radioInputs = step.querySelectorAll('input[type="radio"]');
                        if (radioInputs.length > 0 && !step.querySelector('input:checked')) {
                            allValid = false;
                        }
                    }
                });

                if (!allValid) {
                    if(window.GlobalCore) window.GlobalCore.showToast("Bitte wähle alle erforderlichen Optionen (*) aus.", "error");
                    return;
                }

                // Werte übertragen
                dataDiv.querySelectorAll('input').forEach(i => { if(i.type==='number') i.value=0; else i.checked=false; });
                placeholder.querySelectorAll('input:checked, input[type="number"]').forEach(i => {
                    const target = dataDiv.querySelector(`input[name="${i.name}"][value="${i.value}"], input[name="${i.name}"]`);
                    if (target) { if(i.type==='number') target.value = i.value; else target.checked = true; }
                });
                
                checkbox.checked = true;
                this.toggleNote(checkbox);
                this.updateTotal();
                modal.style.display = 'none';
            };
        }
        if (btnCancel) {
            btnCancel.onclick = () => {
                modal.style.display = 'none';
                checkbox.checked = false;
            };
        }
    }
};

// Globaler Export für +/- Buttons im HTML (onclick)
window.updateQty = (btn, change) => MenuApp.updateQty(btn, change);

document.addEventListener("DOMContentLoaded", () => MenuApp.init());
