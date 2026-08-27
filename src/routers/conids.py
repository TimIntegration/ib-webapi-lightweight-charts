import json

import httpx
from fastapi import APIRouter
from .. import utils
from ..config import IB_GATEWAY_URL

router = APIRouter()


async def get_futures_conid(symbol: str = 'ES') -> tuple[str, list[dict]]:
    """Returns the conid for a given futures symbol."""
    endpoint = f"/trsrv/futures?symbols={symbol}"

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.get(f"{IB_GATEWAY_URL}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                with open('log.json', 'w') as log_file:
                    json.dump(data, log_file, indent=2)
                data_dict = utils._extract_bytestring_to_dict(data)
                conids = [
                    {contract.get('expirationDate'): contract.get('conid')} for contract in data_dict.get(symbol)]
                underlyingConid: str = data_dict.get(symbol)[0].get('underlyingConid')
                print(f"{underlyingConid=}")
                return underlyingConid, conids
        except Exception as e:
            print(f"Error fetching conid for {symbol}: {str(e)}")


