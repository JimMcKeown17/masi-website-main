from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model
import requests, jwt, time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()

# JWKS cache: the signing keys rarely change, so avoid a network round-trip on
# every authenticated request. Refreshed on demand when an unknown kid appears.
_jwks_cache = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 60 * 60


def _get_jwks(force_refresh=False):
    now = time.time()
    if (
        force_refresh
        or _jwks_cache["keys"] is None
        or now - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS
    ):
        url = f"{settings.CLERK_FRONTEND_API}/.well-known/jwks.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        _jwks_cache["keys"] = response.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]

class ClerkAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        print("🔍 ClerkAuthentication.authenticate called")
        
        auth = request.headers.get("Authorization")
        print(f"🔍 Authorization header: {auth[:50] if auth else 'None'}...")
        
        if not auth or not auth.startswith("Bearer "):
            print("🔍 No valid Authorization header found")
            return None

        token = auth.split(" ")[1]
        print(f"🔍 Token extracted: {token[:20]}...")
        
        try:
            # Verify the token against the JWKS of the Clerk instance configured
            # in CLERK_FRONTEND_API (dev vs production have different keys).
            jwks = _get_jwks()
            kid = jwt.get_unverified_header(token).get("kid")
            jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not jwk:
                # Key rotation: refresh once before giving up
                jwks = _get_jwks(force_refresh=True)
                jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not jwk:
                raise exceptions.AuthenticationFailed("Token signed by unknown key")

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)

            # Session tokens carry no audience, but the issuer must be our instance
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=settings.CLERK_FRONTEND_API,
                options={"verify_aud": False},
            )
            print(f"🔍 Token decoded successfully, payload keys: {list(decoded.keys())}")

        except exceptions.AuthenticationFailed:
            raise
        except jwt.ExpiredSignatureError:
            print("🔍 Token has expired")
            raise exceptions.AuthenticationFailed("Token has expired")
        except jwt.InvalidTokenError as e:
            print(f"🔍 Invalid Clerk token: {e}")
            logger.error(f"Invalid Clerk token: {e}")
            raise exceptions.AuthenticationFailed("Invalid Clerk token")
        except Exception as e:
            print(f"🔍 Error validating Clerk token: {e}")
            logger.error(f"Error validating Clerk token: {e}")
            raise exceptions.AuthenticationFailed("Token validation failed")

        # Get user ID from token
        clerk_user_id = decoded.get("sub")
        print(f"🔍 Extracted user ID: {clerk_user_id}")
        
        if not clerk_user_id:
            print("🔍 No user ID in token")
            raise exceptions.AuthenticationFailed("No user ID in token")

        # Fetch user info from Clerk API
        try:
            clerk_secret = getattr(settings, 'CLERK_SECRET_KEY', None)
            print(f"🔍 Clerk secret key configured: {bool(clerk_secret)}")
            print(f"🔍 Clerk secret key (first 10 chars): {clerk_secret[:10] if clerk_secret else 'None'}...")
            
            if not clerk_secret:
                print("🔍 Clerk secret key not configured")
                raise exceptions.AuthenticationFailed("Clerk secret key not configured")
            
            headers = {
                'Authorization': f'Bearer {clerk_secret}',
                'Content-Type': 'application/json'
            }
            
            api_url = f'https://api.clerk.com/v1/users/{clerk_user_id}'
            print(f"🔍 Making request to: {api_url}")
            
            user_response = requests.get(api_url, headers=headers)
            print(f"🔍 Clerk API response status: {user_response.status_code}")
            
            if user_response.status_code != 200:
                print(f"🔍 Clerk API error response: {user_response.text}")
                raise exceptions.AuthenticationFailed(f"Failed to fetch user from Clerk: {user_response.status_code}")
            
            user_data = user_response.json()
            print(f"🔍 User data keys: {list(user_data.keys())}")
            
            # Extract user information
            email_addresses = user_data.get('email_addresses', [])
            print(f"🔍 Email addresses count: {len(email_addresses)}")
            
            primary_email = None
            for email_obj in email_addresses:
                if email_obj.get('id') == user_data.get('primary_email_address_id'):
                    primary_email = email_obj.get('email_address')
                    break
            
            if not primary_email and email_addresses:
                primary_email = email_addresses[0].get('email_address')
            
            print(f"🔍 Primary email found: {primary_email}")
            
            if not primary_email:
                print("🔍 No email found for user")
                raise exceptions.AuthenticationFailed("No email found for user")
            
            # Normalize email to lowercase for consistent lookups
            primary_email = primary_email.lower()
            print(f"🔍 Normalized email: {primary_email}")
            
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            print(f"🔍 User info - Name: {first_name} {last_name}, Email: {primary_email}")
            
        except requests.RequestException as e:
            print(f"🔍 Request exception: {e}")
            logger.error(f"Error fetching user from Clerk API: {e}")
            raise exceptions.AuthenticationFailed("Failed to fetch user information")
        except Exception as e:
            print(f"🔍 Unexpected error in Clerk API call: {e}")
            logger.error(f"Unexpected error in Clerk API call: {e}")
            raise exceptions.AuthenticationFailed("Failed to fetch user information")

        # Create or get user using case-insensitive email lookup
        print(f"🔍 Creating/getting Django user for email: {primary_email}")
        try:
            # Use __iexact for case-insensitive lookup
            user = User.objects.filter(email__iexact=primary_email).first()
            
            if user:
                # User exists - update if needed
                print(f"🔍 User found: {user.email}")
                updated = False
                
                # Update email to lowercase if it's not already
                if user.email != primary_email:
                    user.email = primary_email
                    updated = True
                
                if user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                    
                if user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                    
                if updated:
                    user.save()
                    print("🔍 User info updated")
            else:
                # User doesn't exist - create new one
                user = User.objects.create(
                    email=primary_email,
                    username=primary_email.split("@")[0],
                    first_name=first_name,
                    last_name=last_name
                )
                print(f"🔍 User created: {user.email}")
            
            print(f"🔍 Authentication successful for user: {user.email}")
            return (user, None)
            
        except Exception as e:
            print(f"🔍 Error creating/updating Django user: {e}")
            logger.error(f"Error creating/updating Django user: {e}")
            raise exceptions.AuthenticationFailed("Failed to create user")