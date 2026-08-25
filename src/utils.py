import json

def _extract_bytestring_to_dict(byte_string_message):
    """Convert json bytes or string into dictionary"""
    if isinstance(byte_string_message, dict):
        return byte_string_message
    
    # Convert bytes to string if needed
    if isinstance(byte_string_message, bytes):
        try:
            byte_string_message = byte_string_message.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return None
    
    # Parse JSON string
    if isinstance(byte_string_message, str):
        try:
            return json.loads(byte_string_message)
        except json.JSONDecodeError:
            return None
    
    return None