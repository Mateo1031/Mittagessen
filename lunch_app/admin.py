from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Restaurant, Gericht, Bestellung, Stimme, Favorit, OptionGroup, OptionItem, Schulden, UserProfile, TagesVerantwortlicher, Standort, Oeffnungszeit, SpezialSchliessung, SystemEinstellungen

class OeffnungszeitInline(admin.TabularInline):
    model = Oeffnungszeit
    extra = 7 # Direkt alle Wochentage anzeigen
    ordering = ('wochentag', 'oeffnet_um')

class SpezialSchliessungInline(admin.TabularInline):
    model = SpezialSchliessung
    extra = 1

# --- EBENE 3: Items (Cola, Salami) ---
class OptionItemInline(admin.TabularInline):
    model = OptionItem
    extra = 1
    fields = ('name', 'gericht_verweis', 'aufpreis', 'reihenfolge')
    
    # CRITICAL: Enables search functionality for dish selection
    autocomplete_fields = ['gericht_verweis']

# --- EBENE 2: Options-Gruppen ---
class OptionGroupAdmin(admin.ModelAdmin):
    inlines = [OptionItemInline]
    list_display = ('name', 'gericht', 'pflicht')
    list_filter = ('gericht__restaurant',)
    search_fields = ('name', 'gericht__name')

class OptionGroupInline(admin.TabularInline):
    model = OptionGroup
    extra = 0
    show_change_link = True 

# --- EBENE 1: Gericht ---
class GerichtAdmin(admin.ModelAdmin):
    inlines = [OptionGroupInline]
    list_display = ('name', 'preis')
    list_filter = ('restaurant',)
    
    # CRITICAL: Must be defined for autocomplete to work
    search_fields = ['name', 'restaurant__name'] 
    list_per_page = 2000

class GerichtInline(admin.StackedInline):
    model = Gericht
    extra = 0
    fields = ('name', 'preis', 'kategorie', 'reihenfolge', 'edit_link')
    readonly_fields = ('edit_link',)

    def edit_link(self, instance):
        # Falls das Objekt noch nicht gespeichert ist (keine ID)
        if not instance or not instance.id:
            return "Wird nach dem Speichern verfügbar"
        
        # Link generieren
        url = reverse('admin:lunch_app_gericht_change', args=[instance.id])
        
        # WICHTIG für Django 6.0: 
        # Wir nutzen mark_safe und f-Strings statt format_html, 
        # um den "args or kwargs"-Check zu umgehen, wenn keine Variablen ersetzt werden müssen.
        from django.utils.safestring import mark_safe
        
        return mark_safe(
            f'<a href="{url}" class="button" style="background-color: #3b82f6; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none;">'
            f'Optionen & Details bearbeiten ✏️</a>'
        )

    edit_link.short_description = "Erweiterte Einstellungen"
# --- EBENE 0: Restaurant ---
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'biete_lokal', 'biete_takeaway', 'biete_delivery', 'liefergebuehren')
    inlines = [GerichtInline, OeffnungszeitInline, SpezialSchliessungInline]
    search_fields = ['name']
    
    fieldsets = (
        ('Basisdaten', {
            'fields': ('name', 'beschreibung', 'website', 'mindestbestellwert', 'standort', 'liefergebuehren')
        }),
        ('Einstellungen', {
            'fields': ('biete_lokal', 'biete_takeaway', 'biete_delivery'),
            'classes': ('collapse',),
        }),
        # --- HIER IST DER NEUE TEIL ---
        ('Scraper / Automatisierung', {
            'fields': ('scraper_modul', 'letztes_update'),
            'description': 'Hier den Namen der Funktion aus scrapers.py eintragen (z.B. scrape_knobel)',
            'classes': ('collapse',), # Klappt standardmäßig zu, sieht sauberer aus
        }),
    )

admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(Gericht, GerichtAdmin)
admin.site.register(OptionGroup, OptionGroupAdmin)
admin.site.register(Bestellung)
admin.site.register(Stimme)
admin.site.register(Favorit)
admin.site.register(Standort)
admin.site.register(SystemEinstellungen)


from django import forms
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# 1. Das Formular für den User-Admin
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Zusätzliche Profil-Daten (Standort, Handynummer, Benachrichtigungen)'
    # Optional: Du kannst classes hinzufügen, wenn es standardmäßig zugeklappt sein soll
    # classes = ['collapse']

def benutzer_deaktivieren(modeladmin, request, queryset):
    # 1. Login sperren
    queryset.update(is_active=False)
    
    # 2. Alle E-Mail-Häkchen im Profil ausschalten
    UserProfile.objects.filter(user__in=queryset).update(
        notify_debt=False,
        notify_order_confirm=False,
        notify_daily=False
    )
benutzer_deaktivieren.short_description = "Ausgewählte Benutzer deaktivieren"

def benutzer_aktivieren(modeladmin, request, queryset):
    # 1. Login wieder freigeben
    queryset.update(is_active=True)
    
    # 2. E-Mail-Häkchen wieder auf den Standard (Ein) setzen
    UserProfile.objects.filter(user__in=queryset).update(
        notify_debt=True,
        notify_order_confirm=True,
        notify_daily=True
    )
benutzer_aktivieren.short_description = "Ausgewählte Benutzer aktivieren"

class MyUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    actions = [benutzer_deaktivieren, benutzer_aktivieren]
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active_display', 'is_admin_display')

    def is_active_display(self, obj):
        from django.utils.safestring import mark_safe
        if obj.is_active:
            return mark_safe('<span style="color: #10b981; font-weight: 600;">✅ Aktiv</span>')
        return mark_safe('<span style="color: #ef4444; font-weight: 600;">❌ Inaktiv</span>')
    is_active_display.short_description = 'Status'

    def is_admin_display(self, obj):
        from django.utils.safestring import mark_safe
        if obj.is_superuser:
            return mark_safe('<span style="color: #3b82f6; font-weight: 600;">👑 Admin</span>')
        elif obj.is_staff:
            return mark_safe('<span style="color: #f59e0b; font-weight: 600;">🛠️ Mitarbeiter</span>')
        return mark_safe('<span style="color: #6b7280;">👤 Normal</span>')
    is_admin_display.short_description = 'Rolle'
    
admin.site.unregister(User)
admin.site.register(User, MyUserAdmin)
# --- 4. Schulden Admin (bleibt gleich, nur ein bisschen aufgeräumt) ---
@admin.register(Schulden)
class SchuldenAdmin(admin.ModelAdmin):
    list_display = ('datum', 'schuldner', 'glaeubiger', 'betrag', 'erledigt')
    list_filter = ('erledigt', 'datum', 'glaeubiger')
    search_fields = ('schuldner__username', 'glaeubiger__username')
    

