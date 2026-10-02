"""Public HTTPS custom endpoints, pinned DNS and no credential-bearing redirects."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

def validate_url(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Invalid HTTPS base URL.') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
        or port not in (None, 443) or parsed.query or parsed.fragment):
        raise ValueError('Use a public HTTPS base URL without credentials, query or fragment.')
    host = parsed.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.localhost', '.internal')):
        raise ValueError('Private endpoints are not supported.')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('Private endpoints are not supported.')
    except ValueError as exc:
        if 'Private endpoints' in str(exc):
            raise
    return value.rstrip('/')

class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Endpoint resolves to a private address.')
        self.sock = socket.create_connection((addresses[0][4][0], 443), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)

class Response:
    def __init__(self, connection, response):
        self.connection, self.response = connection, response
    def __enter__(self): return self
    def __exit__(self, *args):
        self.response.close()
        self.connection.close()
    def read(self):
        data = self.response.read(2_000_001)
        if len(data) > 2_000_000: raise ValueError('Provider response exceeds size limit.')
        return data

def public_https_open(request, timeout):
    validate_url(request.full_url)
    url = urlsplit(request.full_url)
    conn = PinnedHTTPS(url.hostname, timeout=timeout, context=ssl.create_default_context())
    try:
        conn.request(request.get_method(), url.path or '/', request.data, dict(request.header_items()))
        response = conn.getresponse()
        if response.status < 200 or response.status >= 300:
            raise ProviderHTTPError(response.status)
        return Response(conn, response)
    except Exception:
        conn.close()
        raise

class ProviderHTTPError(Exception):
    def __init__(self, status): self.status = status
