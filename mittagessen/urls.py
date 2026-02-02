# mittagessen/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('lunch_app.urls')),
    # Standard Login/Logout Views von Django
    path('login/', auth_views.LoginView.as_view(template_name='lunch_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
