# core/utils/helpers.py
from datetime import datetime
from django.conf import settings

def get_site_info():
    """Basic site information"""
    return {
        'site_name': 'Masinyusane',
        'tagline': 'Empowerment Through Education',
        'contact_email': 'info@masinyusane.org',
        'phone': '610 248 9363',
        'address': {
            'street': '72 Russell Road, Central',
            'city': 'Gqeberha',
            'province': 'Eastern Cape',
            'zip': '6001'
        },
        'social_media': {
            'linkedin': 'https://linkedin.com/company/masinyusane',
            'twitter': 'https://twitter.com/masinyusane',
            'facebook': 'https://facebook.com/masinyusane',
            'instagram': 'https://instagram.com/masinyusane',
            'youtube': 'https://youtube.com/masinyusane',
        }
    }

def get_meta_defaults():
    """Default meta tags for SEO and social sharing"""
    return {
        'default_description': 'Masinyusane is a leading African education nonprofit transforming lives through literacy, numeracy, and job creation in South Africa. Our data-driven approach delivers measurable impact in education and employment.',
        
        'default_keywords': [
            'South African education',
            'literacy programs Africa',
            'numeracy education',
            'job creation South Africa',
            'education nonprofit',
            'African education NGO',
            'data driven education',
            'youth employment South Africa',
            'education impact Africa',
            'literacy improvement',
            'educational development',
            'numeraacy',
        ],
        
        # For social sharing cards
        'social_title': 'Masinyusane | Leading African Education Nonprofit',
        'social_description': 'Transforming South African lives through literacy, numeracy, and job creation. Join us in making measurable impact.',
        'default_image': 'path/to/social-share-image.jpg',  # Should be at least 1200x630px
        
        # Additional meta information
        'organization': {
            'name': 'Masinyusane',
            'type': 'NonProfit',
            'area_served': 'South Africa',
            'founding_date': '2008',  # Update with actual year
        },
        
        # Location info for local SEO
        'location': {
            'region': 'South Africa',
            'city': 'Port Elizabeth',  # Update if needed
            'country': 'South Africa'
        }
    }

def format_phone(phone):
    """Format phone numbers consistently"""
    numbers = ''.join(filter(str.isdigit, str(phone)))
    return f"({numbers[:3]}) {numbers[3:6]}-{numbers[6:]}"

def get_environment_info():
    """Environment-specific information"""
    return {
        'is_production': not settings.DEBUG,
        'environment': 'Production' if not settings.DEBUG else 'Development',
        'debug_mode': settings.DEBUG
    }