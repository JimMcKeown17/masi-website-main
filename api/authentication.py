from rest_framework import authentication, exceptions
from django.contrib.auth import get_user_model
import requests, jwt
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()

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
            # Get JWKS from Clerk
            print("🔍 Fetching JWKS from Clerk...")
            jwks_response = requests.get("https://fancy-walleye-25.clerk.accounts.dev/.well-known/jwks.json")
            jwks = jwks_response.json()
            print(f"🔍 JWKS fetched successfully, keys count: {len(jwks.get('keys', []))}")
            
            # Get the public key
            public_key = None
            for key in jwks["keys"]:
                try:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    break
                except Exception:
                    continue
            
            if not public_key:
                print("🔍 No valid key found in JWKS")
                raise exceptions.AuthenticationFailed("No valid key found in JWKS")
            
            print("🔍 Public key extracted successfully")
            
            # Decode the token (session tokens don't have audience)
            decoded = jwt.decode(
                token, 
                public_key, 
                algorithms=["RS256"],
                options={"verify_aud": False}
            )
            print("🔍 Token decoded successfully")
            print(f"🔍 Decoded payload keys: {list(decoded.keys())}")
            
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

        # Create or get user
        print(f"🔍 Creating/getting Django user for email: {primary_email}")
        try:
            user, created = User.objects.get_or_create(
                email=primary_email,
                defaults={
                    "username": primary_email.split("@")[0], 
                    "first_name": first_name,
                    "last_name": last_name
                }
            )
            print(f"🔍 User {'created' if created else 'found'}: {user.email}")
            
            # Update user info if it changed
            if not created:
                updated = False
                if user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                if updated:
                    user.save()
                    print("🔍 User info updated")
            
            print(f"🔍 Authentication successful for user: {user.email}")
            return (user, None)
            
        except Exception as e:
            print(f"🔍 Error creating/updating Django user: {e}")
            logger.error(f"Error creating/updating Django user: {e}")
            raise exceptions.AuthenticationFailed("Failed to create user")
