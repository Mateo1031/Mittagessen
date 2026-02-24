import schedule
import time
import os

def benachrichtigung_senden():
    print("⏰ Es ist 10:00 Uhr! Sende Benachrichtigungen...")
    # Hier rufst du einfach deinen Django-Befehl auf:
    os.system("python manage.py <DEIN_BEFEHL_HIER>")

# Montags bis Freitags um 10:00 Uhr ausführen
schedule.every().monday.at("10:00").do(benachrichtigung_senden)
schedule.every().tuesday.at("10:00").do(benachrichtigung_senden)
schedule.every().wednesday.at("10:00").do(benachrichtigung_senden)
schedule.every().thursday.at("10:00").do(benachrichtigung_senden)
schedule.every().friday.at("10:00").do(benachrichtigung_senden)

print("Wecker gestartet. Warte auf 10:00 Uhr...")

# Endlosschleife, die jede Minute prüft, ob es Zeit ist
while True:
    schedule.run_pending()
    time.sleep(60)
