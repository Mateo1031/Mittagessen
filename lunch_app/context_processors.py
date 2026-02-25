import datetime
from .models import Standort, SystemEinstellungen

def standort_processor(request):
    session_key = 'aktiver_standort_id' 
    standort_id = request.session.get(session_key)
    aktueller_standort = None

    if request.user.is_authenticated:
        # 1. Profil-Check: Füllt die leere Session mit dem Wunsch-Standort
        if not standort_id:
            if hasattr(request.user, 'profile') and request.user.profile.standard_standort:
                standort_id = request.user.profile.standard_standort.id
                request.session[session_key] = standort_id

    # 2. Standort-Objekt aus der Datenbank holen
    if standort_id:
        try:
            aktueller_standort = Standort.objects.get(id=standort_id)
        except Standort.DoesNotExist:
            pass # Wenn er gelöscht wurde, greift der Fallback

    # 3. Fallback für die Anzeige (z.B. auf der Login-Seite)
    # WICHTIG: Wir speichern diesen Fallback NICHT mehr in die Session!
    if not aktueller_standort:
        aktueller_standort = Standort.objects.first()

    return {
        'aktueller_standort': aktueller_standort,
        'alle_standorte': Standort.objects.all(),
    }

def globale_einstellungen(request):
    try:
        einstellungen = SystemEinstellungen.objects.first()
        deadline = einstellungen.bestellschluss if einstellungen else datetime.time(11, 0)
    except Exception:
        # Falls die Datenbank noch nicht bereit ist
        deadline = datetime.time(11, 0)

    # Diese Werte sind nun in JEDER HTML-Datei verfügbar
    return {
        'system_deadline_stunde': deadline.hour,
        'system_deadline_minute': deadline.minute,
        'system_deadline_formatiert': deadline.strftime('%H:%M'),
    }