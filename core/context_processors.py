# core/context_processors.py
from datetime import datetime
from django.conf import settings
from .utils.helpers import get_site_info, get_meta_defaults, get_environment_info

def site_settings(request):
    """Global site settings available to all templates"""
    return {
        # Basic site info
        'site_info': get_site_info(),
        
        # Time and date
        'current_year': datetime.now().year,
        'current_date': datetime.now(),
        
        # Meta defaults for SEO
        'meta_defaults': get_meta_defaults(),
        
        # Current path for navigation highlighting
        'current_path': request.path,
        
        # Environment info
        'environment': get_environment_info(),
        
        # Navigation structure
        'main_nav': [
            {'title': 'Home', 'url': '/', 'name': 'home'},
            {'title': 'About', 'url': '/about/', 'name': 'about'},
            {'title': 'Services', 'url': '/services/', 'name': 'services'},
            {'title': 'Contact', 'url': '/contact/', 'name': 'contact'},
        ],
        
        # Footer links
        'footer_links': {
            'company': [
                {'title': 'About Us', 'url': '/about/'},
                {'title': 'Contact', 'url': '/contact/'},
                {'title': 'Careers', 'url': '/careers/'},
            ],
            'legal': [
                {'title': 'Privacy Policy', 'url': '/privacy/'},
                {'title': 'Terms of Service', 'url': '/terms/'},
            ]
        }
    }
    
def navbar_context(request):
    # Get the current path
    path = request.path

    # Define which pages use the dark navbar
    dark_navbar_pages = ['/children/', '/youth/', '/donate/', '/top-learner/', '/impact/', '/data/', '/apply/']  # Add your white background pages here
    
    # Return appropriate context
    return {
        'use_dark_navbar': path in dark_navbar_pages
    }