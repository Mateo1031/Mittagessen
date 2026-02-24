from django.core.management.base import BaseCommand
from lunch_app.models import Restaurant, Gericht
import requests
from bs4 import BeautifulSoup
import re
import os

class Command(BaseCommand):
    help = 'Holt das Tagesmenü vom Sportcenter Leuholz (mit Browser-Tarnung)'

    def handle(self, *args, **kwargs):
        url = "https://sportcenter-leuholz.ch/speise-und-getraenkekarte#inhalt"
        
        # --- 1. TARNKAPPE (User-Agent) ---
        # Damit denken Server, wir seien ein echter Chrome-Browser auf Windows
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }

        try:
            restaurant = Restaurant.objects.get(name__icontains="Leuholz")
        except Restaurant.DoesNotExist:
            self.stdout.write(self.style.ERROR('Restaurant "Leuholz" nicht gefunden!'))
            return

        # Alte Menüs löschen
        Gericht.objects.filter(restaurant=restaurant, kategorie="Tagesmenü").delete()

        try:
            # Request MIT Headern senden
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Verbindungsfehler: {e}'))
            return

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- 2. FEHLERSUCHE (DEBUGGING) ---
        # Suchen nach der Tabelle mit Klasse 'striped'
        table = soup.find('table', class_='striped')
        
        if not table:
            # Versuche, irgendeine Tabelle zu finden (falls Klasse geändert wurde)
            table = soup.find('table')
        
        if not table:
            # Wenn immer noch nichts gefunden wurde -> HTML speichern zur Analyse
            debug_file = "leuholz_debug.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            
            self.stdout.write(self.style.WARNING(f'Keine Tabelle gefunden! HTML wurde zur Analyse in "{debug_file}" gespeichert.'))
            self.stdout.write("Bitte prüfe die Datei oder öffne sie im Browser.")
            return

        found_count = 0
        current_category = "Tagesmenü"

        # Zeilen durchgehen
        for row in table.find_all('tr'):
            
            # A. KATEGORIE
            header = row.find('th')
            if header:
                # Text holen, egal ob im h3, strong oder direkt
                cat_text = header.get_text(strip=True)
                if cat_text:
                    current_category = cat_text.title()
                continue 

            # B. GERICHT
            cols = row.find_all('td')
            if len(cols) >= 2:
                desc_td = cols[0]
                price_td = cols[1]

                # Preis
                price_text = price_td.get_text(strip=True)
                price = 0.00
                price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
                if price_match:
                    try:
                        price = float(price_match.group(1).replace(',', '.'))
                    except ValueError:
                        price = 0.00

                # Name
                # Wir suchen nach fetten Texten (<b> oder <strong>) als Hauptnamen
                bold_tag = desc_td.find(['b', 'strong'])
                
                full_desc = desc_td.get_text(separator=" ", strip=True)
                
                # Bereinigung von Standard-Phrasen
                clean_desc = full_desc.replace("Menusalat oder Suppe", "")
                clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

                if bold_tag:
                    main_dish = bold_tag.get_text(strip=True)
                    # Wenn der ganze Text fast nur aus dem fetten Teil besteht, nehmen wir das
                    if len(clean_desc) < len(main_dish) + 5:
                         dish_name = f"{current_category}: {main_dish}"
                    else:
                         dish_name = f"{current_category}: {clean_desc}"
                else:
                    dish_name = f"{current_category}: {clean_desc}"

                if len(dish_name) > 5:
                    Gericht.objects.create(
                        restaurant=restaurant,
                        name=dish_name[:200],
                        preis=price,
                        kategorie="Tagesmenü",
                        reihenfolge=1
                    )
                    found_count += 1
                    print(f"Importiert: {dish_name} | {price}")

        if found_count > 0:
            self.stdout.write(self.style.SUCCESS(f'{found_count} Menüs geladen.'))
        else:
            self.stdout.write(self.style.WARNING('Tabelle gefunden, aber keine Gerichte extrahiert (Struktur anders?).'))
