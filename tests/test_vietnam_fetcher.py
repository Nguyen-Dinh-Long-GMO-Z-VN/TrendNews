import pytest
from src.core.vietnam_fetcher import VietnamRSSFetcher


@pytest.fixture
def fetcher():
    return VietnamRSSFetcher()


def test_parse_rss_link_cdata(fetcher):
    xml = "<rss><channel><item><title><![CDATA[Test title]]></title><link><![CDATA[https://example.com/1]]></link></item></channel></rss>"
    items = fetcher._parse_rss_items(xml)
    assert items == [("Test title", "https://example.com/1")]


def test_parse_rss_link_plain(fetcher):
    xml = "<rss><channel><item><title>Test title</title><link>https://example.com/2</link></item></channel></rss>"
    items = fetcher._parse_rss_items(xml)
    assert items == [("Test title", "https://example.com/2")]


def test_parse_rss_link_selfclosing_falls_back_to_guid(fetcher):
    xml = """<rss><channel><item>
        <title>Test title</title>
        <link/>
        <guid isPermaLink="true">https://example.com/3</guid>
    </item></channel></rss>"""
    items = fetcher._parse_rss_items(xml)
    assert items == [("Test title", "https://example.com/3")]


def test_parse_rss_no_link_returns_empty_url(fetcher):
    xml = "<rss><channel><item><title>Test title</title></item></channel></rss>"
    items = fetcher._parse_rss_items(xml)
    assert items == [("Test title", "")]


def test_parse_rss_with_namespace(fetcher):
    """RSS feed với XML namespace."""
    xml = '<?xml version="1.0" encoding="UTF-8"?><rss><channel><item><title>Namespace title</title><link>https://example.com/ns</link></item></channel></rss>'
    items = fetcher._parse_rss_items(xml)
    assert len(items) == 1
    assert items[0][0] == "Namespace title"
    assert items[0][1] == "https://example.com/ns"

def test_parse_rss_limits_items(fetcher):
    """Không trả về quá max_items."""
    items_xml = "".join(
        f"<item><title>Title {i}</title><link>https://ex.com/{i}</link></item>"
        for i in range(60)
    )
    xml = f"<rss><channel>{items_xml}</channel></rss>"
    items = fetcher._parse_rss_items(xml, max_items=50)
    assert len(items) <= 50

def test_parse_rss_malformed_falls_back_to_regex(fetcher):
    """Malformed XML fallback về regex parser."""
    # Không có root element → ET sẽ fail → fallback regex
    malformed = "<item><title>Test</title><link>https://ex.com/1</link></item>"
    items = fetcher._parse_rss_items(malformed)
    assert len(items) == 1
    assert items[0] == ("Test", "https://ex.com/1")
