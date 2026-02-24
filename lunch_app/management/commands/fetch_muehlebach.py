from django.core.management.base import BaseCommand
from lunch_app.models import Restaurant, Gericht
from django.utils import timezone
from curl_cffi import requests 
from bs4 import BeautifulSoup
import re
import io
from pypdf import PdfReader

class Command(BaseCommand):
    help = 'Holt das Tagesmenü vom Landgasthof Mühlebach (Block-Parsing für mehrzeilige PDFs)'

    def handle(self, *args, **kwargs):
        url = "https://www.landgasthof-muehlebach.ch/speisen/"
        base_url = "https://www.landgasthof-muehlebach.ch"

        try:
            restaurant = Restaurant.objects.get(name__icontains="Mühlebach")
        except Restaurant.DoesNotExist:
            self.stdout.write(self.style.ERROR('Restaurant "Mühlebach" nicht gefunden!'))
            return

        # Alte Menüs löschen
        Gericht.objects.filter(restaurant=restaurant, kategorie="Tagesmenü").delete()

        # 1. SEITE LADEN & LINK FINDEN
        try:
            response = requests.get(url, impersonate="chrome", timeout=20)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Verbindungsfehler: {e}'))
            return

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Suche Link
        link_by_text = soup.find('a', string=re.compile(r'Menü|Wochenhit', re.IGNORECASE))
        link_by_href = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        pdf_link = None
        if link_by_text and 'href' in link_by_text.attrs:
            pdf_link = link_by_text['href']
        elif link_by_href:
            pdf_link = link_by_href['href']
            
        if not pdf_link:
            self.stdout.write(self.style.WARNING('Kein PDF-Link gefunden.'))
            return

        if not pdf_link.startswith('http'):
            clean_link = pdf_link.lstrip('/')
            pdf_url = f"{base_url}/{clean_link}"
        else:
            pdf_url = pdf_link

        self.stdout.write(f"PDF gefunden: {pdf_url}")

        # 2. PDF LADEN
        try:
            pdf_response = requests.get(pdf_url, impersonate="chrome", timeout=20)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'PDF Download Fehler: {e}'))
            return

        # 3. TEXT ANALYSE (BLOCK-LOGIK)
        try:
            f = io.BytesIO(pdf_response.content)
            reader = PdfReader(f)
            
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"
            
            lines = full_text.split('\n')
            found_count = 0
            
            # WICHTIG: Das Regex sucht jetzt explizit nach "Fr." oder "CHF"
            # Damit wird das Datum "06.02" ignoriert!
            # Findet: "Fr. 19.50" oder "Fr 19.50"
            price_pattern = re.compile(r'(?:Fr\.?|CHF)\s*(\d{1,2}[\.,]\d{2})', re.IGNORECASE)

            # Buffer speichert die Zeilen VOR dem Preis
            text_buffer = []

            for line in lines:
                line = line.strip()
                if not line: continue # Leere Zeilen ignorieren

                # Check: Ist diese Zeile ein Preis?
                price_match = price_pattern.search(line)

                if price_match:
                    # JA, Preis gefunden!
                    price_str = price_match.group(1).replace(',', '.')
                    try:
                        price = float(price_str)
                    except:
                        text_buffer = [] # Reset bei Fehler
                        continue

                    # Jetzt bauen wir den Namen aus den Zeilen DAVOR (im Buffer)
                    # Wir nehmen die letzten 2-4 Zeilen aus dem Buffer, das sind meist Name + Beilage + "Menu X"
                    if text_buffer:
                        # Verbinde die gesammelten Zeilen mit Leerzeichen
                        raw_desc = " ".join(text_buffer[-3:]) # Nimm max die letzten 3 Zeilen
                        
                        # Bereinigen
                        clean_desc = raw_desc.replace("Menu", "Menü")
                        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                        
                        # Formatierung: Mühlebach Menü X: ...
                        dish_name = f"Mühlebach: {clean_desc}"

                        if len(clean_desc) > 5:
                            Gericht.objects.create(
                                restaurant=restaurant,
                                name=dish_name[:200],
                                preis=price,
                                kategorie="Tagesmenü",
                                reihenfolge=1
                            )
                            found_count += 1
                            print(f"Importiert: {dish_name} | {price}")
                    
                    # Buffer leeren für das nächste Gericht
                    text_buffer = []
                
                else:
                    # NEIN, kein Preis.
                    # Zeile zum Buffer hinzufügen (wird vielleicht Teil des nächsten Gerichts)
                    # Wir ignorieren Zeilen wie "Suppe & Salat", wenn sie zu weit oben stehen
                    # Datum und allgemeine Infos ignorieren wir über simple Filter
                    if "Freitag," in line or "Suppe & Salat" in line or "Portion bestellbar" in line:
                        continue 
                        
                    text_buffer.append(line)

            if found_count > 0:
                self.stdout.write(self.style.SUCCESS(f'{found_count} Menüs geladen.'))
            else:
                self.stdout.write(self.style.WARNING('Keine Menüs erkannt.'))
                # Debug Ausgabe falls leer
                # print(full_text)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Fehler beim Parsen: {e}'))
