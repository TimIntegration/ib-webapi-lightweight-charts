import httpx
from fastapi import APIRouter
from .. import utils
from ..config import IB_GATEWAY_URL

router = APIRouter()


async def get_futures_conid(symbol: str = 'ES') -> list[dict]:
    """Returns the conid for a given futures symbol."""
    endpoint = f"/trsrv/futures?symbols={symbol}"

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.get(f"{IB_GATEWAY_URL}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                data_dict = utils._extract_bytestring_to_dict(data)
                conids = [
                    {contract.get('expirationDate'): contract.get('conid')} for contract in data_dict.get(symbol)]
                return conids
        except Exception as e:
            print(f"Error fetching conid for {symbol}: {str(e)}")


@router.get('/get-conids')
async def list_conids_for_symbol(symbol: str = 'ES'):
    return await get_futures_conid(symbol)