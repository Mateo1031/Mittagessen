import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from django.utils import timezone
import datetime
from django.db.models import Q
import sys
import re
import io
from pypdf import PdfReader
from .models import Gericht, Restaurant

# ==========================================
# HILFSMITTEL: DATUM FINDEN (Robust)
# ==========================================
def extract_date(text):
    """
    Sucht nach einem Datum im Text.
    Erkennt: 10.02.2026, 10.2., 10. Februar, 10. Feb etc.
    """
    if not text: return None

    # Monate als Text (inkl. Abkürzungen)
    months = r"(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)"
    
    # Regex sucht nach Tag + Monat (Zahl oder Text)
    pattern = re.compile(r'(\d{1,2}\.?\s*(?:' + months + r'|\d{1,2}\.)(?:\s*\d{2,4})?)', re.IGNORECASE)
    
    match = pattern.search(text)
    if match:
        # Gefundenes Datum bereinigen (doppelte Leerzeichen weg)
        return re.sub(r'\s+', ' ', match.group(1).strip())
    return None


# ==========================================
# HILFSFUNKTION: SPEICHERN
# ==========================================
def save_if_changed(restaurant, new_dishes_list, category_name="Tagesmenü"):
    existing_dishes = Gericht.objects.filter(restaurant=restaurant)
    
    # Alle Kandidaten finden (Tagesmenü, Menu, etc.)
    candidates = existing_dishes.filter(
        Q(kategorie__icontains="Tages") | Q(kategorie__icontains="Menu")
    )

    # 1. DATUM-CHECK (Das Wichtigste!)
    # Wir prüfen, ob es schon Gerichte mit GENAU diesem Kategorie-Namen (inkl. Datum) gibt
    current_category_exists = candidates.filter(kategorie=category_name).exists()

    # 2. INHALT-CHECK
    existing_set = set(f"{d.name.strip()}|{float(d.preis)}" for d in candidates)
    new_set = set(f"{item['name'].strip()}|{float(item['preis'])}" for item in new_dishes_list)

    # NUR wenn das Datum stimmt UND der Inhalt gleich ist -> Nichts tun
    if current_category_exists and existing_set == new_set:
        print(f"💤 {restaurant.name}: Alles aktuell.")
        return False 
    
    # Sobald das Datum anders ist ODER der Inhalt sich geändert hat -> Update!
    print(f"🔄 {restaurant.name}: Update auf {category_name}")
    candidates.delete() 
    for item in new_dishes_list:
        Gericht.objects.create(
            restaurant=restaurant,
            name=item['name'],
            preis=item['preis'],
            kategorie=category_name, # Hier wird das Datum gespeichert
            reihenfolge=1
        )
    return True

# ==========================================
# 1. SCRAPER: KNOBEL
# ==========================================
def scrape_knobel(restaurant):
    url = "https://www.baeckerei-knobel.ch/cmspage/menue/Altendorf/heute"
    
    try:
        response = requests.get(url, timeout=10)
    except Exception: return False

    soup = BeautifulSoup(response.content, 'html.parser')
    
    full_page_text = soup.get_text(separator=" ")
    header_text = full_page_text[:1000] 
    found_date = extract_date(header_text)
    
    cat_name = f"Tagesmenü {found_date}" if found_date else "Tagesmenü"

    cards = soup.select('.card-block')
    found_dishes = []

    for card in cards:
        title_tag = card.find(class_='card-title')
        if not title_tag: continue
        title_text = title_tag.get_text(strip=True)
        title_tag.extract() 

        full_text = card.get_text(separator=" ", strip=True)
        
        price = 0.00
        all_prices = re.findall(r'(\d+[\.,]\d{2})|(\d+)\.-', full_text)
        if all_prices:
            m = all_prices[0]
            price = float((m[0] if m[0] else m[1]).replace(',', '.'))

        clean = full_text
        clean = re.sub(r'Take-away\s*CHF\s*\d+[\.,]\d{2}', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'CHF\s*\d+[\.,]\d{2}', '', clean)
        clean = re.sub(r'\d+[\.,]\d{2}', '', clean)
        clean = re.sub(r'\d+\.-', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = re.sub(r'(?i)Take-away|CHF$', '', clean).strip()

        dish_name = f"{title_text}: {clean}"

        if price == 0.00:
            if "Tagessuppe" in title_text: price = 8.50
            elif "Menüsalat" in title_text: price = 9.50
            elif "Klassiker" in title_text: price = 24.50
            elif "Gulasch" in full_text: price = 10.50
            elif "Snack" in title_text: price = 9.00

        if clean and len(clean) > 2:
            found_dishes.append({'name': dish_name[:200], 'preis': price})

    return save_if_changed(restaurant, found_dishes, cat_name)


# ==========================================
# 2. SCRAPER: LEUHOLZ
# ==========================================
def scrape_leuholz(restaurant):
    url = "https://sportcenter-leuholz.ch/speise-und-getraenkekarte#inhalt"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
    except Exception: return False

    soup = BeautifulSoup(response.content, 'html.parser')
    
    content_div = soup.find(id='inhalt') or soup.body
    text_sample = content_div.get_text(separator=" ")[:500]
    found_date = extract_date(text_sample)
    
    cat_name = f"Tagesmenü {found_date}" if found_date else "Tagesmenü"

    table = soup.find('table', class_='striped') or soup.find('table')
    if not table: return False

    found_dishes = []
    current_cat_suffix = ""

    for row in table.find_all('tr'):
        header = row.find('th')
        if header:
            cat = header.get_text(strip=True)
            if cat: current_cat_suffix = f" ({cat.title()})"
            continue 

        cols = row.find_all('td')
        if len(cols) >= 2:
            desc_td, price_td = cols[0], cols[1]
            price_text = price_td.get_text(strip=True)
            price = 0.00
            m = re.search(r'(\d+[\.,]\d{2})', price_text)
            if m: price = float(m.group(1).replace(',', '.'))

            bold = desc_td.find(['b', 'strong'])
            full = desc_td.get_text(separator=" ", strip=True).strip()
            clean = full.replace("Menusalat oder Suppe", "")
            clean = re.sub(r'\s+', ' ', clean).strip()

            if bold:
                main = bold.get_text(strip=True)
                if len(clean) < len(main) + 5: dish_name = f"{main}{current_cat_suffix}"
                else: dish_name = f"{clean}{current_cat_suffix}"
            else:
                dish_name = f"{clean}{current_cat_suffix}"

            if len(dish_name) > 5:
                found_dishes.append({'name': dish_name[:200], 'preis': price})

    return save_if_changed(restaurant, found_dishes, cat_name)


# ==========================================
# 3. SCRAPER: MÜHLEBACH
# ==========================================
def scrape_muehlebach(restaurant):
    url = "https://www.landgasthof-muehlebach.ch/speisen/"
    base_url = "https://www.landgasthof-muehlebach.ch"

    try:
        # 1. Webseite laden
        response = cffi_requests.get(url, impersonate="chrome", timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 2. PDF Link suchen - Priorität auf Link-Text "Menü" oder "Menüs"
        link = soup.find('a', string=re.compile(r'Menü', re.IGNORECASE))
        
        if not link:
            link = soup.find('a', href=re.compile(r'\.pdf', re.IGNORECASE))

        if not link:
            print("   ⚠️ Mühlebach: Kein passender Link gefunden.")
            return False
        
        href = link['href']
        pdf_url = href if href.startswith('http') else f"{base_url}/{href.lstrip('/')}"
        
        # 3. PDF laden
        pdf_response = cffi_requests.get(pdf_url, impersonate="chrome", timeout=20)
        
        # 4. Text extrahieren
        f = io.BytesIO(pdf_response.content)
        reader = PdfReader(f)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        # 5. Datum suchen
        found_date = extract_date(full_text[:1200])
        if not found_date:
            found_date = datetime.date.today().strftime("%d.%m.%Y")
            
        cat_name = f"Tagesmenü {found_date}"

        # 6. Gerichte parsen
        lines = full_text.split('\n')
        found_dishes = []
        price_pat = re.compile(r'(?:Fr\.?|CHF)\s*(\d{1,2}[\.,]\d{2})', re.IGNORECASE)
        buf = []

        for line in lines:
            line = line.strip()
            if not line: continue 
            
            m = price_pat.search(line)
            if m:
                price = float(m.group(1).replace(',', '.'))
                if buf:
                    raw = " ".join(buf[-3:])
                    clean = raw.replace("Menu", "Menü").strip()
                    clean = re.sub(r'\s+', ' ', clean)
                    
                    if len(clean) > 5 and not extract_date(clean):
                        # --- GEÄNDERT: Kein "Mühlebach: " Präfix mehr ---
                        found_dishes.append({'name': clean[:200], 'preis': price})
                buf = []
            else:
                if not any(x in line for x in ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag", "Suppe", "Preise"]):
                    buf.append(line)

        print(f"   ✅ Mühlebach Scraper fertig. Kategorie: {cat_name}")
        return save_if_changed(restaurant, found_dishes, cat_name)

    except Exception as e:
        print(f"   ❌ Fehler Mühlebach Scraper: {e}")
        return False


# ==========================================
# HAUPTFUNKTION (Hier war der Fehler!)
# ==========================================
def run_scraper_for_restaurant(restaurant):
    if not restaurant.scraper_modul:
        return  # <--- HIER MUSS EINGERÜCKT SEIN (4 Leerzeichen)

    try:
        current_module = sys.modules[__name__]
        if hasattr(current_module, restaurant.scraper_modul):
            scraper_func = getattr(current_module, restaurant.scraper_modul)
            
            erfolg = scraper_func(restaurant) 
            
            restaurant.letztes_update = timezone.now()
            restaurant.save()
            
            if erfolg:
                print(f"   ✅ {restaurant.name}: OK.")
            else:
                print(f"   💤 {restaurant.name}: Keine Änderung.")
        else:
            print(f"   ❌ {restaurant.scraper_modul} nicht gefunden.")
    except Exception as e:
        print(f"   ❌ Crash {restaurant.name}: {e}")
