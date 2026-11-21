import pytest

from app.netguard import is_local


@pytest.mark.parametrize(
    "host,expected",
    [
        ("192.168.1.5", True), ("10.0.0.2", True), ("172.16.5.5", True), ("127.0.0.1", True), ("::1", True),
        ("169.254.1.1", True), ("8.8.8.8", False), ("172.32.0.1", False), ("::ffff:192.168.1.5", True),
        ("::ffff:8.8.8.8", False), ("testclient", True), (None, True),
    ],
)
def test_is_local(host, expected):
    assert is_local(host) is expected
