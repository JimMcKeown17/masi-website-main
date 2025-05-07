from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        """
        Populates user information from social provider info.
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name and data.get('name'):
            user.name = data['name']
        if not user.email and data.get('email'):
            user.email = data['email']
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Enables auto signup if the email is not blacklisted.
        """
        email = sociallogin.account.extra_data.get('email')
        if email and self.is_email_blacklisted(email):
            return False
        return getattr(settings, 'SOCIALACCOUNT_AUTO_SIGNUP', True)

    def is_email_blacklisted(self, email):
        """
        Checks if the email is blacklisted.
        """
        blacklist = getattr(settings, 'ACCOUNT_EMAIL_BLACKLIST', [])
        return email.lower() in [e.lower() for e in blacklist]

class CustomAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        """
        Fills in a valid username, if required and missing.  If the
        username is already present it is assumed to be valid
        (unique).
        """
        from allauth.account.utils import user_email, user_field, user_username
        first_name = user_field(user, 'first_name')
        last_name = user_field(user, 'last_name')
        email = user_email(user)
        username = user_username(user)
        if username:
            return
        if email:
            username = email.split('@')[0]
        elif first_name and last_name:
            username = f"{first_name.lower()}{last_name.lower()}"
        else:
            username = 'user'
        user_username(user, username)

    def save_user(self, request, user, form, commit=True):
        """
        This is called when saving user via allauth registration.
        We override this to set additional data on user object.
        """
        # We don't want to save the password here
        data = form.cleaned_data
        email = data.get('email', '').lower()  # Convert email to lowercase
        name = data.get('name')
        user_email(user, email)
        if name:
            user.name = name
        if 'password1' in data:
            user.set_password(data["password1"])
        else:
            user.set_unusable_password()
        self.populate_username(request, user)
        if commit:
            user.save()
        return user

    def clean_email(self, email):
        """
        Validates that an email address is unique for the site.
        """
        email = email.lower()  # Convert email to lowercase
        if self.is_email_blacklisted(email):
            raise ValidationError(_("This email address is not allowed."))
        return super().clean_email(email)

    def is_email_blacklisted(self, email):
        """
        Checks if the email is blacklisted.
        """
        blacklist = getattr(settings, 'ACCOUNT_EMAIL_BLACKLIST', [])
        return email.lower() in [e.lower() for e in blacklist]