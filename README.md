# crypto-facilities

Crypto Facilities is a cryptcurrency derivatives exchange. This package is a Python client for the REST API of
the exchange. This is similar to the official client (https://github.com/CryptoFacilities/REST-v2-Python) except
that it implements V3 of the API rather than V2.

## Basic usage

```python
from crypto_facilities import APIKey, get_instruments, get_positions

# Unauthenticated access:
print(get_instruments())

# Authenticed methods require a key argument. You can generate one at
# https://www.cryptofacilities.com/derivatives/account#apiTab
key = APIKey('public', 'private')
print(get_positions(key))
```
