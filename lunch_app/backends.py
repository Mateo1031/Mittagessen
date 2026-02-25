from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class SuperuserOnlyBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        try:
            user = UserModel.objects.get(email__iexact=username)
        except UserModel.DoesNotExist:
            try:
                user = UserModel.objects.get(username__iexact=username)
            except UserModel.DoesNotExist:
                return None

        # --- DER ENTSCHEIDENDE FIX ---
        # Statt "if user.is_superuser" prüfen wir jetzt exakt auf deinen Root-Namen!
        # (Falls dein Root-User "root@user.ch" oder "admin" heißt, passe den Namen hier an)
        if user.username == 'root@user.ch' and user.check_password(password):
            return user
            
        # Alle anderen (auch andere Superuser!) werden eiskalt abgewiesen
        # und MÜSSEN zwingend über das LDAP-Backend gehen.
        return None