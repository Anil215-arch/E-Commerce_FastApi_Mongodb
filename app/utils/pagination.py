import base64
import json
from typing import Optional, Dict, Any

class CursorUtils:
    
    @staticmethod
    def encode_cursor(cursor_dict: Dict[str, Any]) -> str:
        """
        Converts a dictionary (e.g., {"price": 499, "_id": "69ce..."}) 
        into a URL-safe Base64 string.
        """
        if not cursor_dict:
            return ""
            
        # 1. Convert Python dictionary to a JSON string
        json_str = json.dumps(cursor_dict)
        
        # 2. Encode the string to bytes, then to URL-safe Base64
        b64_encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        # 3. Strip the padding '=' characters. They are unnecessary and 
        # can sometimes cause URL parsing issues on older frontends.
        return b64_encoded.rstrip("=")

    @staticmethod
    def decode_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Takes a URL-safe Base64 string and converts it back to a dictionary.
        Returns None if the string is missing, invalid, or tampered with.
        """
        if not cursor_str:
            return None
            
        # 1. Re-add the stripped padding. Base64 requires strings to be a multiple of 4.
        padding_needed = 4 - (len(cursor_str) % 4)
        if padding_needed != 4:
            cursor_str += "=" * padding_needed
            
        try:
            # 2. Decode the Base64 string back to bytes, then to a JSON string
            json_bytes = base64.urlsafe_b64decode(cursor_str)
            
            # 3. Parse the JSON string back into a Python dictionary
            return json.loads(json_bytes.decode('utf-8'))
            
        except (ValueError, TypeError, UnicodeDecodeError):
            # If the cursor is corrupted, tampered with, or not valid JSON,
            # we swallow the error and return None (fallback to Page 1).
            return None