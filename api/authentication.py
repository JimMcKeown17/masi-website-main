from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model
import requests, jwt

User = get_user_model()

class ClerkAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return None

        token = auth.split(" ")[1]
        try:
            jwks = requests.get("https://YOUR-CLERK-INSTANCE_ID.clerk.accounts.dev/.well-known/jwks.json").json()
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwks["keys"][0])
            decoded = jwt.decode(token, public_key, algorithms=["RS256"], audience="YOUR-CLERK-APP-ID")
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid Clerk token")

        email = decoded.get("email")
        clerk_id = decoded.get("sub")
        if not email:
            raise exceptions.AuthenticationFailed("No email in token")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email.split("@")[0], "role": "viewer"}
        )
        return (user, None)
