from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.urls import path
from . import views

urlpatterns = [
    # Die neue Startseite (Auswahl der Art)
    path('', views.welcome, name='welcome'),
    
    # Die Liste der Restaurants (gefiltert nach Art)
    path('liste/<str:art>/', views.restaurant_liste, name='restaurant_liste'),
    
    path('menu/<int:restaurant_id>/', views.restaurant_menu, name='menu'),
    path('bestellen/', views.bestellung_abschliessen, name='bestellen_abschliessen'),
    
    # Alte Home-Route als Fallback (leitet um oder zeigt alles)
    path('', views.welcome, name='home'), 
    
    path('uebersicht/', views.bestell_uebersicht, name='uebersicht'),
    path('stornieren/<int:bestellung_id>/', views.bestellung_stornieren, name='stornieren'),
    path('eigene_stornieren/', views.eigene_bestellung_stornieren, name='eigene_stornieren'),
    path('alles_loeschen/', views.alles_loeschen, name='alles_loeschen'),
    path('toggle_favorit/<int:gericht_id>/', views.toggle_favorit, name='toggle_favorit'),
    path('vote/<int:restaurant_id>/', views.vote_restaurant, name='vote_restaurant'),
    path('copy_order/<int:user_id>/', views.copy_other_order, name='copy_other_order'),
    path('login/', auth_views.LoginView.as_view(template_name='lunch_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('api/get_voters/<int:restaurant_id>/', views.get_voters, name='get_voters'),
    path('claim-order/<int:restaurant_id>/', views.claim_order, name='claim_order'),
    path('set-time/<int:restaurant_id>/', views.set_order_time, name='set_order_time'),
    path('unclaim-order/<int:restaurant_id>/', views.unclaim_order, name='unclaim_order'),
    path('tagesabschluss/', views.tagesabschluss, name='tagesabschluss'),
    path('bezahlt/<int:schulden_id>/', views.schulden_begleichen, name='schulden_begleichen'),
    path('profile/', views.profile, name='profile'),
    # ... deine anderen Pfade ...
    
    # 1. Seite: Passwort ändern Formular
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='lunch_app/password_change.html',
        success_url=reverse_lazy('password_change_done')
    ), name='password_change'),

    # 2. Seite: Bestätigung nach Erfolg
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='lunch_app/password_change_done.html'
    ), name='password_change_done'),
    
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='lunch_app/password_reset.html'
    ), name='password_reset'),

    # 2. Meldung "Gesendet"
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='lunch_app/password_reset_done.html'
    ), name='password_reset_done'),

    # 3. Link aus E-Mail: Neues Passwort eingeben
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='lunch_app/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    # 4. Erfolg!
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='lunch_app/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    path('change-art/<int:restaurant_id>/<str:art_typ>/', views.change_order_type, name='change_order_type'),
    
    path('trigger-all-scrapers/', views.trigger_all_scrapers, name='trigger_all_scrapers'),
    
    path('system-reset/', views.system_reset, name='system_reset'),
    path('account/delete/', views.account_delete, name='account_delete'),
    path('confirm_order/<int:restaurant_id>/', views.confirm_order_placed, name='confirm_order_placed'),
    path('feedback/', views.feedback, name='feedback'),
    path('schulden/confirm/<int:debtor_id>/<str:datum_str>/', views.confirm_daily_payments, name='confirm_daily_payments'),
    path('zahlungsmethode/<int:restaurant_id>/', views.set_payment_method, name='set_payment_method'),
    path('toggle_driver/<int:restaurant_id>/', views.toggle_driver, name='toggle_driver'),
    path('standort-wechseln/<int:standort_id>/', views.set_active_standort, name='set_standort'),
    path('toggle-show-phone/', views.toggle_show_phone, name='toggle_show_phone'),
    path('bestellen-abschliessen/', views.bestellung_abschliessen, name='bestellen_abschliessen'),
    path('stornieren-lokal/<int:restaurant_id>/', views.stornieren_lokal, name='stornieren_lokal'),
]
