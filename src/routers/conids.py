import json
from typing import Optional

import httpx
from fastapi import APIRouter
from .. import utils
from ..config import IB_GATEWAY_URL

router = APIRouter()


async def get_futures_conid(symbol: str = 'ES') -> tuple[Optional[str], list[dict]]:
    """Returns the conid for a given futures symbol."""
    endpoint = f"/trsrv/futures?symbols={symbol}"

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.get(f"{IB_GATEWAY_URL}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                
                data_dict = utils._extract_bytestring_to_dict(data) or {}
                contracts = data_dict.get(symbol) or data_dict.get(symbol.upper()) or data_dict.get(symbol.lower()) or []
                if contracts and isinstance(contracts, list) and len(contracts) > 0:
                    valid_contracts = [c for c in contracts if isinstance(c, dict)]
                    valid_contracts.sort(key=lambda c: int(str(c.get('expirationDate', 0) or 0)))
                    conids = [
                        {contract.get('expirationDate'): contract.get('conid')}
                        for contract in valid_contracts
                    ]
                    underlyingConid = valid_contracts[0].get('underlyingConid')
                    underlying_conid_str = str(underlyingConid) if underlyingConid is not None else None
                    print(f"{underlying_conid_str=}")
                    return underlying_conid_str, conids
                return None, []
        except Exception as e:
            print(f"Error fetching conid for {symbol}: {str(e)}")
            return None, []
    return None, []


