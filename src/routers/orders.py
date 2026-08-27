import asyncio
import json
from typing import Any, Optional

import httpx
from fastapi import APIRouter
from .. import utils
from ..config import IB_GATEWAY_URL, futures_base_conid

router = APIRouter()


def _parse_for_expiration(
    data: Any,
    sec_type: Optional[str] = None
) -> tuple[Optional[str], list[str], str, Optional[str]]:
    """Extracts underlying conid, expirations, secType, and exchange from secdef search response."""
    response_items = data if isinstance(data, list) else [data]
    response_list_of_dict: list[dict] = [
        item for item in response_items if isinstance(item, dict)
    ]
    if not response_list_of_dict:
        return None, [], 'FOP', None

    target_st = sec_type.upper() if sec_type else None

    # Find the item that contains the relevant derivative section (FOP / OPT or matching target_st)
    matched_item = None
    matched_section = None
    for item in response_list_of_dict:
        sections = item.get('sections', [])
        for section in sections:
            st = section.get('secType')
            if target_st and st == target_st:
                matched_item = item
                matched_section = section
                break
            elif not target_st and st in ('FOP', 'OPT'):
                matched_item = item
                matched_section = section
                break
        if matched_item:
            break

    if matched_item and matched_section:
        base_conid = str(matched_item.get('conid')) if matched_item.get('conid') is not None else None
        detected_sec_type = matched_section.get('secType', 'FOP')
        raw_exchange = matched_section.get('exchange')
        detected_exchange = raw_exchange.split(';')[0].strip() if raw_exchange else None

        months: list[str] = []
        for section in matched_item.get('sections', []):
            st = section.get('secType')
            if (target_st and st == target_st) or (not target_st and st in ('FOP', 'OPT')):
                if section.get('months'):
                    for m in section['months'].split(';'):
                        m_clean = m.strip()
                        if m_clean and m_clean not in months:
                            months.append(m_clean)

        print(f"finding expirations for conid: {base_conid}, secType: {detected_sec_type}, exchange: {detected_exchange}")
        return base_conid, months, detected_sec_type, detected_exchange

    # Fallback to first item if no specific derivative section was found
    first_item = response_list_of_dict[0]
    base_conid = str(first_item.get('conid')) if first_item.get('conid') is not None else None
    print(f"fallback conid: {base_conid}")
    return base_conid, [], target_st or 'FOP', None


async def get_option_expirations(
    symbol: str = 'ES',
    sec_type: Optional[str] = None
) -> tuple[Optional[str], list[str], str, Optional[str]]:
    """Helper to retrieve underlying conid, expirations, secType, and exchange from IBKR."""
    # Resolve symbol if a known futures conid was provided
    conid_to_symbol = {v: k for k, v in futures_base_conid.items()}
    resolved_symbol = conid_to_symbol.get(symbol, symbol)

    async with httpx.AsyncClient(verify=False) as client:
        try:
            await utils._iserver_pre_visit()
            await asyncio.sleep(1)
            endpoint = "/iserver/secdef/search"
            payload: dict[str, Any] = {'symbol': resolved_symbol}
            if sec_type:
                payload['secType'] = sec_type

            response = await client.post(
                f"{IB_GATEWAY_URL}{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code != 200:
                print(f"Error searching secdef for {resolved_symbol}: status {response.status_code} {response.text}")
                return None, [], 'FOP', None

            base_conid, months, parsed_sec_type, exchange = _parse_for_expiration(
                data=response.json(),
                sec_type=sec_type
            )
            return base_conid, months, parsed_sec_type, exchange
        except Exception as e:
            print(f"Error fetching expirations for {symbol}: {str(e)}")
            return None, [], 'FOP', None


@router.get('/get-expiration')
async def test_get_option_expirations(
    symbol: str = 'ES',
    sec_type: Optional[str] = None
) -> tuple[Optional[str], list[str]]:
    """Returns list of FOP/OPT expirations as (conid, months)."""
    base_conid, months, _, _ = await get_option_expirations(symbol=symbol, sec_type=sec_type)
    return base_conid, months


async def _find_strikes(
    base_conid: str,
    expiration_month: str,
    sec_type: str = 'FOP',
    exchange: Optional[str] = 'CME',
    right: Optional[str] = 'C'
) -> Any:
    """Fetches strike prices for a given conid and month from IBKR."""
    async with httpx.AsyncClient(verify=False) as client:
        try:
            await utils._iserver_pre_visit()
            await asyncio.sleep(1)
            endpoint = "/iserver/secdef/strikes"
            params: dict[str, Any] = {
                'conid': str(base_conid),
                'sectype': sec_type,
                'month': expiration_month,
            }
            if exchange:
                params['exchange'] = exchange.split(';')[0].strip()

            response = await client.get(f"{IB_GATEWAY_URL}{endpoint}", params=params)
            if response.status_code != 200:
                return {"error": f"Error fetching strikes: status {response.status_code} - {response.text}"}

            data = response.json()
            print(f"Strikes response: {data}")

            if isinstance(data, dict):
                if right:
                    r = right.strip().upper()
                    if r in ('C', 'CALL') and 'call' in data:
                        return data.get('call', [])
                    elif r in ('P', 'PUT') and 'put' in data:
                        return data.get('put', [])
                    elif r == 'ALL':
                        return data
                return data

            return data
        except Exception as e:
            return {"error": f"Error fetching strikes for {base_conid=}, {expiration_month=}: {str(e)}"}


@router.get('/get-strikes')
async def show_strikes(
    symbol: str = 'ES',
    number_of_strikes: int = 30,
    right: Optional[str] = 'C',
    month: Optional[str] = None,
    sec_type: Optional[str] = None,
    exchange: Optional[str] = None
):
    """Returns option strikes for a given symbol and right ('C', 'P', or 'ALL')."""
    base_conid, months, derived_sec_type, derived_exchange = await get_option_expirations(
        symbol=symbol,
        sec_type=sec_type
    )
    if not base_conid:
        return {"error": f"No underlying contract found for symbol {symbol}"}

    target_month = month or (months[0] if months else None)
    if not target_month:
        return {"error": f"No expiration months found for symbol {symbol}"}

    target_month = target_month.strip().upper()
    target_sec_type = sec_type or derived_sec_type or 'FOP'
    target_exchange = exchange or derived_exchange or ('CME' if target_sec_type == 'FOP' else 'SMART')

    strikes = await _find_strikes(
        base_conid=base_conid,
        expiration_month=target_month,
        sec_type=target_sec_type,
        exchange=target_exchange,
        right=right
    )
    # if len(strikes) > number_of_strikes:
    #     start_index = (len(strikes) - number_of_strikes) // 2
    #     end_index = start_index + number_of_strikes
    #     strikes = strikes[start_index:end_index]
    print(f"{strikes=}")
    return strikes