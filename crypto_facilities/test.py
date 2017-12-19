from hamcrest import *
from datetime import datetime, timedelta
from numbers import Number
import contextlib
import functools

import crypto_facilities

with open('read_write.key', 'r') as f:
	public, private = [x.strip() for x in f]
	key = crypto_facilities.APIKey(public, private)

def test_get_instruments():
	instruments = crypto_facilities.get_instruments()
	assert len(instruments) > 3

	i = [i for i in instruments if i['symbol'].startswith('fi_xbtusd_')][0]
	assert_that(i, has_entries({
		'contractSize': instance_of(int),
		'tradeable': instance_of(bool),
		'lastTradingTime': instance_of(datetime),
		'type': instance_of(str),
		'tickSize': instance_of(Number),
		'underlying': instance_of(str),
	}))

def test_get_tickers():
	tickers = crypto_facilities.get_tickers()
	assert len(tickers) > 3

	t = [t for t in tickers if t['symbol'].startswith('fi_xbtusd_')][0]
	assert_that(t, has_entries({
		'symbol': instance_of(str),
		'suspended': instance_of(bool),
		
		'last': instance_of(Number),
		'lastTime': instance_of(datetime),
		'lastSize': instance_of(int),

		'open24h': instance_of(Number),
		#'high24h': instance_of(Number),
		#'low24h': instance_of(Number),
		'vol24h': instance_of(int),

		'bid': instance_of(Number),
		'bidSize': instance_of(int),

		'ask': instance_of(Number),
		'askSize': instance_of(int),

		'markPrice': instance_of(Number),
	}))

ZERO_PRICE = 0
EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE  = 0.0001
EXAMPLE_SYMBOL_IMPOSSIBLY_HIGH_PRICE = 1e6
@functools.lru_cache()
def get_example_symbol():
	tickers = crypto_facilities.get_tickers()
	t = [t for t in tickers if t['symbol'].startswith('fi_xrpusd_') and not t['suspended']][0]

	for c in ('last', 'open24h', 'high24h', 'low24h', 'bid', 'ask', 'markPrice'):
		if c in t:
			assert EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE * 10 < t[c] < EXAMPLE_SYMBOL_IMPOSSIBLY_HIGH_PRICE / 10

	return t['symbol']

def test_get_order_book():
	ob = crypto_facilities.get_order_book(get_example_symbol())
	
	bids = ob.bids
	assert len(bids) > 2

	for bid in bids:
		assert len(bid) == 2
		price, size = bid
		
		assert_that(price, instance_of(Number))
		assert_that(size, instance_of(int))

	prices = [price for price, _size in bids]
	assert sorted(prices, reverse=True) == prices

def test_get_trade_history():
	ts = crypto_facilities.get_trade_history(get_example_symbol())
	
	for t in ts:
		assert_that(t, instance_of(crypto_facilities.Trade))
		assert_that(t.time, instance_of(datetime))
		assert_that(t.trade_id, instance_of(int))
		assert_that(t.price, instance_of(Number))
		assert_that(t.size, instance_of(int))

	times = [t.time for t in ts]
	assert sorted(times, reverse=True) == times

	if ts:
		earlier = times[0] - timedelta(seconds=1)
		ts_earlier = crypto_facilities.get_trade_history(get_example_symbol(), last_time=earlier)
		
		if not ts_earlier:
			assert len(ts) == 1
		else:
			assert 0 < len(ts_earlier) <= len(ts)
			assert ts_earlier[0].time <= earlier

def test_get_accounts():
	accts = crypto_facilities.get_accounts(key)
	
	assert 'cash' in accts
	assert_that(accts['cash'], has_entries({
		'type': instance_of(str),
		'balances': has_entries({
			'xbt': instance_of(Number),
			'xrp': instance_of(Number),	
		}),
	}))

	# e.g. fi_xbtusd
	fi_account = [acct for acct in accts if acct.startswith('fi_')][0]
	assert_that(accts[fi_account], has_entries({
		'type': instance_of(str),
		'currency': instance_of(str),
		'balances': has_entries({
			'xbt': instance_of(Number),
			'xrp': instance_of(Number),	
		}),
		# All in units of 'currency':
		'auxiliary': has_entries({
			'af': instance_of(Number), # Available Funds
			'pnl': instance_of(Number), # P&L of open positions
			'pv': instance_of(Number), # Portfolio value
		}),
		'marginRequirements': has_entries({
			'im': instance_of(Number), # Initial Margin
			'mm': instance_of(Number), # Maintenance Margin
			'lt': instance_of(Number), # Liquidation Threshold
			'tt': instance_of(Number), # Termination Threshold
		}),
		# Approximate underlying spot prices that will cause us to reach margin thresh:
		'triggerEstimates': has_entries({
			'im': instance_of(Number),
			'mm': instance_of(Number),
			'lt': instance_of(Number),
			'tt': instance_of(Number),
		}),
	}))

@contextlib.contextmanager
def ensure_cancelled(order_id):
	assert order_id is not None

	try:
		yield
	finally:
		cancel_status = crypto_facilities.cancel_order(key, order_id)
		assert cancel_status.status in {'cancelled', 'notFound'}

def assert_can_place_order(spec):
	size = 1
	status = crypto_facilities.send_order(key, spec, size)

	with ensure_cancelled(status.order_id):
		assert isinstance(status, crypto_facilities.OrderStatus)
		assert status.status == 'placed'

def test_send_limit_order():
	spec = crypto_facilities.LimitOrderSpec(get_example_symbol(), 'buy', EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE)
	assert_can_place_order(spec)

def test_send_stop_order():
	spec = crypto_facilities.StopOrderSpec(get_example_symbol(), 'buy', EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE * 2, EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE)
	assert_can_place_order(spec)

def test_can_send_bogus_order():
	status = crypto_facilities.send_limit_order(key, get_example_symbol(), 'buy', ZERO_PRICE, 1)
	assert status == crypto_facilities.OrderStatus(received_time=None, status='invalidPrice', order_id=None)

def test_can_batch_modify_orders():
	spec0 = crypto_facilities.LimitOrderSpec(get_example_symbol(), 'buy',  EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE)
	spec1 = crypto_facilities.LimitOrderSpec(get_example_symbol(), 'sell', EXAMPLE_SYMBOL_IMPOSSIBLY_HIGH_PRICE)

	size = 1
	status0 = crypto_facilities.send_order(key, spec0, size)
	with ensure_cancelled(status0.order_id):
		statuses = crypto_facilities.send_or_cancel_orders(key, [
			status0.order_id,
			(spec1, size)
		])
		try:
			assert len(statuses) == 2
			assert statuses[0].status == 'cancelled'
			assert statuses[1].status == 'placed'
		finally:
			cancel_status = [crypto_facilities.cancel_order(key, status.order_id).status for status in statuses if status.order_id is not None]
			assert_that(cancel_status, only_contains(is_in({'cancelled', 'notFound'})))
				
def test_get_open_orders():
	spec = crypto_facilities.LimitOrderSpec(get_example_symbol(), 'buy', EXAMPLE_SYMBOL_IMPOSSIBLY_LOW_PRICE)
	size = 1
	status = crypto_facilities.send_order(key, spec, size)

	with ensure_cancelled(status.order_id):
		open_orders = crypto_facilities.get_open_orders(key)
		assert len(open_orders) == 1
		
		oo, = open_orders
		assert_that(oo, instance_of(crypto_facilities.OpenOrder))
		assert oo.spec == spec
		assert oo.status.status == 'untouched'
		assert oo.filled_size == 0
		assert oo.unfilled_size == 1

def test_get_fill_history():
	fills = crypto_facilities.get_fill_history(key)
	for fill in fills:
		assert_that(fill, has_entries({
			'fillTime': instance_of(datetime),
			'order_id': instance_of(str),
			'fill_id': instance_of(str),
			'symbol': instance_of(str),
			'side': is_in({'sell', 'buy'}),
			'size': instance_of(int),
			'price': instance_of(Number),
		}))

	times = [fill['fillTime'] for fill in fills]
	assert sorted(times, reverse=True) == times

	if fills:
		earlier = times[0] - timedelta(seconds=1)
		earlier_fills = crypto_facilities.get_fill_history(key, last_time=earlier)

		if not earlier_fills:
			assert len(fills) == 1
		else:
			assert 0 < len(earlier_fills) <= len(fills)
			assert earlier_fills[0]['fillTime'] <= earlier

def test_get_positions():
	positions = crypto_facilities.get_positions(key)
	for pos in positions:
		assert_that(pos, has_entries({
			'fillTime': instance_of(datetime),
			'symbol': instance_of(str),
			'side': is_in({'sell', 'buy'}),
			'size': instance_of(int),
			'price': instance_of(Number),
		}))

def test_withdraw():
	# XXX: any way to test this without actually making a transaction..?
	# Crypto Facilities don't seem to operate a testnet or anything
	assert True

def test_get_transfer_history():
	history = crypto_facilities.get_transfer_history(key)
	for h in history:
		assert_that(h, instance_of(crypto_facilities.Transfer))

		assert_that(h.money, instance_of(crypto_facilities.Money))
		assert_that(h.money.currency, instance_of(str))
		assert_that(h.money.amount, instance_of(Number))
		assert_that(h.money.amount, greater_than(0))
		
		assert_that(h.target_address, any_of(instance_of(str), none()))
		assert_that(h.status, instance_of(crypto_facilities.TransferStatus))
		assert_that(h.status.received_time, instance_of(datetime))
		assert_that(h.status.status, instance_of(str))
		assert_that(h.status.transfer_id, instance_of(str))

		assert_that(h.completed_time, instance_of(datetime))
		assert_that(h.transaction_id, instance_of(str))

	times = [h.status.received_time for h in history]
	assert sorted(times, reverse=True) == times

	if history:
		earlier = times[0] - timedelta(seconds=1)
		earlier_history = crypto_facilities.get_transfer_history(key, last_time=earlier)
		
		if not earlier_history:
			assert len(history) == 1
		else:
			assert 0 < len(earlier_history) <= len(history)
			assert earlier_history[0].time <= earlier
