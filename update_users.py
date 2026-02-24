import os
import csv
import django

# 1. Django-Umgebung laden (WICHTIG für externe Skripte)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mittagessen.settings') 
django.setup()

from django.contrib.auth.models import User
from lunch_app.models import UserProfile, Standort

def import_or_update_users(csv_datei_pfad):
    print("🚀 Starte Benutzer-Update...")
    
    aktualisiert = 0
    neu_erstellt = 0

    try:
        # utf-8-sig entfernt das unsichtbare Zeichen, das Excel manchmal an den Dateianfang setzt
        with open(csv_datei_pfad, mode='r', encoding='utf-8-sig') as file:
            
            # HIER IST DIE ÄNDERUNG: delimiter=';' sagt Python, dass die Spalten durch Semikolon getrennt sind
            reader = csv.DictReader(file, delimiter=';')
            
            for row in reader:
                # Hole den Username (Strip entfernt versehentliche Leerzeichen am Anfang/Ende)
                username = row.get('username')
                if not username:
                    continue 

                username = username.strip()

                # 1. User holen oder neu erstellen
                user, created = User.objects.get_or_create(username=username)
                
                # 2. Basis-Daten aktualisieren
                if row.get('first_name'): user.first_name = row['first_name'].strip()
                if row.get('last_name'): user.last_name = row['last_name'].strip()
                if row.get('email'): user.email = row['email'].strip()
                user.save()

                # 3. Profil holen
                profile, _ = UserProfile.objects.get_or_create(user=user)

                # 4. Handynummer aktualisieren
                if row.get('handynummer'):
                    profile.handynummer = row['handynummer'].strip()

                # 5. DEN STANDORT AKTUALISIEREN
                standort_name = row.get('standort')
                if standort_name:
                    standort_name = standort_name.strip()
                    # Wir suchen den Standort in der DB (ignoriert Groß-/Kleinschreibung)
                    standort_obj = Standort.objects.filter(name__iexact=standort_name).first()
                    
                    if standort_obj:
                        profile.standard_standort = standort_obj
                    else:
                        print(f"⚠️ Warnung bei '{username}': Standort '{standort_name}' existiert nicht im Admin-Bereich!")
                
                profile.save()

                # Für die Statistik
                if created:
                    print(f"✅ Neu erstellt: {username}")
                    neu_erstellt += 1
                else:
                    print(f"🔄 Aktualisiert: {username}")
                    aktualisiert += 1

    except FileNotFoundError:
        print(f"❌ Fehler: Die Datei '{csv_datei_pfad}' wurde nicht gefunden.")
    except Exception as e:
        print(f"❌ Ein unerwarteter Fehler ist aufgetreten: {e}")

    # Zusammenfassung
    print("\n" + "="*30)
    print("📊 ZUSAMMENFASSUNG")
    print("="*30)
    print(f"Neue User:     {neu_erstellt}")
    print(f"Aktualisiert:  {aktualisiert}")
    print("="*30)

if __name__ == '__main__':
    import_or_update_users('users.csv')
