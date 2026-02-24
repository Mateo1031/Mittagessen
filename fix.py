from django.db import connection

try:
    with connection.cursor() as cursor:
        # Fügt die fehlende Spalte direkt in die Datenbank-Tabelle ein
        cursor.execute("ALTER TABLE lunch_app_userprofile ADD COLUMN abwesend_von date NULL;")
    print("✅ Urlaubs-Spalte erfolgreich hinzugefügt!")
except Exception as e:
    print(f"Fehler (vielleicht existiert sie schon?): {e}")