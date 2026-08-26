import httpx
from fastapi import APIRouter
from .. import utils
from ..config import IB_GATEWAY_URL
import time, json

router = APIRouter()

@router.get('/get-expirations')
async def find_option_expiration(symbol:str = 'ES'):
    """Returns list of FOP expirations."""
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            await utils._iserver_pre_visit()
            time.sleep(1)
            # go to /iserver/secdef/search before /iserver/secdef/* such as strikes and rules
            endpoint = f"/iserver/secdef/search"
            params = {
                'symbol': symbol,
                'secType': 'STK',
                'name': False
            }

            response = await client.post(f"{IB_GATEWAY_URL}{endpoint}", json=params)

            conid, months = _parse_search_response(data = response.json())
            return conid, months
        except Exception as e:
            return {"error": f"Error fetching expirations for {symbol}: {str(e)}"}


def _parse_search_response(data):
    response_items = data if isinstance(data, list) else [data]
    response_list_of_dict: list[dict] = [
                    item for item in response_items if isinstance(item, dict)
                ]
    base_conid: str = response_list_of_dict[0].get('conid')
    print(f"finding FOP expirations for conid: {base_conid}")
    months: list[str] = []
    for item in response_list_of_dict:
        for section in item.get('sections', []):
            if section.get('secType') == 'FOP' and section.get('months'):
                months.extend(section['months'].split(';'))
    return base_conid, months
