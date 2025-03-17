import re
from datetime import datetime

def clean_text(text):
    """
    Clean text by:
    - Converting to string (in case of None or lists)
    - Stripping whitespace
    - Removing any non-printable characters
    - Normalizing to a standard format
    """
    if text is None:
        return ''
    
    # Convert lists to their first element if possible
    if isinstance(text, list):
        if len(text) > 0:
            text = text[0]
        else:
            return ''
    
    # Handle string representation of lists - common with Airtable API
    if isinstance(text, str) and text.startswith('[') and text.endswith(']'):
        try:
            # Try to interpret as a Python list
            import ast
            parsed_list = ast.literal_eval(text)
            if isinstance(parsed_list, list) and len(parsed_list) > 0:
                text = parsed_list[0]
            else:
                text = ''
        except (SyntaxError, ValueError):
            # If we can't parse it, just leave it as is
            pass
    
    # Convert to string and strip
    cleaned = str(text).strip()
    
    # Remove non-printable characters
    cleaned = re.sub(r'[^\x20-\x7E]', '', cleaned)
    
    # Normalize capitalization
    cleaned = cleaned.title()
    
    return cleaned

def parse_date(date_value):
    """
    Parse date strings from Airtable
    Supports multiple common date formats and handles list inputs
    """
    if not date_value:
        return None
    
    # Handle case where date_value is a list (Airtable can return lists for some fields)
    if isinstance(date_value, list):
        # If it's a list, try to parse the first element if the list isn't empty
        if len(date_value) > 0:
            return parse_date(date_value[0])
        else:
            return None
    
    # Ensure we're working with a string
    date_str = str(date_value).strip()
    
    # List of possible date formats
    date_formats = [
        '%Y-%m-%d',  # ISO format
        '%m/%d/%Y',  # Common US format
        '%d/%m/%Y',  # Common UK format
        '%Y/%m/%d',  # Another common format
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None