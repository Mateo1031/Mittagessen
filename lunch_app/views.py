from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
import datetime 
from .models import Restaurant, Gericht, Bestellung

# --- Diese Funktion hat gefehlt ---
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Konto erstellt! Bitte einloggen.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'lunch_app/register.html', {'form': form})
# ----------------------------------

@login_required
def restaurant_liste(request):
    restaurants = Restaurant.objects.all()
    return render(request, 'lunch_app/index.html', {'restaurants': restaurants})

@login_required
def restaurant_menu(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    
    # Zeitprüfung für die Anzeige
    now = timezone.localtime(timezone.now())
    deadline = datetime.time(11, 0) # 11:00 Uhr
    
    ist_zu_spaet = now.time() > deadline

    context = {
        'restaurant': restaurant,
        'ist_zu_spaet': ist_zu_spaet
    }
    return render(request, 'lunch_app/menu.html', context)

@login_required
def bestellung_abschliessen(request):
    if request.method == 'POST':
        
        # Sicherheitsprüfung der Zeit
        now = timezone.localtime(timezone.now())
        deadline = datetime.time(11, 0)
        
        if now.time() > deadline:
            messages.error(request, "Bestellschluss war um 11:00 Uhr! Bestellung nicht gespeichert.")
            return redirect('home')

        gewaehlte_gerichte_ids = request.POST.getlist('gerichte')
        
        if not gewaehlte_gerichte_ids:
            messages.warning(request, "Du hast nichts ausgewählt!")
            return redirect('home')

        for gericht_id in gewaehlte_gerichte_ids:
            gericht = get_object_or_404(Gericht, id=gericht_id)
            Bestellung.objects.create(benutzer=request.user, gericht=gericht)
        
        anzahl = len(gewaehlte_gerichte_ids)
        messages.success(request, f'{anzahl} Gerichte erfolgreich bestellt!')
        return redirect('uebersicht')
    
    return redirect('home')

@login_required
def bestell_uebersicht(request):
    # Zeige nur heutige Bestellungen
    heute = timezone.localtime(timezone.now()).date()
    
    bestellungen = Bestellung.objects.filter(datum__date=heute).select_related('benutzer', 'gericht', 'gericht__restaurant')

    user_daten = {}
    gesamt_total = 0

    for bestellung in bestellungen:
        user = bestellung.benutzer
        if user not in user_daten:
            user_daten[user] = {'items': [], 'summe': 0}
        
        user_daten[user]['items'].append(bestellung)
        user_daten[user]['summe'] += bestellung.gericht.preis
        gesamt_total += bestellung.gericht.preis

    context = {
        'user_daten': user_daten,
        'gesamt_total': gesamt_total
    }
    return render(request, 'lunch_app/uebersicht.html', context)
