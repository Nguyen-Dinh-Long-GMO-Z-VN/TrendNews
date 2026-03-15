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
