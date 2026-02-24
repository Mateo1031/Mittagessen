from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile
from django.utils import timezone

# Formular 1: Standard User Daten (Jetzt mit Username)
class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(required=True, label="Vorname")
    last_name = forms.CharField(required=True, label="Nachname")

    class Meta:
        model = User
        fields = ['first_name', 'last_name']  # email raus

    def save(self, commit=True):
        user = super().save(commit=False)
        # email und username werden NICHT verändert
        if commit:
            user.save()
        return user

heute_str = timezone.now().date().isoformat()

# Formular 2: Die Erweiterung (Handy)
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['handynummer', 'show_phone', 'notify_daily', 'notify_order_confirm', 'notify_debt', 'abwesend_bis', 'abwesend_von']
        labels = {'handynummer': 'Handynummer (für Bezahlungen)'}
        widgets = {
            'handynummer': forms.TextInput(attrs={'placeholder': ''}),
            'abwesend_bis': forms.DateInput(
                format='%Y-%m-%d',  # <-- HIER IST DIE MAGIE! Zwingt das Format für den Browser
                attrs={
                    'type': 'date', 
                    'class': 'modern-input', # Macht das Design passend zum Rest
                    'style': 'cursor: pointer;',
                    'min': heute_str
                }
            ),
            'abwesend_von': forms.DateInput(
                format='%Y-%m-%d',  # <-- HIER IST DIE MAGIE! Zwingt das Format für den Browser
                attrs={
                    'type': 'date', 
                    'class': 'modern-input', # Macht das Design passend zum Rest
                    'style': 'cursor: pointer;',
                    'min': heute_str
                }
            )
        }
        def clean(self):
            cleaned_data = super().clean()
            von = cleaned_data.get('abwesend_von')
            bis = cleaned_data.get('abwesend_bis')
            heute = timezone.now().date()

            # Fall 1: Startdatum liegt in der Zukunft nach dem Enddatum (Dein 28. bis 24. Problem)
            if von and bis and von > bis:
                self.add_error('abwesend_von', "Das Startdatum darf nicht nach dem Enddatum liegen.")
                self.add_error('abwesend_bis', "Das Enddatum muss nach dem Startdatum liegen.")

            # Fall 2: Jemand gibt ein Enddatum in der Vergangenheit ein
            if bis and bis < heute:
                self.add_error('abwesend_bis', "Du kannst keinen Urlaub in der Vergangenheit beenden.")

            # Fall 3: Unvollständige Angaben
            if (von and not bis) or (bis and not von):
                raise forms.ValidationError("Bitte fülle beide Datumsfelder aus, um den Zeitraum zu speichern.")

            return cleaned_data
        
class CustomRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-Mail-Adresse")
    first_name = forms.CharField(required=True, label="Vorname")
    last_name = forms.CharField(required=True, label="Nachname")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Email = Username
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user
