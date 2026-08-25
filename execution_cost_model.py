"""ATLAS live execution-cost estimator.

Research-only model for OKX linear USDT swaps. It estimates one-way half-spread
and market-impact/slippage from the live L2 book for a configured USDT notional.
The model becomes validated only when:
- the venue is explicitly configured as OKX_USDT_SWAP;
- a real per-side taker fee is configured through ATLAS_EXECUTION_TAKER_FEE_BPS;
- contract metadata proves a linear base-denominated contract value;
- the order book has enough depth to fill the configured research notional.

No fee is invented and no missing depth is extrapolated.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

VERSION = 'EXECUTION_COST_MODEL_V1_OKX_SWAP_L2'
SUPPORTED_VENUE = 'OKX_USDT_SWAP'


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _get_json(url, ua='ATLAS-Research/1.0', timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _inst_id(symbol):
    s = str(symbol or '').upper().replace('BINANCE:', '')
    if not s.endswith('USDT'):
        raise ValueError('symbol must end with USDT')
    return f'{s[:-4]}-USDT-SWAP'


def _first_data(obj, label):
    if str((obj or {}).get('code')) != '0':
        raise RuntimeError(f"OKX {label} code={(obj or {}).get('code')} msg={(obj or {}).get('msg')}")
    rows = (obj or {}).get('data') or []
    if not rows:
        raise RuntimeError(f'OKX {label} returned no data')
    return rows[0]


def _contract_base_value(meta, symbol):
    base = str(symbol).upper().replace('BINANCE:', '')[:-4]
    ct_val = _f(meta.get('ctVal'))
    ct_ccy = str(meta.get('ctValCcy') or '').upper()
    ct_type = str(meta.get('ctType') or '').lower()
    settle = str(meta.get('settleCcy') or '').upper()
    if ct_val is None or ct_val <= 0:
        return None, 'MISSING_CTVAL'
    if ct_type and ct_type != 'linear':
        return None, 'NON_LINEAR_CONTRACT'
    if settle and settle != 'USDT':
        return None, 'NON_USDT_SETTLEMENT'
    if ct_ccy != base:
        return None, f'CTVAL_CCY_NOT_BASE:{ct_ccy or "UNKNOWN"}'
    return ct_val, 'LINEAR_BASE_CTVAL'


def _normalize_book(book):
    bids = []
    asks = []
    for side_name, target in (('bids', bids), ('asks', asks)):
        for row in book.get(side_name) or []:
            if len(row) < 2:
                continue
            px = _f(row[0]); contracts = _f(row[1])
            if px is not None and contracts is not None and px > 0 and contracts > 0:
                target.append((px, contracts))
    if not bids or not asks:
        raise RuntimeError('order book missing bids or asks')
    return bids, asks


def _vwap_for_quote(levels, notional_usdt, base_per_contract):
    remaining = float(notional_usdt)
    quote_filled = 0.0
    base_filled = 0.0
    for px, contracts in levels:
        base_capacity = contracts * base_per_contract
        quote_capacity = base_capacity * px
        if quote_capacity <= 0:
            continue
        quote_take = min(remaining, quote_capacity)
        base_take = quote_take / px
        quote_filled += quote_take
        base_filled += base_take
        remaining -= quote_take
        if remaining <= 1e-9:
            break
    if remaining > max(0.01, notional_usdt * 1e-6) or base_filled <= 0:
        return None, quote_filled
    return quote_filled / base_filled, quote_filled


def estimate(symbol, *, notional_usdt=None, taker_fee_bps=None, venue=None, ua='ATLAS-Research/1.0', getter=_get_json):
    venue = str(venue if venue is not None else os.environ.get('ATLAS_EXECUTION_VENUE', '')).strip().upper()
    raw_fee = taker_fee_bps if taker_fee_bps is not None else os.environ.get('ATLAS_EXECUTION_TAKER_FEE_BPS')
    fee = _f(raw_fee)
    notional = _f(notional_usdt if notional_usdt is not None else os.environ.get('ATLAS_EXECUTION_RESEARCH_NOTIONAL_USDT', '1000'), 1000.0)
    if notional is None or notional <= 0:
        raise ValueError('execution research notional must be positive')

    inst = _inst_id(symbol)
    enc = urllib.parse.urlencode
    meta_obj = getter('https://www.okx.com/api/v5/public/instruments?' + enc({'instType': 'SWAP', 'instId': inst}), ua)
    book_obj = getter('https://www.okx.com/api/v5/market/books?' + enc({'instId': inst, 'sz': 100}), ua)
    meta = _first_data(meta_obj, 'instruments')
    book = _first_data(book_obj, 'books')

    base_per_contract, contract_basis = _contract_base_value(meta, symbol)
    bids, asks = _normalize_book(book)
    best_bid, best_ask = bids[0][0], asks[0][0]
    mid = (best_bid + best_ask) / 2.0
    full_spread_bps = ((best_ask - best_bid) / mid) * 10000.0 if mid > 0 else None
    half_spread_bps = full_spread_bps / 2.0 if full_spread_bps is not None else None

    buy_vwap = sell_vwap = None
    buy_filled = sell_filled = 0.0
    if base_per_contract is not None:
        buy_vwap, buy_filled = _vwap_for_quote(asks, notional, base_per_contract)
        sell_vwap, sell_filled = _vwap_for_quote(bids, notional, base_per_contract)

    buy_impact = ((buy_vwap / best_ask) - 1.0) * 10000.0 if buy_vwap is not None else None
    sell_impact = ((best_bid / sell_vwap) - 1.0) * 10000.0 if sell_vwap is not None and sell_vwap > 0 else None
    impact_values = [x for x in (buy_impact, sell_impact) if x is not None]
    one_way_slippage = sum(impact_values) / len(impact_values) if len(impact_values) == 2 else None

    depth_ok = bool(buy_vwap is not None and sell_vwap is not None)
    venue_ok = venue == SUPPORTED_VENUE
    fee_ok = fee is not None and fee >= 0
    contract_ok = base_per_contract is not None
    validated = bool(venue_ok and fee_ok and contract_ok and depth_ok and half_spread_bps is not None and one_way_slippage is not None)

    blockers = []
    if not venue_ok: blockers.append('EXECUTION_VENUE_NOT_CONFIGURED')
    if not fee_ok: blockers.append('TAKER_FEE_NOT_CONFIGURED')
    if not contract_ok: blockers.append(contract_basis)
    if not depth_ok: blockers.append('INSUFFICIENT_L2_DEPTH_FOR_NOTIONAL')

    return {
        'version': VERSION,
        'symbol': str(symbol).upper().replace('BINANCE:', ''),
        'venue': venue or None,
        'instrument': inst,
        'validated': validated,
        'blockers': blockers,
        'research_notional_usdt': round(notional, 2),
        # profit_engine expects per-side components; 2x these values equals the
        # estimated round-trip crossing/impact/fee cost.
        'spread_bps': round(half_spread_bps, 6) if half_spread_bps is not None else None,
        'fee_bps': round(fee, 6) if fee_ok else None,
        'slippage_bps': round(one_way_slippage, 6) if one_way_slippage is not None else None,
        'full_spread_bps': round(full_spread_bps, 6) if full_spread_bps is not None else None,
        'buy_vwap': buy_vwap,
        'sell_vwap': sell_vwap,
        'best_bid': best_bid,
        'best_ask': best_ask,
        'buy_quote_filled': round(buy_filled, 6),
        'sell_quote_filled': round(sell_filled, 6),
        'contract_base_value': base_per_contract,
        'contract_basis': contract_basis,
        'basis': 'LIVE_OKX_SWAP_L2_PLUS_CONFIGURED_TAKER_FEE',
        'live_execution': False,
        'research_only': True,
    }
