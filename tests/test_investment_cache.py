import time
from src.analysis.investment_analyzer import _cache_key, _is_cache_valid


def test_cache_key_stable_for_same_titles():
    titles = ["Bitcoin rises", "Gold falls", "Fed hikes rate"]
    assert _cache_key(titles) == _cache_key(titles)


def test_cache_key_different_for_different_titles():
    assert _cache_key(["Bitcoin"]) != _cache_key(["Gold"])


def test_cache_valid_within_hours():
    entry = {"timestamp": time.time() - 3600}
    assert _is_cache_valid(entry, cache_hours=6) is True


def test_cache_invalid_after_hours():
    entry = {"timestamp": time.time() - 7 * 3600}
    assert _is_cache_valid(entry, cache_hours=6) is False


def test_cache_key_ignores_minor_tail_changes():
    """Top-20 titles giống nhau → cache key giống nhau."""
    base_titles = [f"Title {i}" for i in range(20)]
    titles_a = base_titles + ["Extra A"]
    titles_b = base_titles + ["Extra B", "Extra C"]
    assert _cache_key(titles_a) == _cache_key(titles_b)
