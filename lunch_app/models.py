# lunch_app/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    beschreibung = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Gericht(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='gerichte')
    name = models.CharField(max_length=200)
    preis = models.DecimalField(max_digits=6, decimal_places=2) # z.B. 12.50

    def __str__(self):
        return f"{self.name} ({self.preis} CHF)"

class Bestellung(models.Model):
    benutzer = models.ForeignKey(User, on_delete=models.CASCADE)
    gericht = models.ForeignKey(Gericht, on_delete=models.CASCADE)
    datum = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.benutzer.username} - {self.gericht.name}"
