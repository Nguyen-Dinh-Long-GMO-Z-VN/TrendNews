"""
Tests cho các feature mới port từ upstream:
- frequency_words parser: regex /p/, => alias, [group], @N, # comment, sections
- dedup: normalize, exact/URL/fuzzy merge xuyên nguồn, source_count
- translator: numbered batch parse, vi-skip, cache
- ai_filter: extract tags, classify parse
- ai_client: env-prefix resolution
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.processors.frequency_words import load_frequency_words, _word_matches
from src.processors.statistics import matches_word_groups, count_word_frequency
from src.processors.dedup import (
    normalize_title,
    normalize_url,
    deduplicate_results,
)
from src.analysis.translator import TitleTranslator
from src.analysis.ai_filter import AIInterestsFilter
from src.analysis.ai_client import AIClient


# ────────────────────────── frequency_words ──────────────────────────

FREQ_CONTENT = """# comment thật — bị bỏ qua
[AI News]
/\\bai\\b/ => AI chung
ChatGPT
OpenAI

[Rust Lang]
+rust
cargo
crate

[Limited]
@3
startup
unicorn

[GLOBAL_FILTER]
bóng đá
/xổ số|lottery/i

[WORD_GROUPS]

[Crypto]
bitcoin
"""


@pytest.fixture
def freq_groups(tmp_path):
    f = tmp_path / "freq.txt"
    f.write_text(FREQ_CONTENT, encoding="utf-8")
    return load_frequency_words(str(f))


def test_parser_groups_and_filters(freq_groups):
    groups, filters = freq_groups
    assert len(groups) == 4
    assert len(filters) == 2
    names = [g["display_name"] for g in groups]
    assert names == ["AI News", "Rust Lang", "Limited", "Crypto"]


def test_parser_regex_word(freq_groups):
    groups, _ = freq_groups
    regex_word = groups[0]["normal"][0]
    assert regex_word["is_regex"] is True
    assert regex_word["display_name"] == "AI chung"


def test_parser_max_count(freq_groups):
    groups, _ = freq_groups
    assert groups[2]["max_count"] == 3
    assert groups[0]["max_count"] == 0


@pytest.mark.parametrize(
    "title,expected",
    [
        ("New AI model released", True),      # regex \bai\b
        ("AI is everywhere", True),
        ("Britain signs deal", False),        # ai in Britain — không khớp
        ("OpenAI launches product", True),
        ("Rust cargo 1.80 out", True),        # +rust AND cargo
        ("Rust in peace my friend", False),   # thiếu required context
        ("Startup raises money", True),
        ("Startup và bóng đá", False),        # global filter
        ("Trúng xổ số độc đắc", False),       # regex filter
        ("Bitcoin hits 100k", True),
    ],
)
def test_matches_word_groups(freq_groups, title, expected):
    groups, filters = freq_groups
    assert matches_word_groups(title, groups, filters) == expected


def test_matches_legacy_string_groups():
    """Backward compat: group words dạng str thuần vẫn match substring."""
    groups = [{"required": [], "normal": ["python"], "group_key": "python"}]
    assert matches_word_groups("Python 3.14 released", groups, []) is True
    assert matches_word_groups("Java released", groups, []) is False


def test_empty_groups_matches_all():
    assert matches_word_groups("anything", [], []) is True


def test_count_word_frequency_display_and_limit():
    """count_word_frequency dùng display_name + cắt theo @N."""
    groups = [
        {
            "required": [],
            "normal": [{"word": "openai", "is_regex": False, "pattern": None, "display_name": None}],
            "group_key": "openai",
            "display_name": "AI News",
            "max_count": 2,
        }
    ]
    results = {
        "src1": {
            f"OpenAI news {i}": {"ranks": [i + 1], "url": "", "mobileUrl": ""}
            for i in range(5)
        }
    }
    stats, total = count_word_frequency(results, groups, [], {"src1": "Nguồn 1"})
    assert len(stats) == 1
    assert stats[0]["word"] == "AI News"
    assert stats[0]["count"] == 5
    assert len(stats[0]["titles"]) == 2  # @2 giới hạn


# ────────────────────────── dedup ──────────────────────────

def test_normalize_title():
    assert normalize_title("OpenAI ra mắt GPT-5!") == "openai ra mắt gpt 5"
    assert normalize_title("  Cùng   Một   Tin  ") == "cùng một tin"
    assert normalize_title("") == ""


def test_normalize_url():
    assert (
        normalize_url("https://a.com/x?utm_source=rss&id=1#frag/")
        == "https://a.com/x?id=1"
    )


def _mk_results():
    return {
        "vnexpress": {
            "OpenAI ra mắt GPT-5": {"ranks": [1], "url": "https://a.com/1", "mobileUrl": ""},
            "Nvidia stock rises": {"ranks": [2], "url": "https://b.com/2", "mobileUrl": ""},
        },
        "tuoitre": {
            "OpenAI ra mắt GPT-5!": {"ranks": [5], "url": "https://c.com/1", "mobileUrl": ""},
            "Tin hoàn toàn khác": {"ranks": [1], "url": "", "mobileUrl": ""},
        },
    }


def _mk_title_info():
    return {
        "vnexpress": {
            "OpenAI ra mắt GPT-5": {
                "first_time": "0900", "last_time": "1000", "count": 2,
                "ranks": [1], "url": "https://a.com/1", "mobileUrl": "",
            },
            "Nvidia stock rises": {
                "first_time": "0900", "last_time": "0900", "count": 1,
                "ranks": [2], "url": "https://b.com/2", "mobileUrl": "",
            },
        },
        "tuoitre": {
            "OpenAI ra mắt GPT-5!": {
                "first_time": "0930", "last_time": "1100", "count": 1,
                "ranks": [5], "url": "https://c.com/1", "mobileUrl": "",
            },
            "Tin hoàn toàn khác": {
                "first_time": "0930", "last_time": "0930", "count": 1,
                "ranks": [1], "url": "", "mobileUrl": "",
            },
        },
    }


def test_dedup_cross_source_merge():
    results = _mk_results()
    info = _mk_title_info()
    new_titles = {"tuoitre": {"OpenAI ra mắt GPT-5!": {}}}

    stats = deduplicate_results(results, info, new_titles)

    assert stats["merged"] == 1
    # Canonical = vnexpress (rank 1 < 5)
    canon = None
    for src, titles in results.items():
        for t, d in titles.items():
            if "GPT-5" in t:
                canon = (src, t, d)
    assert canon is not None
    src, title, data = canon
    assert src == "vnexpress"
    assert data["source_count"] == 2
    assert set(data["sources"]) == {"vnexpress", "tuoitre"}
    assert min(data["ranks"]) == 1
    # title_info merged: first min, last max, count sum
    ti = info["vnexpress"][title]
    assert ti["first_time"] == "0900"
    assert ti["last_time"] == "1100"
    assert ti["count"] == 3
    # new_titles remapped to canonical
    assert title in new_titles.get("vnexpress", {})
    assert "OpenAI ra mắt GPT-5!" not in new_titles.get("tuoitre", {})


def test_dedup_no_false_merge():
    results = _mk_results()
    info = _mk_title_info()
    stats = deduplicate_results(results, info)
    # "Nvidia stock rises" và "Tin hoàn toàn khác" không bị gộp
    assert stats["merged"] == 1  # chỉ cụm GPT-5
    total_titles = sum(len(t) for t in results.values())
    assert total_titles == 3


def test_dedup_same_url_merge():
    results = {
        "a": {"Title A version": {"ranks": [1], "url": "https://x.com/p?utm_source=rss", "mobileUrl": ""}},
        "b": {"Title B different": {"ranks": [2], "url": "https://x.com/p", "mobileUrl": ""}},
    }
    info = {}
    stats = deduplicate_results(results, info)
    assert stats["merged"] == 1


# ────────────────────────── translator ──────────────────────────

def _mock_client(responses):
    client = MagicMock(spec=AIClient)
    client.is_configured.return_value = True
    client.complete.side_effect = responses
    return client


def test_translator_numbered_parse():
    parsed = TitleTranslator._parse_numbered(
        "[1] Bản dịch một\n[2] Bản dịch hai\nphụ đề của hai\n[3] Bản dịch ba",
        3,
    )
    assert parsed[0] == "Bản dịch một"
    assert "Bản dịch hai" in parsed[1]
    assert parsed[2] == "Bản dịch ba"


def test_translator_numbered_parse_missing_index():
    # AI sót số 2 → vị trí 2 rỗng, không lệch
    parsed = TitleTranslator._parse_numbered("[1] A\n[3] C", 3)
    assert parsed == ["A", "", "C"]


def test_translator_skips_vietnamese_and_uses_cache(tmp_path):
    cache = tmp_path / "cache.json"
    tr = TitleTranslator(
        _mock_client([]),
        {"ENABLED": True, "CACHE_FILE": str(cache), "BATCH_DELAY": 0},
    )
    vi_title = "OpenAI ra mắt mô hình mới"   # có 'mô' → detect tiếng Việt
    result = tr.translate_map([vi_title])
    assert result[vi_title] == vi_title
    tr.client.complete.assert_not_called()


def test_translator_batch_and_cache(tmp_path):
    cache = tmp_path / "cache.json"
    tr = TitleTranslator(
        _mock_client(["[1] Tin một đã dịch\n[2] Tin hai đã dịch"]),
        {"ENABLED": True, "CACHE_FILE": str(cache), "BATCH_DELAY": 0},
    )
    titles = ["Title one", "Title two"]
    result = tr.translate_map(titles)
    assert result["Title one"] == "Tin một đã dịch"
    assert result["Title two"] == "Tin hai đã dịch"

    # Lần 2: từ cache, không gọi AI
    tr.client.complete.side_effect = []
    tr.client.complete.reset_mock()
    result2 = tr.translate_map(titles)
    assert result2["Title one"] == "Tin một đã dịch"
    tr.client.complete.assert_not_called()


def test_translator_failure_keeps_original(tmp_path):
    cache = tmp_path / "cache.json"
    client = _mock_client([])
    client.complete.side_effect = RuntimeError("API down")
    tr = TitleTranslator(
        client,
        {"ENABLED": True, "CACHE_FILE": str(cache), "BATCH_DELAY": 0, "MAX_RETRIES": 0},
    )
    result = tr.translate_map(["Some title"])
    assert "Some title" not in result  # lỗi → caller giữ nguyên gốc


def test_translator_disabled():
    tr = TitleTranslator(_mock_client([]), {"ENABLED": False})
    assert tr.translate_map(["x"]) == {}


# ────────────────────────── ai_filter ──────────────────────────

def test_ai_filter_extract_tags(tmp_path):
    interests = tmp_path / "interests.txt"
    interests.write_text("1. AI models\n2. Chips", encoding="utf-8")
    client = _mock_client(
        ['{"tags": [{"tag": "AI", "description": "models"}, {"tag": "Chips", "description": "semis"}]}']
    )
    f = AIInterestsFilter(
        client,
        {
            "INTERESTS_FILE": str(interests),
            "CRITERIA_CACHE_FILE": str(tmp_path / "crit.json"),
        },
    )
    tags = f.extract_tags(interests.read_text())
    assert [t["tag"] for t in tags] == ["AI", "Chips"]
    assert tags[0]["id"] == 1

    # Lần 2: từ cache, không gọi AI
    client.complete.reset_mock()
    tags2 = f.extract_tags(interests.read_text())
    assert len(tags2) == 2
    client.complete.assert_not_called()


def test_ai_filter_classify_parse(tmp_path):
    interests = tmp_path / "interests.txt"
    interests.write_text("AI stuff", encoding="utf-8")
    client = _mock_client(
        [
            '[{"id": 1, "tag_id": 1, "score": 0.9}, '
            '{"id": 1, "tag_id": 2, "score": 0.7}, '
            '{"id": 2, "tag_id": 1, "score": 0.3}, '
            '{"id": 99, "tag_id": 1, "score": 0.9}]'
        ]
    )
    f = AIInterestsFilter(
        client,
        {"INTERESTS_FILE": str(interests), "CRITERIA_CACHE_FILE": str(tmp_path / "c.json"), "MIN_SCORE": 0.5},
    )
    batch = [
        {"id": 1, "title": "GPT-5 out", "source": "x"},
        {"id": 2, "title": "Football", "source": "y"},
    ]
    tags = [{"id": 1, "tag": "AI"}, {"id": 2, "tag": "Other"}]
    result = f.classify_batch(batch, tags, "AI stuff")
    # Tin 1: best tag = AI (0.9 > 0.7); tin 2: score 0.3 < min → bỏ; id 99 invalid → bỏ
    assert result == {1: {"tag": "AI", "tag_id": 1, "score": 0.9}}


def test_ai_filter_unconfigured_returns_none(tmp_path):
    client = _mock_client([])
    client.is_configured.return_value = False
    f = AIInterestsFilter(client, {"INTERESTS_FILE": str(tmp_path / "none.txt")})
    assert f.filter_titles({"a": {"title x": {}}}) is None


# ────────────────────────── ai_client env prefix ──────────────────────────

def test_ai_client_prefix_resolution(monkeypatch):
    monkeypatch.delenv("TRANSLATE_PROVIDER", raising=False)
    monkeypatch.delenv("TRANSLATE_API_KEY", raising=False)
    monkeypatch.delenv("TRANSLATE_MODEL", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    client = AIClient("TRANSLATE")
    assert client.provider == "gemini"
    assert client.model == "gemini-3.5-flash"
    assert client.api_key == "test-google-key"
    assert client.is_configured()


def test_ai_client_prefix_override(monkeypatch):
    monkeypatch.setenv("TRANSLATE_PROVIDER", "openai")
    monkeypatch.setenv("TRANSLATE_API_KEY", "sk-x")
    monkeypatch.setenv("TRANSLATE_MODEL", "gpt-x")
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://custom.api/")
    client = AIClient("TRANSLATE")
    assert client.provider == "openai"
    assert client.model == "gpt-x"
    assert client.base_url == "https://custom.api"


def test_ai_client_default_ai_prefix():
    client = AIClient()
    assert client.provider in ("claude", "openai", "deepseek", "gemini", "ollama")


# ────────────────────────── RSS Atom parsing ──────────────────────────

def test_rss_atom_entry_parsing():
    """Atom <entry> + <link href/> phải parse được (Reddit .rss, The Verge)."""
    from src.core.vietnam_fetcher import VietnamRSSFetcher
    atom = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>OpenAI releases GPT-6</title>
        <link rel="alternate" href="https://reddit.com/r/OpenAI/comments/abc/"/>
        <link rel="self" href="https://reddit.com/self"/>
      </entry>
      <entry>
        <title>Rust 1.90 released &amp; stable</title>
        <link href="https://example.com/rust"/>
      </entry>
    </feed>"""
    f = VietnamRSSFetcher()
    items = f._parse_rss_items_xml(atom, 50)
    assert len(items) == 2
    assert items[0] == ("OpenAI releases GPT-6", "https://reddit.com/r/OpenAI/comments/abc/")
    assert items[1] == ("Rust 1.90 released & stable", "https://example.com/rust")


def test_rss_atom_regex_fallback():
    """Fallback regex cũng phải đọc được <entry> khi XML malformed."""
    from src.core.vietnam_fetcher import VietnamRSSFetcher
    broken = """<feed><entry><title type="html">A &quot;quoted&quot; title</title>
    <link href="https://reddit.com/r/x/comments/1/"/></entry>
    <entry><title>Second</title><link rel="alternate" href="https://ex.com/2"/></entry>
    <unclosed"""
    f = VietnamRSSFetcher()
    items = f._parse_rss_items(broken, 50)
    assert len(items) == 2
    assert items[0] == ('A "quoted" title', "https://reddit.com/r/x/comments/1/")
    assert items[1][1] == "https://ex.com/2"


def test_rss_2_item_still_works():
    """RSS 2.0 <item> không bị ảnh hưởng bởi Atom support."""
    from src.core.vietnam_fetcher import VietnamRSSFetcher
    rss = """<?xml version="1.0"?><rss><channel>
      <item><title>Tin A</title><link>https://a.com/1</link></item>
      <item><title>Tin B</title><link>https://a.com/2</link></item>
    </channel></rss>"""
    f = VietnamRSSFetcher()
    items = f._parse_rss_items_xml(rss, 50)
    assert items == [("Tin A", "https://a.com/1"), ("Tin B", "https://a.com/2")]
