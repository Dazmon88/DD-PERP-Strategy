> ## Documentation Index
> Fetch the complete documentation index at: https://docs.ondoperps.xyz/llms.txt
> Use this file to discover all available pages before exploring further.

# API Key Authentication

> Example of how to use API keys

## Generating an API Key

To generate an API Key

1. Sign into your account with a web browser
2. Click on your address in the upper right corner
3. Click **API Keys**
4. Click **Add New API Key**
5. Name the key
6. Select the correct permissions
7. Click **Create API Key**
8. Record the secret key

<Warning>
  The secret key should be treated the same way as a password and not stored in an unencrypted manner. Place it in a password manager or key vault.
</Warning>

### IP Whitelisting

It is strongly recommended to whitelist the IP addresses which are allowed to make requests for the given API key.

Up to 16 IP addresses can be added per API key. Only IPv4 addresses are supported at this time.

The default state with no whitelisted addresses (empty whitelist) is to allow requests from any IP. If there are addresses on the whitelist, then only requests from the whitelisted IPs are allowed. Requests from IPs not on the whitelist will error with code 401 and message: `"IP addr x.x.x.x is not allowed for key ondoKeyId_yyyyyyyy"`.

## Making an Authenticated REST Request

Authenticated REST requests need the following headers:

* `ONDO-KEY-ID` The key id (including the "ondoKeyId\_" prefix)
* `ONDO-TIMESTAMP` Number of milliseconds since the Unix epoch, this must be within 30 seconds of the time the request is received.
* `ONDO-SIGN` hex representation of SHA256 HMAC of the following four strings concatenated together using the API Secret (including the "ondoApiSecret\_" prefix).
  * `timestamp` identical to the ONDO-TIMESTAMP header
  * `method` HTTP method in uppercase
  * `requestPath` full path and query parameters of the URL, excluding the hostname
  * `body` request body string

## Error Codes

Requests made through API key authentication can fail with the following error codes:

* `api_key_not_found` — The API key provided could not be found.
* `failed_to_parse_timestamp` — The timestamp provided could not be parsed.
* `timestamp_too_far` — The timestamp is too far from the server timestamp (more than 30 seconds in the past or future)
* `failed_to_decode_hex_signature` — The hex signature could not be decoded.
* `signature_mismatch` — There is a mismatch in the signature.
* `key_doesnt_have_scope` — The API key does not have the required scope for the endpoint.
* `ip_not_permitted` — The IP address making the request is not whitelisted for this API key.

## Example in Go

```go theme={null}
package main
import (
  "crypto/hmac"
  "crypto/sha256"
  "encoding/hex"
  "fmt"
  "io"
  "net/http"
  "strings"
  "time"
)
func main() {
  keyId := "ondoKeyId_KEYID"
  apiSecret := "ondoApiSecret_SECRET"
  method := "GET"
  base := "https://api.ondoperps.xyz"
  path := "/v1/perps/orders?market=AAPL-USD.P&limit=1000"
  body := ""
  req, _ := http.NewRequest(method, base+path, strings.NewReader(body))
  timestamp := fmt.Sprintf("%d", time.Now().UnixMilli())
  // Ensure path contains query params `?market=AVAX-USDC&limit=1000`.
  concattedString := timestamp + method + path + body
  mac := hmac.New(sha256.New, []byte(apiSecret))
  mac.Write([]byte(concattedString))
  sig := mac.Sum(nil)
  req.Header.Set("ONDO-KEY-ID", keyId)
  req.Header.Set("ONDO-TIMESTAMP", timestamp)
  req.Header.Set("ONDO-SIGN", hex.EncodeToString(sig))
  res, err := http.DefaultClient.Do(req)
  if err != nil {
    fmt.Printf("http err: %s", err)
    return
  }
  data, _ := io.ReadAll(res.Body)
  fmt.Printf("Status: %s, Body: %s", res.Status, data)
}
```

Note: in Go, `req.URL.RequestURI()` contains the query parameters and should be used, whereas `req.URL.Path` does not.

## Example in Python

```python theme={null}
import hmac
import hashlib
import time
import requests

key_id = "ondoKeyId_KEYID"
api_secret = "ondoApiSecret_SECRET"
method = "GET"
base = "https://api.ondoperps.xyz"
path = "/v1/perps/orders?market=AAPL-USD.P&limit=1000"
body = ""

url = base + path
timestamp = str(int(time.time() * 1000))
# Ensure path contains query params `?market=AAPL-USD.P&limit=1000`
concatted_string = timestamp + method + path + body
mac = hmac.new(api_secret.encode(), concatted_string.encode(), hashlib.sha256)
signature = mac.hexdigest()

headers = {
    "ONDO-KEY-ID": key_id,
    "ONDO-TIMESTAMP": timestamp,
    "ONDO-SIGN": signature
}

response = requests.get(url, headers=headers)

print(f"Status: {response.status_code}, Body: {response.text}")
```
