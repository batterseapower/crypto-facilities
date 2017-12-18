import collections
import datetime
import time
import requests
import base64
import hashlib
import hmac
import json
from typing import List, Tuple, Union

# API calls are limited to 1 call every 0.1 seconds per IP address. If the API limit is
# exceeded, the API will return error equal to apiLimitExeeded.

APIKey = collections.namedtuple('APIKey', 'public private')
BASE_URL = 'https://www.cryptofacilities.com/derivatives'
API_VERSION = '/api/v3/'

def parse_time(s: str) -> datetime.datetime:
    # e.g. 2016-02-25T09:45:53.818Z
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%fZ')

def format_time(t: datetime.datetime) -> str:
    millisecond = t.microsecond // 1000
    return t.strftime('%Y-%m-%dT%H:%M:%S.') + '{0:3}'.format(millisecond) + 'Z'

next_nonce = int(time.time() * 1000000)
def make_request(path, data=[], method='GET', key=None):
    global next_nonce

    if key is None:
        headers = {}
    else:
        post_data = '&'.join(k + '=' + v for k, v in data)

        nonce = str(next_nonce)
        next_nonce += 1

        headers = {
            'APIKey': key.public,
            'Nonce': nonce,
            'Authent': get_auth_ent(post_data, nonce, API_VERSION + path, key.private),
        }

    url = BASE_URL + API_VERSION + path
    
    if method == 'GET':
        r = requests.get(url, headers=headers, params=collections.OrderedDict(data))
    else:
        r = requests.post(url, headers=headers, data=collections.OrderedDict(data))
    
    r.raise_for_status()

    r = r.json()
    result = r.pop('result')
    if result == 'success':
        return r
    else:
        assert result == 'error'
        raise ValueError(r.get('error', 'unspecifiedError'))


def get_auth_ent(post_data, nonce, endpoint, private_key):
    message = post_data + nonce + endpoint

    sha256_hash = hashlib.sha256()
    sha256_hash.update(message.encode('utf8'))
    hash_digest = sha256_hash.digest()
    
    secret = base64.b64decode(private_key)
    
    hmac_digest = hmac.new(secret, hash_digest, hashlib.sha512).digest()
    return base64.b64encode(hmac_digest)

def parse_time_fields(fields, xs):
    result = []
    for x in xs:
        x = x.copy()
        result.append(x)

        for field in fields:
            if field in x:
                x[field] = parse_time(x[field])

    return result

# {
#   "symbol": "fi_xbtusd_180615",
#   "type”: “futures_inverse”,
#   “tradeable”: “true”,
#   “underlying”: “rr_xbtusd”,
#   “lastTradingTime”: “2018-06-15T16:00:00.000Z",
#   "tickSize": 1,
#   "contractSize”: 1,
# },
def get_instruments():
    result = make_request('instruments')['instruments']
    return parse_time_fields(['lastTradingTime'], result)

# {
#   "symbol": "fi_xbtusd_180615",
#   "suspended": false,
#   "last": 4232,
#   "lastTime": "2016-02-25T10:56:10.364Z",
#   "lastSize": 5000,
#   "open24h": 4418,
#   "high24h": 4265,
#   "low24h": 4169,
#   "vol24h": 112000,
#   "bid": 4232,
#   "bidSize": 5000,
#   "ask": 4236,
#   "askSize": 5000,
#   "markPrice": 4227,
# },
def get_tickers():
    result = make_request('tickers')['tickers']
    return parse_time_fields(['lastTime'], result)

# {
#   “bids”: [
#     [4213, 2000],
#     [4210, 4000],
#     ...,
#   ],
#   “asks”: [
#     [4218, 4000],
#     [4220, 5000],
#     ...,
#   ],
# },
#
# Arrays are [price, size]. Bids have descending price, asks have ascending price.
def get_order_book(symbol: str):
    return make_request('orderbook', data=[('symbol', symbol)])['orderBook']

# [
#   {
#     “time”: “2016-02-23T10:10:01.000Z”,
#     “trade_id”: 865,
#     “price”: 4322,
#     “size”: 5000,
#   },
#   {
#     “time”: “2016-02-23T10:05:12.000Z”,
#     “trade_id”: 864,
#     “price”: 4324,
#     “size”: 2000,
#   },
#   ...,
# ],
#
# Always returns <= 100 entries
def get_trade_history(symbol: str, last_time: datetime.datetime = None):
    data = [('symbol', symbol)]
    if last_time is not None:
        data.append(('lastTime', format_time(last_time)))

    result = make_request('history', data=data)['history']
    return parse_time_fields(['time'], result)

# {
#   “cash”: {
#     “type”: “cashAccount”,
#     “balances”: {
#       “xbt”: 141.31756797,
#       “xrp”: 52465.1254,
#     },
#   },
#   “fi_xbtusd”: {
#     “type”: “marginAccount”,
#     “currency”: “xbt”,
#     “balances”: {
#       “fi_xbtusd_171215”: 50000,
#       “fi_xbtusd_180615”: -15000,
#       ...,
#       “xbt”: 141.31756797,
#       “xrp”: 0,
#     },
#     “auxiliary”: {
#       “af”: 100.73891563,
#       “pnl”: 12.42134766,
#       “pv”: 153.73891563,
#     },
#     “marginRequirements”:{
#       “im”: 52.8,
#       “mm”: 23.76,
#       “lt”: 39.6,
#       “tt”: 15.84,
#     },
#     “triggerEstimates”:{
#       “im”: 3110,
#       “mm”: 3000,
#       “lt”: 2890,
#       “tt”: 2830,
#     },
#   },
#   ...
# },
def get_accounts(key: APIKey):
    return make_request('accounts', key=key)['accounts']

LimitOrderSpec = collections.namedtuple('LimitOrderSpec', 'symbol side price')
StopOrderSpec  = collections.namedtuple('StopOrderSpec',  'symbol side limit_price stop_price')
OrderSpec = Union[LimitOrderSpec, StopOrderSpec]

def _get_order_entry_data(order: OrderSpec, size: int):
    data = [('symbol', order.symbol), ('side', order.side), ('size', str(size))]
    if isinstance(order, LimitOrderSpec):
        data = [('orderType', 'lmt')] + data + [('limitPrice', str(order.price))]
    elif isinstance(order, StopOrderSpec):
        data = [('orderType', 'stp')] + data + [('limitPrice', str(order.limit_price)), ('stopPrice', str(order.stop_price))]
    else:
        raise ValueError(str(type(order)))

    return data

def _get_order_spec(struct: dict) -> OrderSpec:
    symbol = struct['symbol']
    
    side = struct['side']
    assert side in ('buy', 'sell')

    limit_price = float(struct['limitPrice'])

    typ = struct['orderType']
    if typ == 'lmt':
        assert struct.get('stopPrice') is None
        return LimitOrderSpec(symbol, side, limit_price)
    elif typ == 'stp':
        stop_price = float(struct['stopPrice'])
        return StopOrderSpec(symbol, side, limit_price, stop_price)
    else:
        raise ValueError('Unknown order type ' + typ)

OrderStatus = collections.namedtuple('OrderStatus', 'received_time status order_id')

def _get_order_status(struct: dict, order_id: str = None) -> OrderStatus:
    if order_id is None:
        # Can be missing if placing the order failed
        order_id = struct.get('order_id')
    else:
        assert 'order_id' not in struct or struct['order_id'] == order_id

    return OrderStatus(
        # Time can be missing if e.g. the order fully filled immediately
        received_time=None if 'receivedTime' not in struct else parse_time(struct['receivedTime']),
        status=struct['status'],
        order_id=order_id
    )

def send_order(key: APIKey, order: OrderSpec, size: int) -> OrderStatus:
    data = _get_order_entry_data(order, size)
    result = make_request('sendorder', data=data, method='POST', key=key)['sendStatus']
    return _get_order_status(result)

# {
#   “receivedTime”: “2016-02-25T09:45:53.601Z”,
#   “status”: “placed”,
#   “order_id”: “c18f0c17-9971-40e6-8e5b-10df05d422f0”,
# }
def send_limit_order(key: APIKey, symbol: str, side: Union['buy', 'sell'], price: float, size: int) -> OrderStatus:
    return send_order(key, LimitOrderSpec(symbol, side, price), size)

def send_stop_order(key: APIKey, symbol: str, side: Union['buy', 'sell'], limit_price: float, stop_price: float, size: int) -> OrderStatus:
    return send_order(key, StopOrderSpec(symbol, side, limit_price, stop_price), size, key=key)

# {
#   “receivedTime”: “2016-02-25T09:45:53.601Z”,
#   “status”: “cancelled”,
# }
def cancel_order(key: APIKey, order_id: str) -> OrderStatus:
    result = make_request('cancelorder', data=[('order_id', order_id)], method='POST', key=key)['cancelStatus']
    return _get_order_status(result, order_id=order_id)

# Strings supplied here will be interpreted as requests to cancellation the corresponding
# order ID. Orders will be intepreted as requests to place that order.
def send_or_cancel_orders(key: APIKey, instructions: List[Union[str, Tuple[OrderSpec, int]]]) -> List[OrderStatus]:
    instruction_structs = []
    order_id_to_ixs = {}
    for i, instruction in enumerate(instructions):
        if isinstance(instruction, str):
            instruction_struct = {
                'order': 'cancel',
                'order_id': instruction
            }
            order_id_to_ixs.setdefault(instruction, []).append(i)
        else:
            spec, size = instruction
            instruction_struct = dict(_get_order_entry_data(spec, size))
            instruction_struct['order'] = 'send'
            instruction_struct['order_tag'] = str(i)
        instruction_structs.append(instruction_struct)

    result = make_request('batchorder', data=[('json', json.dumps({'batchOrder': instruction_structs}))], method='POST', key=key)['batchStatus']
    
    statuses = [None] * len(instruction_structs)
    for result_struct in result:
        if 'order_tag' in result_struct:
            ixs = [int(result_struct['order_tag'])]
            status = _get_order_status(result_struct)
            assert not any(isinstance(instructions[i], str) for i in ixs)
        else:
            order_id = result_struct['order_id']
            ixs = order_id_to_ixs[order_id]
            status = _get_order_status(result_struct, order_id=order_id)
            
        for i in ixs:
            assert statuses[i] is None
            statuses[i] = status

    assert [x for x in statuses if x is None] == []
    return statuses

OpenOrder = collections.namedtuple('OpenOrder', 'spec status filled_size unfilled_size')

def get_open_orders(key: APIKey) -> List[OpenOrder]:
    orders = []
    for record in make_request('openorders', key=key)['openOrders']:
        spec = _get_order_spec(record)
        status = _get_order_status(record)
        unfilled_size = int(record['unfilledSize'])
        filled_size = int(record['filledSize'])

        orders.append(OpenOrder(spec, status, filled_size, unfilled_size))

    return orders

# {
#   “result”: “success”,
#   “serverTime”: “2016-02-25T09:45:53.818Z”,
#   “fills”: [
#     {
#     “fillTime”: “2016-02-25T09:47:01.000Z”,
#     “order_id”: “c18f0c17-9971-40e6-8e5b-10df05d422f0”,
#     “fill_id”: “522d4e08-96e7-4b44-9694-bfaea8fe215e”,
#     “symbol”: “fi_xbtusd_180615”,
#     “side”: ”buy”,
#     “size”: 2000,
#     “price”: 4255,
#     },
#     ...
#   }
# }
#
# Always returns <= 100 entries
def get_fill_history(key: APIKey, last_time: datetime.datetime = None):
    data = []
    if last_time is not None:
        data.append(('lastFillTime', format_time(last_time)))

    result = make_request('fills', data=data, key=key)['fills']
    return parse_time_fields(['fillTime'], result)

# [
#   {
#     “fillTime”: “2016-02-25T09:47:01.000Z”,
#     “symbol”: “fi_xbtusd_180615”,
#     “side”: ”long”,
#     “size”: 1000,
#     “price”: 4255,
#   },
#   {
#     “fillTime”: “2016-02-25T09:47:01.000Z”,
#     “symbol”: “fi_xbtusd_180615”,
#     “side”: ”buy”,
#     “size”: 1000,
#     “price”: 4255,
#   },
#   ...,
# ]
def get_positions(key: APIKey):
    result = make_request('openpositions', key=key)['openPositions']
    return parse_time_fields(['fillTime'], result)

# {
#   “receivedTime”: “2016-02-25T09:47:01.000Z”,
#   “status”: “accepted”,
#   “transfer_id”: “b243cf7a-657d-488e-ab1c-cfb0f95362ba”,
# }
def withdraw(key: APIKey, target_address: str, currency: Union['xbt', 'xrp'], amount: float):
    data = [('targetAddress', target_address), ('currency', currency), ('amount', amount)]
    result = make_request('withdrawal', data=data, method='POST', key=key)
    result, = parse_time_fields(['receivedTime'], [result])
    return result

# [
#   {
#     “receivedTime”: “2016-01-28T07:09:42.000Z”,
#     “completedTime”: “2016-01-28T08:26:46.000Z”,
#     “status”: “processed”,
#     “transfer_id”:
#     “b243cf7a-657d-488e-ab1c-cfb0f95362ba”,
#     “transaction_id”: “4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b”,
#     “targetAddress”: “1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa”,
#     “transferType”: “deposit”
#     “currency”: “xbt”,
#     “amount”: 2.58,
#   },
#   ...
# ]
def get_transfer_history(key: APIKey, last_time: datetime.datetime = None):
    data = []
    if last_time is not None:
        data.append(('lastTransferTime', format_time(last_time)))

    result = make_request('transfers', data=data, key=key)['transfers']
    return parse_time_fields(['receivedTime', 'completedTime'], result)
