from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import datetime

class Standort(models.Model):
    name = models.CharField(max_length=100)
    
    class Meta:
        verbose_name = 'Standort'
        verbose_name_plural = 'Standorte'

    def __str__(self):
        return self.name

class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    beschreibung = models.TextField(blank=True)
    mindestbestellwert = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name="Min. Bestellwert")
    website = models.URLField(blank=True, verbose_name="Webseite/Link")
    
    biete_lokal = models.BooleanField(default=True, verbose_name="Bietet Essen vor Ort")
    biete_takeaway = models.BooleanField(default=True, verbose_name="Bietet Take-Away")
    biete_delivery = models.BooleanField(default=False, verbose_name="Bietet Lieferung")
    letztes_update = models.DateTimeField(null=True, blank=True)
    scraper_modul = models.CharField(max_length=100, blank=True, null=True, help_text="Name der Funktion in scrapers.py (z.B. scrape_adler)")
    standort = models.ForeignKey(Standort, on_delete=models.SET_NULL, null=True, blank=True, related_name='restaurants')

    def ist_jetzt_offen(self):
        jetzt = timezone.localtime(timezone.now())
        heute = jetzt.date()
        uhrzeit = jetzt.time()
        wochentag = heute.weekday()

        # 1. Check Spezial-Schliessungen (Feiertage haben Vorrang)
        ausnahme = self.ausnahmen.filter(datum=heute).first()
        if ausnahme:
            return not ausnahme.ist_geschlossen

        # 2. Check reguläre Öffnungszeiten (Zimmerstunden-Logik)
        tages_zeiten = self.zeiten.filter(wochentag=wochentag)
        
        # Wenn ein Eintrag für heute auf "Ganztägig geschlossen" steht -> Zu.
        if tages_zeiten.filter(geschlossen=True).exists():
            return False

        # Wir prüfen alle Schichten (z.B. Mittag und Abend)
        for schicht in tages_zeiten:
            if schicht.oeffnet_um and schicht.schliesst_um:
                if schicht.oeffnet_um <= uhrzeit <= schicht.schliesst_um:
                    return True
        
        return False

    # In deiner models.py beim Restaurant-Model
    @property
    def kann_heute_bestellen(self):
        jetzt = timezone.localtime(timezone.now())
        heute_datum = jetzt.date()
        aktuelle_uhrzeit = jetzt.time()
        wochentag = heute_datum.weekday() # Nutzt 0-6 wie deine anderen Funktionen

        # 1. Check Spezial-Schliessungen (wie in ist_jetzt_offen)
        ausnahme = self.ausnahmen.filter(datum=heute_datum).first()
        if ausnahme and ausnahme.ist_geschlossen:
            return False

        # 2. Check reguläre Zeiten
        tages_zeiten = self.zeiten.filter(wochentag=wochentag)
        
        # Wenn ganztägig geschlossen markiert -> False
        if tages_zeiten.filter(geschlossen=True).exists():
            return False

        for schicht in tages_zeiten:
            if schicht.oeffnet_um and schicht.schliesst_um:
                # Fall A: Es ist gerade offen
                if schicht.oeffnet_um <= aktuelle_uhrzeit <= schicht.schliesst_um:
                    return True
                # Fall B: Es öffnet heute erst noch
                if schicht.oeffnet_um > aktuelle_uhrzeit:
                    return True
                    
        return False

    def naechste_oeffnung(self):
        try:
            jetzt = timezone.localtime(timezone.now())
            
            # WICHTIG: Wir nutzen .all(), um die vorgeladenen Daten (prefetch_related) 
            # zu nutzen. Das verhindert hunderte neue Datenbankabfragen!
            zeiten_list = list(self.zeiten.all())
            ausnahmen_list = list(self.ausnahmen.all())
            
            # Wir prüfen die nächsten 7 Tage
            for i in range(8):
                check_datum = jetzt.date() + timedelta(days=i)
                wochentag = check_datum.weekday()
                
                # 1. Ist an diesem Tag eine Spezialschliessung (Feiertag etc.)?
                ausnahme = next((a for a in ausnahmen_list if a.datum == check_datum), None)
                if ausnahme and ausnahme.ist_geschlossen:
                    continue # Überspringen und nächsten Tag prüfen
                
                # 2. Reguläre Zeiten für diesen Tag filtern und nach Uhrzeit sortieren
                tages_zeiten = [z for z in zeiten_list if z.wochentag == wochentag and not z.geschlossen and z.oeffnet_um]
                tages_zeiten.sort(key=lambda x: x.oeffnet_um)
                
                for schicht in tages_zeiten:
                    if i == 0: # Heute
                        if schicht.oeffnet_um > jetzt.time():
                            return f"Heute, {schicht.oeffnet_um.strftime('%H:%M')} Uhr"
                    elif i == 1: # Morgen
                        return f"Morgen, {schicht.oeffnet_um.strftime('%H:%M')} Uhr"
                    else: # Später in der Woche
                        tage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                        return f"{tage[wochentag]}, {schicht.oeffnet_um.strftime('%H:%M')} Uhr"
            
            return "Auf unbestimmte Zeit" # Falls in den nächsten 7 Tagen nichts gefunden wird
        except Exception as e:
            print(f"Fehler bei naechste_oeffnung für {self.name}: {e}")
            return ""

    liefergebuehren = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Liefergebühren (CHF)"
    )

    class Meta:
        verbose_name = 'Restaurant'
        verbose_name_plural = 'Restaurants'

    def __str__(self):
        return self.name

class Gericht(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='gerichte')
    name = models.CharField(max_length=200)
    preis = models.DecimalField(max_digits=6, decimal_places=2)
    kategorie = models.CharField(max_length=100, default="Hauptspeise")
    reihenfolge = models.IntegerField(default=100) 

    class Meta:
        verbose_name = 'Gericht'
        verbose_name_plural = 'Gerichte'

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"

class OptionGroup(models.Model):
    gericht = models.ForeignKey(Gericht, on_delete=models.CASCADE, related_name='option_groups')
    name = models.CharField(max_length=100) 
    pflicht = models.BooleanField(default=False, verbose_name="Auswahl ist Pflicht")
    reihenfolge = models.IntegerField(default=0)
    
    TYP_CHOICES = [
        ('RADIO', 'Einzelwahl (Nur eines wählbar)'),
        ('CHECKBOX', 'Mehrfachwahl (Ankreuzen)'),
        ('NUMBER', 'Mengenwahl (Zähler 0-15)'),
    ]
    typ = models.CharField(max_length=20, choices=TYP_CHOICES, default='RADIO')

    def __str__(self):
        return f"{self.gericht.name} - {self.name} ({self.get_typ_display()})"

    class Meta:
        ordering = ['reihenfolge']
        verbose_name = 'Option Group'
        verbose_name_plural = 'Option Groups'

class OptionItem(models.Model):
    group = models.ForeignKey(OptionGroup, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100, blank=True, verbose_name="Name (oder leer lassen wenn Gericht gewählt)")
    gericht_verweis = models.ForeignKey(
        Gericht, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Existierendes Gericht verknüpfen"
    )
    aufpreis = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    reihenfolge = models.IntegerField(default=0)

    def get_name(self):
        if self.gericht_verweis:
            return self.gericht_verweis.name
        return self.name

    def __str__(self):
        return self.get_name()
    
    class Meta:
        ordering = ['reihenfolge']

class Bestellung(models.Model):
    benutzer = models.ForeignKey(User, on_delete=models.CASCADE)
    gericht = models.ForeignKey(Gericht, on_delete=models.CASCADE, null=True, blank=True)
    lokal_anmeldung = models.BooleanField(default=False, verbose_name="Nur Anmeldung (Lokal)")
    datum = models.DateTimeField(default=timezone.now)
    notiz = models.CharField(max_length=200, blank=True, null=True)
    optionen_text = models.TextField(blank=True, null=True, verbose_name="Gewählte Optionen")

    ART_CHOICES = [
        ('LOKAL', 'Im Restaurant essen'),
        ('TAKEAWAY', 'Take-Away'),
        ('DELIVERY', 'Bestellen'), 
    ]
    art = models.CharField(max_length=20, choices=ART_CHOICES, default='TAKEAWAY')

    class Meta:
        verbose_name = 'Bestellung'
        verbose_name_plural = 'Bestellungen'

    def __str__(self):
        return f"{self.benutzer.username} - {self.gericht.name}"


class Stimme(models.Model):
    benutzer = models.ForeignKey(User, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='stimmen')
    datum = models.DateField(auto_now_add=True)
    
    # --- WICHTIG: Das Feld 'art' muss hier sein, damit wir filtern können ---
    ART_CHOICES = [
        ('LOKAL', 'Im Restaurant essen'),
        ('TAKEAWAY', 'Take-Away'),
        ('DELIVERY', 'Bestellen'), 
    ]
    art = models.CharField(max_length=20, choices=ART_CHOICES, default='LOKAL')

    class Meta:
        unique_together = ('benutzer', 'datum')
        verbose_name = 'Stimme'
        verbose_name_plural = 'Stimmen'

    def __str__(self):
        return f"{self.benutzer.username} -> {self.restaurant.name} ({self.art})"

class Favorit(models.Model):
    benutzer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favoriten')
    gericht = models.ForeignKey(Gericht, on_delete=models.CASCADE, related_name='favorisiert_von')
    erstellt_am = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('benutzer', 'gericht')
        verbose_name = 'Favorit'
        verbose_name_plural = 'Favoriten'
    
class TagesVerantwortlicher(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, null=True, blank=True)
    datum = models.DateField(default=timezone.now)
    nutzer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    bestellzeit = models.CharField(max_length=20, blank=True, null=True, help_text="z.B. 12:00")
    bestellung_bestaetigt = models.BooleanField(default=False)
    zahlungsart = models.CharField(max_length=20, default='SONST')
    fahrer = models.ManyToManyField(User, related_name='fahrten', blank=True)

    art = models.CharField(max_length=20, choices=[
        ('LOKAL', 'Lokal'),
        ('TAKEAWAY', 'Takeaway'),
        ('DELIVERY', 'Lieferung')
    ], default='DELIVERY') # Default nach Bedarf anpassen

    class Meta:
        unique_together = ('restaurant', 'datum', 'art') # Nur einer pro Restaurant pro Tag
        
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    handynummer = models.CharField(max_length=20, blank=True, null=True, verbose_name="Handynummer")
    show_phone = models.BooleanField(default=False, verbose_name="Handynummer anzeigen")
    notify_daily = models.BooleanField(default=True, verbose_name="Tägliche Erinnerung (10:00 Uhr)")
    notify_order_confirm = models.BooleanField(default=True, verbose_name="Bestätigung bei Bestellung")
    notify_debt = models.BooleanField(default=True, verbose_name="Täglicher Schulden-Report")
    standard_standort = models.ForeignKey(Standort, on_delete=models.SET_NULL, null=True, blank=True)
    abwesend_von = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Abwesend/Urlaub von"
    )
    abwesend_bis = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Abwesend/Urlaub bis (inklusive)"
    )
    def __str__(self):
        return f'{self.user.username} Profile'

# WICHTIG: Falls du 'Standort' ganz oben in der models.py noch nicht importiert hast,
# musst du sicherstellen, dass die Klasse Standort über diesen Funktionen definiert ist!

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # 1. Wir suchen den gewünschten Standard-Standort (z.B. "Altendorf")
        standard = Standort.objects.filter(name="Altendorf").first()
        
        # Fallback: Falls "Altendorf" nicht existiert, nimm einfach den allerersten
        if not standard:
            standard = Standort.objects.first()
            
        # 2. Profil direkt MIT dem gefundenen Standort erstellen
        UserProfile.objects.create(user=instance, standard_standort=standard)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # get_or_create gibt zwei Dinge zurück: Das Profil und ob es gerade neu erstellt wurde
    profile, wurde_erstellt = UserProfile.objects.get_or_create(user=instance)
    
    # Falls das Profil für einen ALTEN User hier als Notlösung gerade neu erstellt wurde:
    if wurde_erstellt:
        standard = Standort.objects.filter(name="Altendorf").first() or Standort.objects.first()
        profile.standard_standort = standard
        
    profile.save()
# ... deine anderen Imports ...

class Schulden(models.Model):
    ZAHLUNGSART_CHOICES = [
        ('TWINT_REQ', 'TWINT Anforderung'),
        ('TWINT_SEND', 'TWINT gesendet'),
        ('SONST', 'Sonstiges'),
    ]
    glaeubiger = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guthaben_eintraege') # Der, der das Geld kriegt (Organizer)
    schuldner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schulden_eintraege') # Der, der bezahlen muss
    betrag = models.DecimalField(max_digits=6, decimal_places=2)
    datum = models.DateField(default=timezone.now)
    erledigt = models.BooleanField(default=False) # Um später "Bezahlt" zu markieren
    zahlungsart = models.CharField(
        max_length=20, 
        choices=ZAHLUNGSART_CHOICES, 
        default='SONST'
    )

    class Meta:
        verbose_name = 'Schuld'
        verbose_name_plural = 'Schulden'

    def __str__(self):
        return f"{self.schuldner} schuldet {self.glaeubiger} {self.betrag}"
        
        
class Oeffnungszeit(models.Model):
    WEEKDAYS = [
        (0, 'Montag'), (1, 'Dienstag'), (2, 'Mittwoch'),
        (3, 'Donnerstag'), (4, 'Freitag'), (5, 'Samstag'), (6, 'Sonntag'),
    ]
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='zeiten')
    wochentag = models.IntegerField(choices=WEEKDAYS)
    # null=True, blank=True erlaubt leere Felder bei Schliessungen
    oeffnet_um = models.TimeField(null=True, blank=True)
    schliesst_um = models.TimeField(null=True, blank=True)
    geschlossen = models.BooleanField(default=False, verbose_name="Heute geschlossen")

    # WICHTIG: Die Meta-Klasse mit unique_together löschen wir komplett!

class SpezialSchliessung(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='ausnahmen')
    datum = models.DateField()
    ist_geschlossen = models.BooleanField(default=True, verbose_name="An diesem Tag geschlossen")
    notiz = models.CharField(max_length=100, blank=True, help_text="z.B. Auffahrt") 

class SystemEinstellungen(models.Model):
    bestellschluss = models.TimeField(
        default=datetime.time(11, 0), 
        verbose_name="Bestellschluss (Uhrzeit)"
    )
    
    def save(self, *args, **kwargs):
        # Diese Zeile erzwingt, dass immer nur Eintrag Nummer 1 (die globale Einstellung) überschrieben wird
        self.pk = 1 
        super().save(*args, **kwargs)

    def __str__(self):
        return "Allgemeine System-Einstellungen"

    class Meta:
        verbose_name = "System-Einstellung"
        verbose_name_plural = "System-Einstellungen"