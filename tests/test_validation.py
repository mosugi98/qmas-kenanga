import pytest

from app.validation import normalize_kadar


@pytest.mark.parametrize("raw,expected", [("22k", "22K"), (" 24K ", "24K"), ("9K", "9K")])
def test_kadar_valid(raw, expected):
    assert normalize_kadar(raw) == expected


@pytest.mark.parametrize("raw", ["", "K", "abc", "22", "240K"])
def test_kadar_tidak_valid(raw):
    with pytest.raises(ValueError):
        normalize_kadar(raw)
