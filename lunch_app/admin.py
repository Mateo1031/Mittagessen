# lunch_app/admin.py
from django.contrib import admin
from .models import Restaurant, Gericht, Bestellung

class GerichtInline(admin.TabularInline):
    model = Gericht
    extra = 1

class RestaurantAdmin(admin.ModelAdmin):
    inlines = [GerichtInline]

admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(Bestellung)
