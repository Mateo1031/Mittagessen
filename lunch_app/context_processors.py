import datetime
from .models import Standort, SystemEinstellungen

def standort_processor(request):
    # Schickt alle Standorte automatisch an jedes HTML-Template
    return {
        'alle_standorte': Standort.objects.all()
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