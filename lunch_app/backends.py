from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # Hier ist der Trick: Wir suchen in der Spalte 'email' 
            # nach dem Wert, der im Login-Feld 'username' eingegeben wurde.
            user = UserModel.objects.get(email__iexact=username)
        except UserModel.DoesNotExist:
            # Keine E-Mail gefunden? Dann lassen wir Django weitermachen.
            return None
        except UserModel.MultipleObjectsReturned:
            # Falls (aus Versehen) zwei Leute die gleiche E-Mail haben, abbrechen.
            return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
