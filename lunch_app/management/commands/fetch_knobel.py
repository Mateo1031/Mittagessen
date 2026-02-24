from django.core.management.base import BaseCommand
from lunch_app.models import Restaurant, Gericht
import requests
from bs4 import BeautifulSoup
import re

class Command(BaseCommand):
    help = 'Holt das Tagesmenü vom Knobel mit verbesserter Texterkennung'

    def handle(self, *args, **kwargs):
        url = "https://www.baeckerei-knobel.ch/cmspage/menue/Altendorf/heute"
        
        try:
            restaurant = Restaurant.objects.get(name__icontains="Knobel")
        except Restaurant.DoesNotExist:
            self.stdout.write(self.style.ERROR('Restaurant "Knobel" nicht gefunden!'))
            return

        # Alte Tagesmenüs löschen
        Gericht.objects.filter(restaurant=restaurant, kategorie="Tagesmenü").delete()

        try:
            response = requests.get(url)
            response.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Fehler beim Laden: {e}'))
            return

        soup = BeautifulSoup(response.content, 'html.parser')
        cards = soup.select('.card-block')
        
        found_count = 0

        for card in cards:
            # 1. TITEL SUCHEN
            title_tag = card.find(class_='card-title')
            if not title_tag: continue
            
            title_text = title_tag.get_text(strip=True)

            # --- WICHTIGE ÄNDERUNG HIER ---
            # Wir entfernen den Titel aus dem HTML-Objekt der Karte.
            # So können wir danach einfach den "ganzen Rest" als Text holen.
            title_tag.extract() 

            # Jetzt holen wir ALLES was noch übrig ist (Beschreibung, Preise, Zusatzinfos)
            # separator=" " sorgt dafür, dass <br> oder <p> durch Leerzeichen ersetzt werden
            full_text = card.get_text(separator=" ", strip=True)

            # 

            # 2. PREIS EXTRAHIEREN
            # Wir suchen nach Preisen (z.B. 19.50 oder 19.-)
            # Wir nehmen den ersten gefundenen Preis als Hauptpreis (meistens der Menüpreis, nicht Takeaway)
            price = 0.00
            # Regex sucht: Ziffern.Ziffern ODER Ziffern.- (ignoriert den Take-away Preis meistens, da er später kommt)
            # Knobel listet meist zuerst den normalen Preis, dann den Take-Away Preis.
            all_prices = re.findall(r'(\d+[\.,]\d{2})|(\d+)\.-', full_text)
            
            if all_prices:
                # Das erste Match nehmen
                first_match = all_prices[0]
                price_str = first_match[0] if first_match[0] else first_match[1]
                price = float(price_str.replace(',', '.'))

            # 3. TEXT BEREINIGEN
            clean_name = full_text

            # Entferne das Wort "Take-away" und alles was danach kommt bis zum Ende einer Preisangabe
            # Das ist etwas aggressiver, um "Take-away CHF 16.50" komplett loszuwerden
            clean_name = re.sub(r'Take-away\s*CHF\s*\d+[\.,]\d{2}', '', clean_name, flags=re.IGNORECASE)
            
            # Entferne einzelne Preise "CHF 19.50" oder nur "19.50"
            clean_name = re.sub(r'CHF\s*\d+[\.,]\d{2}', '', clean_name)
            clean_name = re.sub(r'\d+[\.,]\d{2}', '', clean_name)
            clean_name = re.sub(r'\d+\.-', '', clean_name)

            # Entferne "Suppe oder Salat" (Optional, falls du das nicht im Text willst)
            # clean_name = clean_name.replace("Suppe oder Salat", "")

            # Bereinige doppelte Leerzeichen und Zeilenumbrüche
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()
            
            # Entferne Reste wie "CHF" am Ende
            clean_name = re.sub(r'(?i)Take-away|CHF$', '', clean_name).strip()

            dish_name = f"{title_text}: {clean_name}"

            # 4. FALLBACKS (falls Preis nicht erkannt wurde)
            if price == 0.00:
                if "Tagessuppe" in title_text: price = 8.50
                elif "Menüsalat" in title_text: price = 9.50
                elif "Klassiker" in title_text: price = 24.50
                elif "Gulasch" in full_text or "Monatssuppe" in title_text: price = 10.50
                elif "Snack" in title_text: price = 9.00

            # Speichern
            if clean_name and len(clean_name) > 2: 
                Gericht.objects.create(
                    restaurant=restaurant,
                    name=dish_name[:200], 
                    preis=price,
                    kategorie="Tagesmenü",
                    reihenfolge=1
                )
                found_count += 1
                self.stdout.write(f"Importiert: {dish_name} | {price} CHF")

        self.stdout.write(self.style.SUCCESS(f'Fertig! {found_count} Menüs für Knobel geladen.'))
