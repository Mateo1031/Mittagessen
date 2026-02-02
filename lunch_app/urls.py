from django.urls import path
from . import views

urlpatterns = [
    path('', views.restaurant_liste, name='home'),
    path('restaurant/<int:restaurant_id>/', views.restaurant_menu, name='menu'),
    
    # NEU: Diese URL verarbeitet jetzt das Formular mit den Checkboxen
    path('bestellen_abschliessen/', views.bestellung_abschliessen, name='bestellen_abschliessen'),
    
    path('zusammenfassung/', views.bestell_uebersicht, name='uebersicht'),
    path('register/', views.register, name='register'),
]
