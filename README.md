# crypto-facilities

Crypto Facilities is a cryptcurrency derivatives exchange. This package is a Python client for the REST API of
the exchange. This is similar to the official client (https://github.com/CryptoFacilities/REST-v2-Python) except
that it implements V3 of the API rather than V2.

Disclaimer: I haven't used this too seriously yet "in production", but it does have
extensive tests.

## Basic usage

```python
from crypto_facilities import APIKey, get_instruments, get_positions

# Unauthenticated access:
print(get_instruments())

# Authenticated methods require a key argument. You can generate one at
# https://www.cryptofacilities.com/derivatives/account#apiTab
key = APIKey('public', 'private')
print(get_positions(key))
```

## Rate limits

API calls are limited to 1 call every 0.1 seconds per IP address. If this is exceeded
you will start getting exceptions from the API, so if you are going to use the API
heavily you might to implement your own rate limiting to keep below this threshold.
