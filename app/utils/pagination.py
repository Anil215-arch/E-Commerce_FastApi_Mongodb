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
            
        json_str = json.dumps(cursor_dict)
        b64_encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return b64_encoded.rstrip("=")

    @staticmethod
    def decode_cursor(cursor_str: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Takes a URL-safe Base64 string and converts it back to a dictionary.
        Returns None if the string is missing, invalid, or tampered with.
        """
        if not cursor_str:
            return None
            
        padding_needed = 4 - (len(cursor_str) % 4)
        if padding_needed != 4:
            cursor_str += "=" * padding_needed
            
        try:
            json_bytes = base64.urlsafe_b64decode(cursor_str)
            return json.loads(json_bytes.decode('utf-8'))
            
        except (ValueError, TypeError, UnicodeDecodeError):
            return None