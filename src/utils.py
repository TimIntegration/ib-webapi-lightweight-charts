import json, httpx
from .config import IB_GATEWAY_URL

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


async def _iserver_pre_visit():
    '''
    Initialize Brokerage Session per
    https://www.interactivebrokers.com/docs/web-api/api/web-api/initializing-brokerage-session
    '''
    endpoint = '/iserver/auth/ssodh/init'
    payload = {}
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.post(
                url=f"{IB_GATEWAY_URL}{endpoint}",
                json=payload,
                headers=headers
                )
        except Exception as e:
            print(f"Error visit {endpoint}: {str(e)}")

