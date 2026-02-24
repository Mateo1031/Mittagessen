from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.messages import get_messages
from django.utils import timezone
from django.core.mail import send_mail
from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model, logout
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from .forms import UserUpdateForm, ProfileUpdateForm, CustomRegisterForm
from . import scrapers
import datetime
import re
import sys 
from .models import Restaurant, Gericht, Bestellung, Stimme, Favorit, User, OptionGroup, OptionItem, TagesVerantwortlicher, UserProfile, Schulden, Standort, SystemEinstellungen

def get_deadline():
    """Holt die globale Bestell-Deadline aus der Datenbank."""
    einstellungen = SystemEinstellungen.objects.first()
    if einstellungen and einstellungen.bestellschluss:
        return einstellungen.bestellschluss
    return datetime.time(11, 0) # Fallback, falls nichts eingestellt ist

def clear_messages(request):
    storage = get_messages(request)
    for _ in storage: pass

def aufraemen_alter_daten():
    heute = timezone.now().date()
    Stimme.objects.filter(datum__lt=heute).delete()
    Bestellung.objects.filter(datum__date__lt=heute).delete()

def register(request):
    if request.method == 'POST':
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.email:
                betreff = "Willkommen bei der Lunch-App! 🥗"
                nachricht = (
                    f"Hallo {user.get_full_name()},\n\n"
                    f"vielen Dank für deine Registrierung!\n"
                    f"Dein Account wurde erfolgreich erstellt. Du kannst dich ab sofort einloggen und dein Mittagessen mit dem Team organisieren.\n\n"
                    f"Guten Appetit!\n"
                    f"Dein Lunch-Team"
                )
                try:
                    send_mail(subject=betreff, message=nachricht, from_email=None, recipient_list=[user.email], fail_silently=True)
                except Exception as e:
                    print(f"Fehler beim Willkommens-Mailversand: {e}")
            messages.success(request, 'Konto erfolgreich erstellt! Bitte logge dich jetzt ein.')
            return redirect('login')
    else:
        form = CustomRegisterForm()
    return render(request, 'lunch_app/register.html', {'form': form})

@login_required
def welcome(request):
    heute = timezone.now().date()
    existing_order = Bestellung.objects.filter(benutzer=request.user, datum__date=heute).first()
    existing_order_art = existing_order.art if existing_order else None
    
    # NEU: Prüfen, ob der User heute im Urlaub/Abwesend ist
    ist_abwesend = False
    profile = getattr(request.user, 'profile', None)
    if profile and profile.abwesend_von and profile.abwesend_bis:
        if profile.abwesend_von <= heute <= profile.abwesend_bis:
            ist_abwesend = True
            
    context = {
        'existing_order_art': existing_order_art,
        'ist_abwesend': ist_abwesend,
        'abwesend_bis': profile.abwesend_bis if ist_abwesend else None
    }
    return render(request, 'lunch_app/welcome.html', context)

@login_required
def restaurant_liste(request, art):

    aktiver_standort_id = request.session.get('aktiver_standort_id')
    
    # 2. Wenn noch nichts in der Session ist, nehmen wir den Standard-Standort des Users
    if not aktiver_standort_id and hasattr(request.user, 'profile') and request.user.profile.standard_standort:
        aktiver_standort_id = request.user.profile.standard_standort.id
        request.session['aktiver_standort_id'] = aktiver_standort_id

    # 3. RESTAURANTS FILTERN (Hier passiert die Magie!)
    if aktiver_standort_id:
        # Nur Restaurants laden, die genau diese Standort-ID haben
        restaurants = Restaurant.objects.filter(standort_id=aktiver_standort_id)
    else:
        # Fallback: Falls gar kein Standort gesetzt ist, zeige alle
        restaurants = Restaurant.objects.all()

    aufraemen_alter_daten()
    heute = timezone.now().date()
    request.session['gewaehlte_art'] = art
    
    base_query = restaurants.annotate(
        stimmen_anzahl=Count('stimmen', filter=Q(stimmen__datum=heute, stimmen__art=art))
    ).prefetch_related('zeiten', 'ausnahmen')
    
    if art == 'LOKAL':
        gefilterte_restaurants = base_query.filter(biete_lokal=True)
        titel = "🍽️ Restaurants (Vor Ort)"
    elif art == 'TAKEAWAY':
        gefilterte_restaurants = base_query.filter(biete_takeaway=True)
        titel = "🥡 Take-Away Angebote"
    elif art == 'DELIVERY':
        gefilterte_restaurants = base_query.filter(biete_delivery=True)
        titel = "🛵 Lieferdienste"
    else:
        gefilterte_restaurants = base_query
        titel = "Alle Restaurants"

    # === HIER KOMMT DER NEUE SUCH-BLOCK HIN ===
    suchbegriff = request.GET.get('q')
    if suchbegriff:
        # Achtung: Die Variable heißt hier 'gefilterte_restaurants'
        gefilterte_restaurants = gefilterte_restaurants.filter(
            Q(name__icontains=suchbegriff) | 
            Q(beschreibung__icontains=suchbegriff) | 
            Q(gerichte__name__icontains=suchbegriff)
        ).distinct()
    # === ENDE SUCH-BLOCK ===

    top_restaurants = gefilterte_restaurants.filter(stimmen_anzahl__gt=0).order_by('-stimmen_anzahl')[:3]
    user_vote = Stimme.objects.filter(benutzer=request.user, datum=heute, art=art).first()
    user_vote_id = user_vote.restaurant.id if user_vote else None

    existing_order = Bestellung.objects.filter(benutzer=request.user, datum__date=heute).first()
    existing_order_art = existing_order.art if existing_order else None
    
    context = {
        'restaurants': gefilterte_restaurants.order_by('name'),
        'top_restaurants': top_restaurants,
        'user_vote_id': user_vote_id, 
        'page_title': titel,
        'current_art': art,
        'existing_order_art': existing_order_art, 
        'existing_order_restaurant_id': existing_order.gericht.restaurant.id if existing_order else None,
        'existing_order_restaurant_name': existing_order.gericht.restaurant.name if existing_order else None,
    }
    return render(request, 'lunch_app/index.html', context)

@login_required
def restaurant_menu(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    heute = timezone.localtime(timezone.now()).date()
    vorauswahl_art = request.session.get('gewaehlte_art', 'LOKAL')
    existing_order = Bestellung.objects.filter(benutzer=request.user, datum__date=heute).first()
    existing_order_art = existing_order.art if existing_order else None

    fremde = Bestellung.objects.filter(benutzer=request.user, datum__date=heute).exclude(gericht__restaurant=restaurant).select_related('gericht__restaurant').first()
    if fremde:
        clear_messages(request)
        messages.error(request, f"⚠️ Bestellung bei {fremde.gericht.restaurant.name} ist schon final. Stornierung blockiert.")
        return redirect('uebersicht')

    gerichte_liste = list(restaurant.gerichte.all().prefetch_related('option_groups__items', 'option_groups__items__gericht_verweis').order_by('kategorie', 'reihenfolge'))
    eigene_bestellungen = Bestellung.objects.filter(benutzer=request.user, datum__date=heute, gericht__restaurant=restaurant)
    
    bestell_map = {b.gericht_id: {'notiz': b.notiz if b.notiz else "", 'optionen': b.optionen_text} for b in eigene_bestellungen}
    bereits_bestellt_ids = list(bestell_map.keys())
    alte_art = eigene_bestellungen.first().art if eigene_bestellungen.exists() else vorauswahl_art
    total_others = Bestellung.objects.filter(datum__date=heute, gericht__restaurant=restaurant).exclude(benutzer=request.user).aggregate(Sum('gericht__preis'))['gericht__preis__sum'] or 0

    andere_bestellungen = Bestellung.objects.filter(datum__date=heute, gericht__restaurant=restaurant).exclude(benutzer=request.user).select_related('benutzer')
    social_proof = {}
    for b in andere_bestellungen:
        if b.gericht_id not in social_proof: social_proof[b.gericht_id] = []
        if len(social_proof[b.gericht_id]) < 5: social_proof[b.gericht_id].append(b.benutzer.username[:2].upper())

    favoriten_ids = list(Favorit.objects.filter(benutzer=request.user, gericht__restaurant=restaurant).values_list('gericht_id', flat=True))

    for g in gerichte_liste:
        g.saved_note = bestell_map[g.id]['notiz'] if g.id in bestell_map else ""

    mindestwert = restaurant.mindestbestellwert
    own_db_total = eigene_bestellungen.aggregate(Sum('gericht__preis'))['gericht__preis__sum'] or 0
    current_total_display = total_others + own_db_total
    
    progress_percent = min((current_total_display / mindestwert) * 100, 100) if mindestwert > 0 else 0
    missing_amount = max(mindestwert - current_total_display, 0) if mindestwert > 0 else 0
    goal_reached = current_total_display >= mindestwert if mindestwert > 0 else True

    now = timezone.localtime(timezone.now())
    deadline = get_deadline()
    
    check_art = existing_order_art if existing_order_art else vorauswahl_art
    
    org_entry = TagesVerantwortlicher.objects.filter(
        restaurant=restaurant, 
        datum=heute, 
        art=check_art
    ).first()
    
    is_locked = True if (org_entry and org_entry.bestellung_bestaetigt) else False
    
    return render(request, 'lunch_app/menu.html', {
        'restaurant': restaurant,
        'ist_zu_spaet': now.time() > deadline,
        'current_total': current_total_display,
        'total_others': total_others,
        'mindestwert': mindestwert,
        'progress_percent': progress_percent,
        'missing_amount': missing_amount,
        'goal_reached': goal_reached,
        'bereits_bestellt_ids': bereits_bestellt_ids, 
        'alte_art': alte_art,
        'social_proof': social_proof,
        'favoriten_ids': favoriten_ids,
        'gerichte_liste': gerichte_liste,
        'existing_order_art': existing_order_art
    })

@login_required
def bestellung_abschliessen(request):
    if request.method == 'POST':
        now = timezone.localtime(timezone.now())
        deadline = get_deadline()
        heute = now.date()
        restaurant_id = request.POST.get('restaurant_id')
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)

        current_art = request.POST.get('art') or request.session.get('gewaehlte_art', 'LOKAL')

        check_org = TagesVerantwortlicher.objects.filter(
            restaurant=restaurant, 
            datum=heute, 
            art=current_art
        ).first()
        
        if check_org and check_org.bestellung_bestaetigt:
            messages.error(request, "⚠️ Die Bestellung ist bereits abgeschlossen! Keine Änderungen mehr möglich.")
            return redirect('uebersicht')

        if now.time() > deadline and not request.user.is_superuser:
            clear_messages(request)
            messages.error(request, "Zu spät! Bestellschluss war um 11:00 Uhr.")
            return redirect('home')

        
        Stimme.objects.update_or_create(benutzer=request.user, datum=heute, defaults={'restaurant': restaurant, 'art': current_art})
        Bestellung.objects.filter(benutzer=request.user, datum__date=heute, gericht__restaurant=restaurant).delete()

        gewaehlte_gerichte_ids = request.POST.getlist('gerichte')
        if gewaehlte_gerichte_ids:
            for g_id in gewaehlte_gerichte_ids:
                notiz_text = request.POST.get(f'notiz_{g_id}', '').strip()
                gericht = Gericht.objects.get(id=g_id)
                optionen_liste = []
                for gruppe in gericht.option_groups.all():
                    if gruppe.typ == 'RADIO':
                        item_id = request.POST.get(f"group_{gruppe.id}")
                        if item_id:
                            item = OptionItem.objects.get(id=item_id)
                            optionen_liste.append(f"{item.gericht_verweis.name if item.gericht_verweis else item.name}{' (+'+str(item.aufpreis)+')' if item.aufpreis > 0 else ''}")
                    elif gruppe.typ == 'CHECKBOX':
                        for item_id in request.POST.getlist(f"group_{gruppe.id}"):
                            item = OptionItem.objects.get(id=item_id)
                            optionen_liste.append(f"{item.gericht_verweis.name if item.gericht_verweis else item.name}{' (+'+str(item.aufpreis)+')' if item.aufpreis > 0 else ''}")
                    elif gruppe.typ == 'NUMBER':
                        for item in gruppe.items.all():
                            qty = request.POST.get(f"qty_{item.id}")
                            if qty and int(qty) > 0:
                                optionen_liste.append(f"{qty}x {item.gericht_verweis.name if item.gericht_verweis else item.name}{' (+'+str(item.aufpreis*int(qty))+')' if item.aufpreis > 0 else ''}")

                Bestellung.objects.create(benutzer=request.user, gericht_id=g_id, art=current_art, notiz=notiz_text or None, optionen_text=" | ".join(optionen_liste) or None)
            messages.success(request, "Gespeichert!")
            
        # ... dein vorheriger Code (Bestellung create etc.) ...
        
        # NEU: Bei LOKAL nur anmelden, kein Gericht nötig
        if current_art == 'LOKAL':
            Bestellung.objects.filter(benutzer=request.user, datum__date=heute, art='LOKAL').delete()
            # Dummy-Bestellung ohne Gericht
            Bestellung.objects.create(
                benutzer=request.user,
                gericht=None,
                art='LOKAL',
                lokal_anmeldung=True
            )
            Stimme.objects.update_or_create(
                benutzer=request.user, 
                datum=heute, 
                defaults={'restaurant': restaurant, 'art': 'LOKAL'}
            )
            messages.success(request, "✋ Du bist dabei!")
            return redirect('uebersicht')
    return redirect('uebersicht')

@login_required
def bestellung_stornieren(request, bestellung_id):
    bestellung = get_object_or_404(Bestellung, id=bestellung_id)
    if bestellung.benutzer != request.user and not request.user.is_superuser: return redirect('uebersicht')
    now = timezone.localtime(timezone.now())
    if now.time() > get_deadline() and not request.user.is_superuser:
        messages.error(request, "Zu spät.")
        return redirect('uebersicht')
    
    res, heute = bestellung.gericht.restaurant, bestellung.datum.date()
    
    check_org = TagesVerantwortlicher.objects.filter(
        restaurant=res, 
        datum=heute, 
        art=bestellung.art
    ).first()
    
    if check_org and check_org.bestellung_bestaetigt and not request.user.is_superuser:
        messages.error(request, "⚠️ Bestellung ist bereits finalisiert. Stornierung nicht mehr möglich.")
        return redirect('uebersicht')
    
    bestellung.delete()
    if not Bestellung.objects.filter(benutzer=request.user, datum__date=heute, gericht__restaurant=res).exists():
        Stimme.objects.filter(benutzer=request.user, datum=heute, restaurant=res).delete()
        return redirect('home')
    return redirect('uebersicht')

@login_required
def eigene_bestellung_stornieren(request):
    now = timezone.localtime(timezone.now())
    next_url = request.GET.get('next', '/')
    heute = now.date()
    if now.time() > get_deadline() and not request.user.is_superuser:
        messages.error(request, "Zu spät.")
        return redirect(next_url if next_url else 'uebersicht')
        
    eigene_bestellungen = Bestellung.objects.filter(benutzer=request.user, datum__date=heute)
    
    for b in eigene_bestellungen:
        check_org = TagesVerantwortlicher.objects.filter(
            restaurant=b.gericht.restaurant, 
            datum=heute, 
            art=b.art
        ).first()
        
        if check_org and check_org.bestellung_bestaetigt:
            messages.error(request, f"⚠️ Bestellung bei {b.gericht.restaurant.name} ist schon final. Stornierung blockiert.")
            return redirect(next_url if next_url else 'uebersicht')

    # Wenn Prüfung okay, dann löschen
    Bestellung.objects.filter(benutzer=request.user, datum__date=heute).delete()
        
    Bestellung.objects.filter(benutzer=request.user, datum__date=now.date()).delete()
    Stimme.objects.filter(benutzer=request.user, datum=now.date()).delete()
    messages.success(request, "Storniert.")
    return redirect(next_url if next_url else 'home')

@login_required
def alles_loeschen(request):
    if not request.user.is_superuser: return redirect('uebersicht')
    heute = timezone.now().date()
    Bestellung.objects.filter(datum__date=heute).delete()
    Stimme.objects.filter(datum=heute).delete()
    return redirect('uebersicht')

def auto_tagesabschluss():
    heute = timezone.now().date()
    alte_organizers = TagesVerantwortlicher.objects.filter(datum__lt=heute)
    if not alte_organizers.exists() and not Bestellung.objects.filter(datum__date__lt=heute).exists():
        Stimme.objects.filter(datum__lt=heute).delete()
        return 0 
    count = 0
    with transaction.atomic(): 
        for org in alte_organizers:
            if org.art == 'LOKAL':
                Bestellung.objects.filter(datum__date=org.datum, gericht__restaurant=org.restaurant).delete()
                continue
                
            alle_besteller_count = Bestellung.objects.filter(datum__date=org.datum, gericht__restaurant=org.restaurant, art=org.art).values('benutzer').distinct().count()
            liefergebuehr = org.restaurant.liefergebuehren
            anteil_pro_person = float(liefergebuehr) / alle_besteller_count if (liefergebuehr > 0 and alle_besteller_count > 0) else 0.0
                
            bestellungen = Bestellung.objects.filter(datum__date=org.datum, gericht__restaurant=org.restaurant).exclude(benutzer=org.nutzer)
            seen_users_debt = set() 
        
            for b in bestellungen:
                preis = float(b.gericht.preis)
                if b.optionen_text:
                    matches = re.findall(r'\(\+(\d+(?:\.\d+)?)\)', b.optionen_text)
                    for m in matches: 
                        preis += float(m)
                
                # WICHTIG: Den Lieferanteil NUR beim ersten Gericht der Person aufschlagen!
                if b.benutzer.id not in seen_users_debt:
                    preis += anteil_pro_person
                    seen_users_debt.add(b.benutzer.id)
                z_art = getattr(org, 'zahlungsart', 'SONST')
                Schulden.objects.create(glaeubiger=org.nutzer, schuldner=b.benutzer, betrag=preis, datum=org.datum, zahlungsart=z_art)
                count += 1
            Bestellung.objects.filter(datum__date=org.datum, gericht__restaurant=org.restaurant).delete()
        alte_organizers.delete()
        Bestellung.objects.filter(datum__date__lt=heute).delete()
        Stimme.objects.filter(datum__lt=heute).delete()

    User = get_user_model()
    for nutzer in User.objects.exclude(email=''):
        if hasattr(nutzer, 'profile') and not nutzer.profile.notify_debt: continue
        meine_s = Schulden.objects.filter(schuldner=nutzer, erledigt=False)
        mir_s = Schulden.objects.filter(glaeubiger=nutzer, erledigt=False)
        if meine_s.exists() or mir_s.exists():
            msg = f"Hallo {nutzer.get_full_name() or nutzer.username},\n\nTag abgeschlossen.\n"
            send_mail("🤖 Lunch-Abschluss", msg, None, [nutzer.email], fail_silently=True)
    return count

@login_required
def bestell_uebersicht(request):
    auto_tagesabschluss()
    heute = timezone.localtime(timezone.now()).date()
    
    # 1. Aktiven Standort ermitteln (genau wie auf der Startseite)
    aktiver_standort_id = request.session.get('aktiver_standort_id')
    if not aktiver_standort_id and hasattr(request.user, 'profile') and request.user.profile.standard_standort:
        aktiver_standort_id = request.user.profile.standard_standort.id
        request.session['aktiver_standort_id'] = aktiver_standort_id

    # 2. Basis-Abfrage: Alle Bestellungen von heute
    bestellungen = Bestellung.objects.filter(datum__date=heute)

    # 3. FILTERN: Nur Bestellungen für Restaurants an diesem Standort!
    if aktiver_standort_id:
        # Wir filtern über 2 Ecken: Bestellung -> Gericht -> Restaurant -> Standort
        bestellungen = bestellungen.filter(gericht__restaurant__standort_id=aktiver_standort_id)

    # 4. Daten für die Anzeige optimieren und sortieren
    bestellungen = bestellungen.select_related(
        'benutzer', 'gericht', 'gericht__restaurant'
    ).order_by('gericht__restaurant__name', 'art', 'benutzer__username')

    user_hat_bestellt = Bestellung.objects.filter(benutzer=request.user, datum__date=heute).exists()
    
    restaurant_daten = {}
    gesamt_total = 0
    
    # ... ab hier bleibt dein restlicher Code der Funktion exakt gleich! ...
    # for b in bestellungen:
    #     res = b.gericht.restaurant
    # ...
    
    for b in bestellungen:
        res = b.gericht.restaurant
        group_key = f"{res.id}_{b.art}" 
        
        if group_key not in restaurant_daten:
            verantwortlicher = TagesVerantwortlicher.objects.filter(restaurant=res, datum=heute, art=b.art).first()

            restaurant_daten[group_key] = {
                'items': [], 
                'zusammenfassung': {}, 
                'summe': 0, 
                'mindestwert': res.mindestbestellwert,
                'percent': 0, 
                'reached': False, 
                'missing': 0,
                'restaurant_obj': res,
                'art': b.art,
                'art_display': b.get_art_display(),
                'bestellzeit': verantwortlicher.bestellzeit if verantwortlicher else None,
                'bestaetigt': verantwortlicher.bestellung_bestaetigt if verantwortlicher else False,
                # HIER WIRD DIE ZAHLUNGSART AN DAS TEMPLATE ÜBERGEBEN
                'zahlungsart': getattr(verantwortlicher, 'zahlungsart', 'SONST') if verantwortlicher else 'SONST',
                'organizer': verantwortlicher.nutzer if (verantwortlicher and verantwortlicher.nutzer_id) else None,
                'fahrer_liste': verantwortlicher.fahrer.all() if verantwortlicher else [],
                'bestellzeit': verantwortlicher.bestellzeit if verantwortlicher else None,
            }
        
                # NEU:
        if b.lokal_anmeldung or not b.gericht:
            preis = 0
        else:
            preis = float(b.gericht.preis)
        if b.optionen_text:
            for m in re.findall(r'\(\+(\d+(?:\.\d+)?)\)', b.optionen_text): preis += float(m)
        b.kalkulierter_preis = preis
        b.optionen_liste_split = b.optionen_text.split(" | ") if b.optionen_text else []
        
        restaurant_daten[group_key]['items'].append(b)
        restaurant_daten[group_key]['summe'] += preis
        gesamt_total += preis
        
        if b.lokal_anmeldung or not b.gericht:
            continue  # LOKAL-Anmeldungen in der Zusammenfassung überspringen
        key = f"{b.gericht.name}___{b.optionen_text or ''}___{b.notiz or ''}"
        if key not in restaurant_daten[group_key]['zusammenfassung']:
            restaurant_daten[group_key]['zusammenfassung'][key] = {
                'anzahl': 0, 'name': b.gericht.name, 'preis': preis, 'notiz': b.notiz, 'optionen_liste': b.optionen_liste_split
            }
        restaurant_daten[group_key]['zusammenfassung'][key]['anzahl'] += 1
        
    for d in restaurant_daten.values():
        res = d['restaurant_obj']
        
        unique_besteller = set([item.benutzer for item in d['items']])
        anzahl_besteller = len(unique_besteller)
        
        # 1. Anteil berechnen
        anteil = 0.0
        if res.liefergebuehren > 0 and anzahl_besteller > 0:
            anteil = float(res.liefergebuehren) / anzahl_besteller
            d['anteil_pro_person'] = anteil
            d['summe'] += float(res.liefergebuehren)
            gesamt_total += float(res.liefergebuehren)
        else:
            d['anteil_pro_person'] = 0.0

        # 2. Den Anteil nur an das ERSTE Gericht einer Person heften
        seen_users = set() 
        for item in d['items']:
            item.preis_inkl_lieferung = item.kalkulierter_preis + anteil
            
            if item.benutzer.id not in seen_users:
                item.mein_lieferanteil = anteil  # Hier speichern wir die echten CHF (z.B. 1.50)
                seen_users.add(item.benutzer.id)
            else:
                item.mein_lieferanteil = 0.0     # Alle weiteren Gerichte kriegen 0.0

        # 3. Restliche Berechnungen
        for key, info in d['zusammenfassung'].items():
            info['preis_inkl_lieferung'] = info['preis'] + anteil

        mv = float(d['mindestwert'])
        d['percent'] = min((d['summe'] / mv) * 100, 100) if mv > 0 else 100
        d['reached'] = d['summe'] >= mv
        d['missing'] = max(mv - d['summe'], 0)

    current_art = request.session.get('gewaehlte_art')
    if not current_art:
        current_art = 'LOKAL' 
        
    return render(request, 'lunch_app/uebersicht.html', {
        'restaurant_daten': restaurant_daten, 'gesamt_total': gesamt_total, 
        'ist_zu_spaet': timezone.localtime(timezone.now()).time() > get_deadline(), 
        'user_hat_bestellt': user_hat_bestellt, 'current_art': current_art
    })

@login_required
def toggle_favorit(request, gericht_id):
    if request.method == 'POST':
        g = get_object_or_404(Gericht, id=gericht_id)
        fav = Favorit.objects.filter(benutzer=request.user, gericht=g).first()
        if fav: fav.delete(); status = 'removed'
        else: Favorit.objects.create(benutzer=request.user, gericht=g); status = 'added'
        return JsonResponse({'status': status})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def copy_other_order(request, user_id):
    now = timezone.localtime(timezone.now())
    if now.time() > get_deadline() and not request.user.is_superuser: return redirect('uebersicht')
    target = get_object_or_404(User, id=user_id)
    vorlage = Bestellung.objects.filter(benutzer=target, datum__date=now.date())
    if not vorlage.exists(): return redirect('uebersicht')
    Bestellung.objects.filter(benutzer=request.user, datum__date=now.date()).delete()
    Stimme.objects.update_or_create(benutzer=request.user, datum=now.date(), defaults={'restaurant': vorlage.first().gericht.restaurant, 'art': vorlage.first().art})
    Bestellung.objects.bulk_create([Bestellung(benutzer=request.user, gericht=b.gericht, art=b.art, notiz=b.notiz, optionen_text=b.optionen_text) for b in vorlage])
    return redirect('uebersicht')

@login_required
def vote_restaurant(request, restaurant_id):
    if request.method == 'POST':
        res = get_object_or_404(Restaurant, id=restaurant_id)
        heute = timezone.now().date()
        art = request.session.get('gewaehlte_art', 'LOKAL')

        # Prüfen, ob eine Bestellung existiert
        hat_bestellung = Bestellung.objects.filter(
            benutzer=request.user, 
            datum__date=heute, 
            gericht__restaurant=res
        ).exists()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Wenn bereits bestellt wurde, senden wir einen Fehler zurück!
            if hat_bestellung:
                return JsonResponse({
                    'status': 'blocked', 
                    'message': 'Du hast hier bereits bestellt! Deine Wahl ist fixiert.'
                })

            # Normale Logik (Toggle)
            s = Stimme.objects.filter(benutzer=request.user, datum=heute, restaurant=res).first()
            
            if s:
                s.delete()
                status = 'removed'
            else:
                # Alte Stimme löschen (Single Vote)
                Stimme.objects.filter(benutzer=request.user, datum=heute).delete()
                Stimme.objects.create(benutzer=request.user, datum=heute, restaurant=res, art=art)
                status = 'added'
            
            return JsonResponse({'status': status})

    return redirect('menu', restaurant_id=restaurant_id)

@login_required
def get_voters(request, restaurant_id):
    stimmen = Stimme.objects.filter(restaurant_id=restaurant_id, datum=timezone.now().date(), art=request.session.get('gewaehlte_art', 'LOKAL'))
    return JsonResponse({'voters': [s.benutzer.get_full_name() or s.benutzer.username for s in stimmen]})

@login_required
def claim_order(request, restaurant_id):
    if request.method == 'POST':
        heute = timezone.now().date()
        art = request.POST.get('art')
        
        # Holen oder Erstellen (hier bleibt nutzer leer, wenn neu)
        obj, created = TagesVerantwortlicher.objects.get_or_create(
            restaurant_id=restaurant_id, 
            datum=heute, 
            art=art
        )
        
        # Erst hier übernimmt jemand aktiv die Verantwortung
        if not obj.nutzer:
            obj.nutzer = request.user
            obj.save()
            messages.success(request, "Du hast die Verantwortung übernommen! ✋")
        elif obj.nutzer == request.user:
            messages.info(request, "Du bist schon der Organisator.")
        else:
            messages.error(request, "Jemand anderes ist bereits Organisator.")
            
    return redirect('uebersicht')

@login_required
def set_order_time(request, restaurant_id):
    if request.method == "POST":
        heute = timezone.now().date()
        art = request.POST.get('art') 
        neue_zeit = request.POST.get('bestellzeit')
        
        # 1. Wir suchen, ob für dieses Restaurant heute schon ein Eintrag existiert
        # (Egal ob von einem Fahrer oder einem Organisator erstellt)
        obj = TagesVerantwortlicher.objects.filter(
            restaurant_id=restaurant_id, 
            datum=heute, 
            art=art
        ).first()

        if not obj:
            # Fall A: Es gibt noch gar nichts -> Wir erstellen alles neu
            obj = TagesVerantwortlicher.objects.create(
                restaurant_id=restaurant_id,
                datum=heute,
                art=art,
                nutzer=request.user,
                bestellzeit=neue_zeit
            )
            messages.success(request, "Du hast die Verantwortung übernommen!")
        
        else:
            # Fall B: Es existiert schon ein Eintrag (z.B. durch einen Fahrer)
            
            # Prüfen, ob schon jemand anderes der Chef ist
            if obj.nutzer and obj.nutzer != request.user:
                messages.error(request, "Jemand anderes ist bereits Organisator.")
                return redirect('uebersicht')

            # Wenn noch kein Nutzer eingetragen ist oder du es selbst bist:
            if not obj.bestellung_bestaetigt:
                obj.nutzer = request.user # Hier trägst du dich als Chef ein
                obj.bestellzeit = neue_zeit
                obj.save()
                messages.success(request, "Du hast die Verantwortung übernommen und die Zeit gesetzt!")
            else:
                messages.error(request, "Bestellung ist bereits abgeschlossen.")

    return redirect('uebersicht')

# --- NEUE FUNKTION: Speichert die Zahlungsmethode für die ganze Gruppe ---
@login_required
def set_payment_method(request, restaurant_id):
    if request.method == "POST":
        heute = timezone.now().date()
        art = request.POST.get('art')
        z_art = request.POST.get('zahlungsart')
        org = TagesVerantwortlicher.objects.filter(restaurant_id=restaurant_id, datum=heute, nutzer=request.user, art=art).first()
        
        if org:
            if not org.bestellung_bestaetigt:
                org.zahlungsart = z_art
                org.save()
                messages.success(request, "Zahlungsmethode für die Gruppe gespeichert!")
            else:
                messages.error(request, "Bestellung ist bereits abgeschlossen.")
    return redirect('uebersicht')

@login_required
def unclaim_order(request, restaurant_id):
    if request.method == "POST":
        heute = timezone.now().date()
        art = request.POST.get('art') 
        entry = TagesVerantwortlicher.objects.filter(restaurant_id=restaurant_id, datum=heute, nutzer=request.user, art=art).first()
        if entry:
            if not entry.bestellung_bestaetigt:
                entry.delete()
            else:
                messages.error(request, "Bereits bestätigt.")
    return redirect('uebersicht')

@login_required
def tagesabschluss(request):
    if not request.user.is_superuser:
        messages.error(request, "Keine Berechtigung.")
        return redirect('uebersicht')

    heute = timezone.now().date()
    organizers = TagesVerantwortlicher.objects.filter(datum=heute)
    eintraege_erstellt = 0
    
    for org in organizers:
        if org.art == 'LOKAL':
            continue
        glaeubiger = org.nutzer
        
        alle_besteller_count = Bestellung.objects.filter(datum__date=heute, gericht__restaurant=org.restaurant, art=org.art).values('benutzer').distinct().count()
        liefergebuehr = org.restaurant.liefergebuehren
        anteil_pro_person = float(liefergebuehr) / alle_besteller_count if (liefergebuehr > 0 and alle_besteller_count > 0) else 0.0
        
        bestellungen = Bestellung.objects.filter(
            datum__date=heute, 
            gericht__restaurant=org.restaurant,
            art=org.art 
        ).exclude(benutzer=glaeubiger)
        
        seen_users_debt = set() 
        
        for b in bestellungen:
            preis = float(b.gericht.preis)
            if b.optionen_text:
                matches = re.findall(r'\(\+(\d+(?:\.\d+)?)\)', b.optionen_text)
                for m in matches: 
                    preis += float(m)
            
            # WICHTIG: Den Lieferanteil NUR beim ersten Gericht der Person aufschlagen!
            if b.benutzer.id not in seen_users_debt:
                preis += anteil_pro_person
                seen_users_debt.add(b.benutzer.id)
            z_art = getattr(org, 'zahlungsart', 'SONST')
            Schulden.objects.create(
                glaeubiger=glaeubiger,
                schuldner=b.benutzer,
                betrag=preis,
                datum=heute,
                zahlungsart=z_art
            )
            eintraege_erstellt += 1

    User = get_user_model()
    users_with_email = User.objects.exclude(email__exact='').exclude(email__isnull=True)
    mails_sent = 0

    for user in users_with_email:
        if hasattr(user, 'profile'):
            if not user.profile.notify_debt:
                continue 

        try:
            meine_schulden = Schulden.objects.filter(schuldner=user, erledigt=False)
            mir_schulden = Schulden.objects.filter(glaeubiger=user, erledigt=False)
            
            if not meine_schulden.exists() and not mir_schulden.exists():
                continue

            msg = f"Hallo {user.get_full_name() or user.username},\n\nDer heutige Tag wurde abgeschlossen. Hier ist dein Kontostand von heute:\n\n"
            
            # --- NEU: Schulden pro Person zusammenrechnen (gruppieren) ---
            if meine_schulden.exists():
                msg += "📉 DU SCHULDEST:\n"
                total_s = 0
                
                # Zählt alle Zettel zusammen, die an denselben Gläubiger gehen
                meine_gruppiert = meine_schulden.values('glaeubiger__username', 'glaeubiger__first_name', 'glaeubiger__last_name').annotate(total_betrag=Sum('betrag'))
                
                for s in meine_gruppiert:
                    msg += f"- {s['total_betrag']:.2f} CHF an {s['glaeubiger__first_name']} {s['glaeubiger__last_name']}\n"
                    total_s += s['total_betrag']
                msg += f"-> Total: {total_s:.2f} CHF\n\n"
            
            if mir_schulden.exists():
                msg += "📈 DIR WIRD GESCHULDET:\n"
                total_h = 0
                
                # Zählt alle Zettel zusammen, die vom selben Schuldner kommen
                mir_gruppiert = mir_schulden.values('schuldner__username', 'schuldner__first_name', 'schuldner__last_name').annotate(total_betrag=Sum('betrag'))
                
                for s in mir_gruppiert:
                    msg += f"- {s['schuldner__first_name']} {s['schuldner__last_name']}: {s['total_betrag']:.2f} CHF\n"
                    total_h += s['total_betrag']
                msg += f"-> Total: {total_h:.2f} CHF\n\n"
            
            send_mail(f"💰 Tagesabschluss: Kontostand", msg, None, [user.email], fail_silently=True)
            mails_sent += 1
        except Exception as e:
            print(f"Mail error: {e}")

    # Hier kommen dann deine Löschbefehle, die du schon hast:
    # Bestellung.objects.filter(datum__date=heute).delete()
    # ...

    Bestellung.objects.filter(datum__date=heute).delete()
    TagesVerantwortlicher.objects.filter(datum=heute).delete()
    Stimme.objects.all().delete()
    
    messages.success(request, f"Tag erfolgreich abgeschlossen! {eintraege_erstellt} Buchungen erstellt.")
    return redirect('uebersicht')

@staff_member_required
def system_reset(request):
    Bestellung.objects.all().delete(); Schulden.objects.all().delete(); Stimme.objects.all().delete()
    return redirect('uebersicht')

@login_required
def account_delete(request):
    user = request.user; logout(request); user.delete()
    return redirect('login')

@login_required
def confirm_order_placed(request, restaurant_id):
    heute = timezone.now().date()
    res = get_object_or_404(Restaurant, id=restaurant_id)
    art = request.POST.get('art') 
    
    org = TagesVerantwortlicher.objects.filter(datum=heute, restaurant=res, nutzer=request.user, art=art).first()
    if not org: 
        messages.error(request, "Nicht berechtigt.")
        return redirect('uebersicht')
    
    bestellungen = Bestellung.objects.filter(datum__date=heute, gericht__restaurant=res, art=art)
    
    if res.mindestbestellwert > 0:
        aktueller_wert = 0
        for b in bestellungen:
            p = float(b.gericht.preis)
            if b.optionen_text:
                for m in re.findall(r'\(\+(\d+(?:\.\d+)?)\)', b.optionen_text):
                    p += float(m)
            aktueller_wert += p
            
        if aktueller_wert < res.mindestbestellwert:
            fehlt = res.mindestbestellwert - aktueller_wert
            messages.error(request, f"⚠️ Mindestbestellwert nicht erreicht! Es fehlen noch {fehlt:.2f} CHF.")
            return redirect('uebersicht')
    
    # 1. Besteller ermitteln und Lieferanteil berechnen
    unique_users = set([b.benutzer for b in bestellungen])
    anzahl_besteller = len(unique_users)
    anteil_pro_person = 0.0
    
    if res.liefergebuehren > 0 and anzahl_besteller > 0:
        anteil_pro_person = float(res.liefergebuehren) / anzahl_besteller

    # 2. Basis-Texte für die E-Mail (Zeit, Art, Fahrer, Zahlung)
    t = org.bestellzeit
    if t:
        zeit = t.strftime("%H:%M") if hasattr(t, 'strftime') else str(t)[:5]
        zeit_anzeige = f"um {zeit} Uhr"
    else:
        zeit_anzeige = "Zeit noch offen"
        
    if art == 'LOKAL': 
        sub = "Tisch reserviert"
        txt = f"Tisch bei {res.name} reserviert!"
        lbl = "Treffen"
    elif art == 'TAKEAWAY': 
        sub = "Abholung bestätigt"
        txt = f"Take-Away bei {res.name} bestellt!"
        lbl = "Abholung"
    else:
        sub = "Bestellung aufgegeben"
        txt = f"Essen bei {res.name} bestellt!"
        lbl = "Lieferung"
    
    fahrer_text = ""
    if art == 'LOKAL':
        fahrer_list = [u.first_name or u.username for u in org.fahrer.all()]
        if fahrer_list:
            fahrer_str = ", ".join(fahrer_list)
            fahrer_text = f"\n🚗 Fahrer: {fahrer_str}"
        else:
            fahrer_text = "\n🚗 Fahrer: Noch niemand eingetragen!"

    # 3. INDIVIDUELLE E-MAILS SCHREIBEN UND SENDEN
    for user in unique_users:
        if not user.email:
            continue
        if hasattr(user, 'profile') and not user.profile.notify_order_confirm:
            continue
            
        # Alle Bestellungen DIESES Users filtern
        user_bestellungen = [b for b in bestellungen if b.benutzer == user]
        
        personal_total = 0.0
        kassenbon = "📋 Deine Bestellung:\n"
        
        for item in user_bestellungen:
            preis = float(item.gericht.preis)
            if item.optionen_text:
                for m in re.findall(r'\(\+(\d+(?:\.\d+)?)\)', item.optionen_text):
                    preis += float(m)
            
            personal_total += preis
            
            # Text für Optionen und Notizen aufhübschen
            opt_str = f" | {item.optionen_text}" if item.optionen_text else ""
            notiz_str = f" [Notiz: {item.notiz}]" if item.notiz else ""
            
            kassenbon += f"- {item.gericht.name}{opt_str}{notiz_str}: {preis:.2f} CHF\n"
        
        # Liefergebühr hinzufügen, falls vorhanden
        if anteil_pro_person > 0:
            kassenbon += f"- Anteil Liefergebühr: {anteil_pro_person:.2f} CHF\n"
            personal_total += anteil_pro_person
            
        kassenbon += "-------------------------\n"
        kassenbon += f"Gesamttotal: {personal_total:.2f} CHF\n"

        z_art_text = ""
        if art != 'LOKAL':
            z_art_code = getattr(org, 'zahlungsart', 'SONST')
            organisator_name = org.nutzer.get_full_name() or org.nutzer.username if org.nutzer else "Organisator"
            organisator_nummer = org.nutzer.profile.handynummer if org.nutzer.profile.handynummer else "keine Nummer hinterlegt"
            if z_art_code == 'TWINT_SEND':
                z_art_text = f"✅ TWINT: Bitte überweise {personal_total:.2f} CHF per TWINT an {organisator_name} auf die Nummer {organisator_nummer}"
            elif z_art_code == 'TWINT_REQ':
                z_art_text = f"📲 TWINT: {organisator_name} schickt dir eine TWINT-Anfrage mit dem Betrag: {personal_total:.2f} CHF"
            else:
                z_art_text = "Sonstiges"

        organisator_anzeige = f"\n👤 Verantwortlich: {org.nutzer.get_full_name() or org.nutzer.username}" if org.nutzer else ""
        nachricht = f"Hallo {user.get_full_name() or user.username},\n\n{txt}\n\n{lbl}: {zeit_anzeige}\n\n{organisator_anzeige}\n\n{kassenbon}\nZahlungsmethode: {z_art_text}{fahrer_text}\n\nGuten Appetit!"
        
        # E-Mail nur an diesen einen User schicken
        send_mail(f"✅ {sub}: {res.name}", nachricht, None, [user.email], fail_silently=True)
    
    org.bestellung_bestaetigt = True
    org.save()
    messages.success(request, "Bestätigt und Zusammenfassungen verschickt!")
    return redirect('uebersicht')
    
@login_required
def toggle_show_phone(request):
    if request.method == 'POST':
        request.user.profile.show_phone = True
        request.user.profile.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)
    
@login_required
def schulden_begleichen(request, schulden_id):
    eintrag = get_object_or_404(Schulden, id=schulden_id)
    
    if request.user == eintrag.glaeubiger:
        eintrag.erledigt = True
        eintrag.save()
        messages.success(request, "Zahlung bestätigt.")
    else:
        messages.error(request, "Nur der Empfänger kann den Erhalt bestätigen.")
        
    return redirect('profile')

@login_required
def confirm_daily_payments(request, debtor_id, datum_str):
    schuldner = get_object_or_404(User, id=debtor_id)
    offene_posten = Schulden.objects.filter(
        glaeubiger=request.user,
        schuldner=schuldner,
        datum=datum_str,
        erledigt=False
    )
    
    total = offene_posten.aggregate(Sum('betrag'))['betrag__sum'] or 0
    offene_posten.update(erledigt=True)
    
    datum_huebsch = f"{datum_str[-2:]}.{datum_str[5:7]}.{datum_str[:4]}"
    messages.success(request, f"Zahlung bestätigt! {total:.2f} CHF von {schuldner.get_full_name() or schuldner.username}")
    return redirect('profile')

@login_required
def profile(request):
    UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Profil aktualisiert!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

   # 1. Guthaben (NEU: abwesend_von und abwesend_bis hinzugefügt)
    raw_guthaben = Schulden.objects.filter(
        glaeubiger=request.user, erledigt=False
    ).values(
        'schuldner', 'schuldner__username', 'schuldner__first_name', 'schuldner__last_name', 'datum', 'zahlungsart', 'schuldner__profile__handynummer', 'schuldner__profile__show_phone',
        'schuldner__profile__abwesend_von', 'schuldner__profile__abwesend_bis'
    ).annotate(total_betrag=Sum('betrag'), anzahl=Count('id')).order_by('-datum', 'schuldner__username')

    # 2. Schulden (NEU: abwesend_von und abwesend_bis hinzugefügt)
    raw_schulden = Schulden.objects.filter(
        schuldner=request.user, erledigt=False
    ).values(
        'glaeubiger', 'glaeubiger__username', 'glaeubiger__first_name', 'glaeubiger__last_name', 'glaeubiger__profile__handynummer', 'glaeubiger__profile__show_phone', 'datum', 'zahlungsart',
        'glaeubiger__profile__abwesend_von', 'glaeubiger__profile__abwesend_bis'
    ).annotate(total_betrag=Sum('betrag'), anzahl=Count('id')).order_by('-datum', 'glaeubiger__username')

    # --- NEU: Urlaubs-Check in Echtzeit ---
    heute = timezone.now().date()
    
    guthaben_liste = list(raw_guthaben)
    for item in guthaben_liste:
        von = item.get('schuldner__profile__abwesend_von')
        bis = item.get('schuldner__profile__abwesend_bis')
        item['im_urlaub'] = True if (von and bis and von <= heute <= bis) else False

    schulden_liste = list(raw_schulden)
    for item in schulden_liste:
        von = item.get('glaeubiger__profile__abwesend_von')
        bis = item.get('glaeubiger__profile__abwesend_bis')
        item['im_urlaub'] = True if (von and bis and von <= heute <= bis) else False
    # --------------------------------------

    total_guthaben = Schulden.objects.filter(glaeubiger=request.user, erledigt=False).aggregate(Sum('betrag'))['betrag__sum'] or 0
    total_schulden = Schulden.objects.filter(schuldner=request.user, erledigt=False).aggregate(Sum('betrag'))['betrag__sum'] or 0

    context = {
        'u_form': u_form,
        'p_form': p_form,
        # WICHTIG: Hier übergeben wir jetzt die bearbeiteten Listen!
        'guthaben_liste': guthaben_liste, 
        'schulden_liste': schulden_liste, 
        'total_guthaben': total_guthaben,
        'total_schulden': total_schulden,
    }

    return render(request, 'lunch_app/profile.html', context)

@login_required
def change_order_type(request, restaurant_id, art_typ):
    if art_typ in ['LOKAL', 'TAKEAWAY', 'DELIVERY']:
        request.session['gewaehlte_art'] = art_typ
    
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if restaurant.scraper_modul:
        try:
            if hasattr(scrapers, restaurant.scraper_modul):
                scraper_func = getattr(scrapers, restaurant.scraper_modul)
                scraper_func(restaurant)
        except Exception as e:
            print(f"❌ Scraper Fehler in View: {e}")

    return redirect('menu', restaurant_id=restaurant_id)

@login_required
def feedback(request):
    if not request.user.email:
        messages.warning(request, "Bitte hinterlege zuerst eine E-Mail-Adresse in deinem Profil, damit wir dir antworten können.")
        return redirect('profile')

    if request.method == 'POST':
        betreff = request.POST.get('betreff', '').strip()
        nachricht = request.POST.get('nachricht', '').strip()

        if betreff and nachricht:
            deine_admin_email = settings.ADMIN_FEEDBACK_EMAIL
            subject = f"💡 Neues App-Feedback: {betreff}"
            message = f"Neues Feedback von: {request.user.get_full_name() or request.user.username} ({request.user.email})\n\nNachricht:\n{nachricht}"

            try:
                send_mail(subject, message, None, [deine_admin_email], fail_silently=False)
                messages.success(request, "Vielen Dank für dein Feedback! Es wurde erfolgreich gesendet.")
                return redirect('home')
            except Exception as e:
                messages.error(request, f"Fehler beim Senden: {e}")
        else:
            messages.error(request, "Bitte fülle beide Felder aus.")

    return render(request, 'lunch_app/feedback.html')
    

def trigger_all_scrapers(request):
    restaurants = Restaurant.objects.all()
    for res in restaurants:
        if res.scraper_modul:
            try:
                if hasattr(scrapers, res.scraper_modul):
                    getattr(scrapers, res.scraper_modul)(res)
            except Exception as e:
                print(f"Fehler bei Scraper {res.name}: {e}")
                
    return JsonResponse({'status': 'ok'})
    
    
@login_required
def toggle_driver(request, restaurant_id):
    if request.method == 'POST':
        heute = timezone.now().date()
        res = get_object_or_404(Restaurant, id=restaurant_id)
        art = request.POST.get('art')

        # Wir erstellen den Eintrag OHNE einen Nutzer festzulegen
        obj, created = TagesVerantwortlicher.objects.get_or_create(
            restaurant=res,
            datum=heute,
            art=art
        )

        if request.user in obj.fahrer.all():
            obj.fahrer.remove(request.user)
            messages.info(request, "Du fährst doch nicht.")
        else:
            obj.fahrer.add(request.user)
            messages.success(request, "Du bist als Fahrer eingetragen! 🚗")

    return redirect('uebersicht')
    
    
def set_active_standort(request, standort_id):
    try:
        # 1. Den gewünschten Standort aus der Datenbank holen
        neuer_standort = Standort.objects.get(id=standort_id)
    except Standort.DoesNotExist:
        return redirect('/') # Sicherheits-Fallback

    # 2. Den Standort für das schnelle Umschalten in der Session merken
    request.session['aktiver_standort_id'] = neuer_standort.id

    # 3. WICHTIG: Den neuen Standort DAUERHAFT in der Datenbank speichern!
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        request.user.profile.standard_standort = neuer_standort
        request.user.profile.save()

    # 4. Den User dorthin zurückschicken, wo er gerade herkam
    next_url = request.META.get('HTTP_REFERER', '/')
    return redirect('home')
