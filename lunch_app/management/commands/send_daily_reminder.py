import os
import shutil
import time
from datetime import datetime
import schedule  # <-- NEU: Das Uhrwerk

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from lunch_app.models import Bestellung

def run_full_weekly_backup():
    """Erstellt ein ZIP-Archiv des gesamten Projektordners."""
    source_dir = '/app'
    # Zielordner im Container
    target_dir = '/app/backups/full_backups'
    os.makedirs(target_dir, exist_ok=True)

    # Dateiname mit Jahr und Kalenderwoche
    timestamp = datetime.now().strftime('%Y_KW%V')
    backup_path = os.path.join(target_dir, f'full_project_backup_{timestamp}')

    try:
        print("📦 Starte wöchentliches Voll-Backup...")
        # Erstellt eine .zip Datei vom gesamten source_dir
        shutil.make_archive(backup_path, 'zip', source_dir)
        print(f"✅ Voll-Backup erfolgreich erstellt: {backup_path}.zip")

    except Exception as e:
        print(f"❌ Fehler beim Voll-Backup: {e}")

def run_database_backup():
    """Kopiert die SQLite-Datenbank nachts in einen Backup-Ordner."""
    # Backup-Ordner im Projektverzeichnis erstellen
    backup_dir = '/app/backups/db_backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Dateinamen mit Zeitstempel generieren
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    backup_file = os.path.join(backup_dir, f'db_backup_{timestamp}.sqlite3')
    
    # Den Pfad zur aktuellen Datenbank holen
    db_path = settings.DATABASES['default']['NAME']
    
    try:
        shutil.copy2(db_path, backup_file)
        print(f"✅ [15:00] Backup erfolgreich erstellt: {backup_file}")
        
        # Aufräumen: Backups löschen, die älter als 14 Tage sind
        jetzt = time.time()
        for datei in os.listdir(backup_dir):
            datei_pfad = os.path.join(backup_dir, datei)
            # 14 Tage = 1.209.600 Sekunden
            if os.stat(datei_pfad).st_mtime < jetzt - 14 * 86400:
                os.remove(datei_pfad)
                print(f"🗑️ Altes Backup gelöscht: {datei}")
                
    except Exception as e:
        print(f"❌ Fehler beim Backup: {e}")


class Command(BaseCommand):
    help = 'Läuft permanent im Hintergrund und führt geplante Tasks (Mails & Backup) aus.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starte Hintergrund-Scheduler..."))
        self.stdout.write("Warte auf 10:00 Uhr (Mails) und 15:00 Uhr (Backup).")
        
        # 1. Die Termine in den Kalender eintragen
        schedule.every().day.at("10:00").do(self.check_and_send_mails)
        schedule.every().day.at("15:00").do(run_database_backup)
        schedule.every().friday.at("16:00").do(run_full_weekly_backup)
        
        # 2. Die Endlosschleife (Der Wecker tickt)
        while True:
            schedule.run_pending()
            time.sleep(30)  # Schläft 60 Sekunden, prüft dann wieder die Uhrzeit

    def check_and_send_mails(self):
        """Das ist dein alter handle-Code, jetzt in einer eigenen Funktion."""
        self.stdout.write("Prüfe, ob E-Mails versendet werden müssen...")
        
        heute = timezone.now().date()
        if heute.isoweekday() >= 6:
            self.stdout.write("Wochenende - keine Mails.")
            return

        User = get_user_model()
        users_to_remind = User.objects.filter(profile__notify_daily=True)

        count = 0
        for user in users_to_remind:
            profile = getattr(user, 'profile', None)
            if profile and profile.abwesend_von and profile.abwesend_bis:
                # Wenn heute zwischen (oder genau auf) den Daten liegt
                if profile.abwesend_von <= heute <= profile.abwesend_bis:
                    print(f"Skipping {user.username} (im Urlaub)")
                    continue
            hat_bestellt = Bestellung.objects.filter(benutzer=user, datum__date=heute).exists()
            if not hat_bestellt:
                try:
                    self.send_reminder_mail(user)
                    count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Fehler bei {user.username}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Fertig! {count} Erinnerungen versendet."))

    def send_reminder_mail(self, user):
        if not user.email:
            return

        subject = "🍽️ Hunger? Zeit für Mittagessen!"
        message = (
            f"Hallo {user.username},\n\n"
            f"Es ist 10:00 Uhr und du hast noch nichts für heute bestellt.\n"
            f"Schnell, bevor die Deadline abläuft!\n\n"
            f"Hier geht's zur Auswahl:\n"
            f"http://mittagessen.adeon.ch\n\n"
            f"(Du kannst diese Erinnerung in deinem Profil deaktivieren.)"
        )

        send_mail(
            subject,
            message,
            None, 
            [user.email],
            fail_silently=False
        )
