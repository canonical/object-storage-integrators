import pytest

from src.core.domain import S3ConnectionInfo
from src.managers.s3 import S3Manager


@pytest.mark.parametrize(
    "no_proxy_env, endpoint, expected",
    [
        # Exact hostname match
        ("example.com", "https://example.com", True),
        # Domain suffix match
        (".example.com", "https://sub.example.com", True),
        # Subdomain match
        ("example.com", "https://sub.example.com", True),
        # Host not in no_proxy
        ("example.com", "https://other.com", False),
        # IP exact match
        ("10.1.1.1", "https://10.1.1.1", True),
        # IP in CIDR
        ("10.0.0.0/8", "https://10.152.183.1", True),
        # IP outside CIDR
        ("10.0.0.0/8", "https://192.168.1.1", False),
        # Multiple entries in no_proxy
        ("127.0.0.1,example.com,10.0.0.0/8", "https://10.5.5.5", True),
        ("127.0.0.1,example.com,10.0.0.0/8", "https://192.168.1.1", False),
        # Empty no_proxy
        ("", "https://anything.com", False),
        # Localhost and loopback IPs
        ("127.0.0.1,localhost,::1", "http://127.0.0.1", True),
        ("127.0.0.1,localhost,::1", "http://localhost", True),
        ("127.0.0.1,localhost,::1", "http://[::1]", True),
        ("127.0.0.1,localhost,::1", "http://10.0.0.1", False),
        # Empty endpoint or missing hostname
        ("example.com", "", False),
        ("example.com", "file:///tmp/file.txt", False),
        # Wildcard subdomain edge
        (".example.com", "https://deep.sub.example.com", True),
        # Multiple domains / IPs with whitespace
        (" example.com , 10.0.0.0/8 ,localhost ", "https://10.12.34.56", True),
        (" example.com , 10.0.0.0/8 ,localhost ", "https://otherhost.com", False),
        # Invalid CIDR entries (should be ignored)
        ("10.0.0.0/8,invalid_cidr,example.com", "https://10.1.2.3", True),
        ("10.0.0.0/8,invalid_cidr,example.com", "https://notexample.com", False),
        # Endpoint with port number
        ("example.com", "https://example.com:8080/path", True),
        ("example.com", "https://other.com:443/path", False),
        # Mixed case domain (should be case-insensitive)
        ("EXAMPLE.COM", "https://example.com", True),
        ("EXAMPLE.COM", "https://Sub.Example.Com", True),
    ],
)
def test_skip_proxy(no_proxy_env, endpoint, expected, monkeypatch):
    # Patch JUJU_CHARM_NO_PROXY env var
    monkeypatch.setenv("JUJU_CHARM_NO_PROXY", no_proxy_env)
    s3_manager = S3Manager(conn_info=S3ConnectionInfo())
    assert s3_manager.skip_proxy(endpoint) == expected
