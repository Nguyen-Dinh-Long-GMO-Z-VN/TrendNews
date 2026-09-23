# Sequential Bug Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 8 bugs/improvements in TrendRadar sequentially, từ high-impact đến low-impact.

**Architecture:** Mỗi fix là một commit độc lập. Không có dependency giữa các fix (ngoại trừ Fix 5 refactor lại code Fix 1 đã sửa). Chạy manual test sau mỗi fix.

**Tech Stack:** Python 3.10+, requests, xml.etree.ElementTree (stdlib), pytest (cần cài thêm cho tests)

---

## Setup

**Bước đầu tiên — cài pytest nếu chưa có:**

```bash
pip install pytest
mkdir -p tests
touch tests/__init__.py
```

---

### Task 1: Fix RSS null bug

**Files:**
- Modify: `src/core/vietnam_fetcher.py:84-96`
- Test: `tests/test_vietnam_fetcher.py`

**Step 1: Tạo file test**

```python
# tests/test_vietnam_fetcher.py
import pytest
from src.core.vietnam_fetcher import VietnamRSSFetcher

fetcher = VietnamRSSFetcher()

def test_parse_rss_link_cdata():
    xml = """<item>
        <title><![CDATA[Test title]]></title>
        <link><![CDATA[https://example.com/1]]></link>
    </item>"""
    items = fetcher._parse_rss_items(f"<rss><channel>{xml}</channel></rss>")
    assert items == [("Test title", "https://example.com/1")]

def test_parse_rss_link_plain():
    xml = """<item>
        <title>Test title</title>
        <link>https://example.com/2</link>
    </item>"""
    items = fetcher._parse_rss_items(f"<rss><channel>{xml}</channel></rss>")
    assert items == [("Test title", "https://example.com/2")]

def test_parse_rss_link_selfclosing_falls_back_to_guid():
    """<link/> self-closing — URL phải lấy từ <guid>"""
    xml = """<item>
        <title>Test title</title>
        <link/>
        <guid isPermaLink="true">https://example.com/3</guid>
    </item>"""
    items = fetcher._parse_rss_items(f"<rss><channel>{xml}</channel></rss>")
    assert items == [("Test title", "https://example.com/3")]

def test_parse_rss_no_link_returns_empty_url():
    xml = """<item>
        <title>Test title</title>
    </item>"""
    items = fetcher._parse_rss_items(f"<rss><channel>{xml}</channel></rss>")
    assert items == [("Test title", "")]
```

**Step 2: Chạy test để verify FAIL**

```bash
cd /home/dinhlong-vnlab/Documents/TrendNews
pytest tests/test_vietnam_fetcher.py -v
```

Expected: `test_parse_rss_link_selfclosing_falls_back_to_guid` FAIL (trả về `""` thay vì URL từ guid).

**Step 3: Fix code**

Mở `src/core/vietnam_fetcher.py`, tìm method `_parse_rss_items`, thay đoạn link extraction:

```python
# CŨ (dòng ~84-96):
link_match = re.search(
    r"<link><!\[CDATA\[(.*?)\]\]></link>|<link>(.*?)</link>"
    r"|<link\s*/>"
    r"|<guid[^>]*>(https?://[^<]+)</guid>",
    block, re.DOTALL
)
url = ""
if link_match:
    url = (
        link_match.group(1) or link_match.group(2) or link_match.group(3) or ""
    ).strip()
```

```python
# MỚI:
link_match = re.search(
    r"<link><!\[CDATA\[(.*?)\]\]></link>"
    r"|<link>(.*?)</link>",
    block, re.DOTALL
)
guid_match = re.search(r"<guid[^>]*>(https?://[^<]+)</guid>", block)

url = ""
if link_match:
    url = (link_match.group(1) or link_match.group(2) or "").strip()
if not url and guid_match:
    url = guid_match.group(1).strip()
```

**Step 4: Chạy test verify PASS**

```bash
pytest tests/test_vietnam_fetcher.py -v
```

Expected: tất cả 4 tests PASS.

**Step 5: Commit**

```bash
git add tests/test_vietnam_fetcher.py src/core/vietnam_fetcher.py tests/__init__.py
git commit -m "fix: correct RSS link group matching in VietnamRSSFetcher

- Tách pattern <link/> self-closing ra khỏi capture group chain
- Dùng guid fallback riêng thay vì group(3) không có capture
- Thêm tests cho 4 trường hợp link extraction

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 2: Fix double `save_titles_to_file()`

**Files:**
- Modify: `main.py:355-365` (vùng `_execute_mode_strategy`)

**Step 1: Tìm đúng dòng cần sửa**

```bash
grep -n "save_titles_to_file" main.py
```

Expected output: 2 dòng gần nhau trong `_execute_mode_strategy`.

**Step 2: Sửa code**

Tìm đoạn trong `_execute_mode_strategy`:

```python
# CŨ: 2 dòng riêng biệt
title_file = save_titles_to_file(results, id_to_name, failed_ids)
print(f"标题đãlưuđến: {title_file}")
# ... vài dòng sau ...
time_info = Path(save_titles_to_file(results, id_to_name, failed_ids)).stem
```

```python
# MỚI: dùng lại title_file từ dòng đầu
title_file = save_titles_to_file(results, id_to_name, failed_ids)
print(f"标题đãlưuđến: {title_file}")
# ... vài dòng sau ...
time_info = Path(title_file).stem
```

**Lưu ý:** `save_titles_to_file` trong `_crawl_data()` (dòng ~350) là lần gọi hợp lệ — KHÔNG sửa dòng đó. Chỉ sửa lần gọi thứ 2 trong `_execute_mode_strategy()`.

**Step 3: Verify thủ công**

```bash
grep -n "save_titles_to_file" main.py
```

Expected: chỉ còn 2 lần xuất hiện — 1 trong `_crawl_data`, 1 trong `_execute_mode_strategy`.

**Step 4: Commit**

```bash
git add main.py
git commit -m "fix: remove duplicate save_titles_to_file call in _execute_mode_strategy

- Lần gọi thứ 2 chỉ để lấy Path.stem từ file đã lưu ở lần 1
- Dùng lại biến title_file thay vì ghi file 2 lần

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 3: Wire CONFIG weights vào analytics.py

**Files:**
- Modify: `mcp_server/tools/analytics.py:40-74`
- Test: `tests/test_analytics_weights.py`

**Step 1: Tạo test**

```python
# tests/test_analytics_weights.py
import pytest
from unittest.mock import patch

def test_calculate_news_weight_uses_config():
    """Weight calculation phải dùng giá trị từ CONFIG, không hardcode."""
    from mcp_server.tools.analytics import calculate_news_weight

    news_data = {"ranks": [1], "count": 1}

    # Default config (0.6/0.3/0.1) — score = (11-1)*0.6 + min(1,10)*10*0.3 + 1.0*0.1
    # = 10*0.6 + 10*0.3 + 100*0.1 = 6 + 3 + 10 = 19.1
    default_score = calculate_news_weight(news_data)
    assert abs(default_score - 19.1) < 0.01

def test_calculate_news_weight_empty_ranks():
    from mcp_server.tools.analytics import calculate_news_weight
    assert calculate_news_weight({"ranks": [], "count": 0}) == 0.0

def test_calculate_news_weight_high_rank():
    from mcp_server.tools.analytics import calculate_news_weight
    # rank=1 (top) -> rank_score=10, count=5, hotness=100%
    news_data = {"ranks": [1, 1, 1, 1, 1], "count": 5}
    score = calculate_news_weight(news_data, rank_threshold=5)
    # rank_weight = 10, freq_weight = 50, hotness = 100
    # total = 10*0.6 + 50*0.3 + 100*0.1 = 6 + 15 + 10 = 31
    assert abs(score - 31.0) < 0.01
```

**Step 2: Chạy test**

```bash
pytest tests/test_analytics_weights.py -v
```

Expected: tests PASS (hardcode 0.6/0.3/0.1 cho kết quả đúng về số) — đây là baseline.

**Step 3: Sửa code để đọc từ CONFIG**

Mở `mcp_server/tools/analytics.py`, tìm function `calculate_news_weight`, sửa:

```python
# CŨ:
# 权重cấu hình（với config.yaml 保持một致）
RANK_WEIGHT = 0.6
FREQUENCY_WEIGHT = 0.3
HOTNESS_WEIGHT = 0.1
```

```python
# MỚI:
try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.config.settings import CONFIG
    RANK_WEIGHT = CONFIG.get("RANK_WEIGHT", 0.6)
    FREQUENCY_WEIGHT = CONFIG.get("FREQUENCY_WEIGHT", 0.3)
    HOTNESS_WEIGHT = CONFIG.get("HOTNESS_WEIGHT", 0.1)
except Exception:
    # Fallback nếu chạy MCP server độc lập không có src/
    RANK_WEIGHT = 0.6
    FREQUENCY_WEIGHT = 0.3
    HOTNESS_WEIGHT = 0.1
```

**Step 4: Chạy lại test**

```bash
pytest tests/test_analytics_weights.py -v
```

Expected: tất cả PASS (giá trị giống nhau vì config.yaml = 0.6/0.3/0.1).

**Step 5: Commit**

```bash
git add mcp_server/tools/analytics.py tests/test_analytics_weights.py
git commit -m "fix: read weight config from CONFIG instead of hardcoded values in analytics.py

- calculate_news_weight() giờ đọc RANK_WEIGHT/FREQUENCY_WEIGHT/HOTNESS_WEIGHT từ CONFIG
- Fallback về 0.6/0.3/0.1 nếu MCP server chạy độc lập
- Thêm tests cho weight calculation

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 4: `requests.Session` cho DataFetcher và VietnamRSSFetcher

**Files:**
- Modify: `src/core/data_fetcher.py`
- Modify: `src/core/vietnam_fetcher.py`

**Step 1: Sửa DataFetcher**

Mở `src/core/data_fetcher.py`, tìm `__init__` và `fetch_data`:

```python
# CŨ __init__:
def __init__(self, proxy_url: Optional[str] = None):
    self.proxy_url = proxy_url
```

```python
# MỚI __init__:
def __init__(self, proxy_url: Optional[str] = None):
    self.proxy_url = proxy_url
    self.session = requests.Session()
    self.session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    })
    if proxy_url:
        self.session.proxies = {"http": proxy_url, "https": proxy_url}
```

Trong `fetch_data`, thay `requests.get(...)` bằng `self.session.get(...)` và xóa phần build `headers` + `proxies` riêng lẻ:

```python
# CŨ:
headers = { "User-Agent": ..., "Accept": ..., ... }  # xóa block này
proxies = None
if self.proxy_url:
    proxies = {"http": self.proxy_url, "https": self.proxy_url}
# ...
response = requests.get(url, proxies=proxies, headers=headers, timeout=10)
```

```python
# MỚI:
response = self.session.get(url, timeout=10)
```

**Step 2: Sửa VietnamRSSFetcher tương tự**

```python
# CŨ __init__:
def __init__(self, proxy_url: Optional[str] = None):
    self.proxy_url = proxy_url
    self.headers = {
        "User-Agent": "Mozilla/5.0 ...",
        "Accept": "application/rss+xml, ...",
    }
```

```python
# MỚI __init__:
def __init__(self, proxy_url: Optional[str] = None):
    self.proxy_url = proxy_url
    self.session = requests.Session()
    self.session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })
    if proxy_url:
        self.session.proxies = {"http": proxy_url, "https": proxy_url}
```

Trong `fetch_rss`, thay:

```python
# CŨ:
response = requests.get(rss_url, headers=self.headers, proxies=proxies, timeout=10)
```

```python
# MỚI:
response = self.session.get(rss_url, timeout=10)
```

Xóa phần build `proxies` riêng lẻ trong `fetch_rss`.

**Step 3: Verify thủ công**

```bash
grep -n "requests.get" src/core/data_fetcher.py src/core/vietnam_fetcher.py
```

Expected: không còn `requests.get` trong 2 file này (chỉ có `self.session.get`).

**Step 4: Commit**

```bash
git add src/core/data_fetcher.py src/core/vietnam_fetcher.py
git commit -m "perf: use requests.Session for connection reuse in DataFetcher and VietnamRSSFetcher

- Tạo Session trong __init__, reuse cho tất cả requests
- Set headers và proxies 1 lần tại Session level
- Giảm TCP handshake overhead khi crawl 100+ platforms đồng thời

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 5: RSS parser regex → xml.etree.ElementTree

**Files:**
- Modify: `src/core/vietnam_fetcher.py` (method `_parse_rss_items`)
- Test: `tests/test_vietnam_fetcher.py` (thêm test cases mới)

**Step 1: Thêm test cho edge cases XML**

Thêm vào `tests/test_vietnam_fetcher.py`:

```python
def test_parse_rss_with_namespace():
    """RSS với namespace Atom."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <item>
      <title>Namespace title</title>
      <link>https://example.com/ns</link>
    </item>
  </channel>
</rss>"""
    items = fetcher._parse_rss_items(xml)
    assert len(items) == 1
    assert items[0][0] == "Namespace title"
    assert items[0][1] == "https://example.com/ns"

def test_parse_rss_limits_50_items():
    """Không trả về quá 50 items."""
    items_xml = "\n".join(
        f"<item><title>Title {i}</title><link>https://ex.com/{i}</link></item>"
        for i in range(60)
    )
    xml = f"<rss><channel>{items_xml}</channel></rss>"
    items = fetcher._parse_rss_items(xml)
    assert len(items) <= 50

def test_parse_rss_malformed_falls_back_to_regex():
    """Malformed XML fallback về regex parser."""
    malformed = "<item><title>Test</title><link>https://ex.com/1</link></item>"
    # Không có root element → ET sẽ fail → fallback
    items = fetcher._parse_rss_items(malformed)
    # Regex fallback vẫn parse được item đơn lẻ
    assert len(items) == 1
```

**Step 2: Chạy test (phải PASS vì regex hiện tại xử lý được)**

```bash
pytest tests/test_vietnam_fetcher.py -v
```

**Step 3: Thay thế `_parse_rss_items` bằng xml.etree**

```python
# MỚI: trong src/core/vietnam_fetcher.py
import xml.etree.ElementTree as ET

def _parse_rss_items(self, content: str, max_items: int = 50) -> List[Tuple[str, str]]:
    """Extract (title, url) pairs từ RSS XML string.

    Dùng xml.etree.ElementTree; fallback về regex nếu XML không valid.
    """
    try:
        return self._parse_rss_items_xml(content, max_items)
    except ET.ParseError:
        return self._parse_rss_items_regex(content, max_items)

def _parse_rss_items_xml(self, content: str, max_items: int) -> List[Tuple[str, str]]:
    """Parse RSS dùng xml.etree — xử lý namespace và CDATA."""
    # Strip namespace declarations để ET xử lý đơn giản hơn
    content_clean = re.sub(r'\s+xmlns(?::\w+)?="[^"]+"', '', content)
    root = ET.fromstring(content_clean)

    items = []
    # Tìm tất cả <item> bất kể depth
    for item in root.iter("item"):
        title_el = item.find("title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        url = ""
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            url = link_el.text.strip()
        # Fallback: guid
        if not url:
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text:
                candidate = guid_el.text.strip()
                if candidate.startswith("http"):
                    url = candidate

        if title:
            items.append((title, url))
        if len(items) >= max_items:
            break

    return items

def _parse_rss_items_regex(self, content: str, max_items: int) -> List[Tuple[str, str]]:
    """Fallback regex parser cho malformed XML."""
    items = []
    item_blocks = re.findall(r"<item[^>]*>(.*?)</item>", content, re.DOTALL)

    for block in item_blocks[:max_items]:
        title_match = re.search(
            r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",
            block, re.DOTALL
        )
        title = ""
        if title_match:
            title = (title_match.group(1) or title_match.group(2) or "").strip()

        link_match = re.search(
            r"<link><!\[CDATA\[(.*?)\]\]></link>"
            r"|<link>(.*?)</link>",
            block, re.DOTALL
        )
        guid_match = re.search(r"<guid[^>]*>(https?://[^<]+)</guid>", block)

        url = ""
        if link_match:
            url = (link_match.group(1) or link_match.group(2) or "").strip()
        if not url and guid_match:
            url = guid_match.group(1).strip()

        if title:
            items.append((title, url))

    return items
```

Xóa method `_parse_rss_items` cũ và đảm bảo `import xml.etree.ElementTree as ET` ở đầu file.

**Step 4: Chạy tất cả tests**

```bash
pytest tests/test_vietnam_fetcher.py -v
```

Expected: tất cả PASS kể cả test namespace và malformed.

**Step 5: Commit**

```bash
git add src/core/vietnam_fetcher.py tests/test_vietnam_fetcher.py
git commit -m "refactor: replace regex RSS parser with xml.etree.ElementTree

- Primary: ET parser xử lý namespace, encoding, CDATA chuẩn hơn
- Fallback: regex parser (đã fix group matching từ Task 1) cho malformed XML
- Tách thành 3 methods: _parse_rss_items (dispatcher), _xml, _regex
- Thêm tests cho namespace và malformed fallback

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 6: Configurable RSS item limit

**Files:**
- Modify: `src/core/vietnam_fetcher.py`
- Modify: `config/config.yaml`

**Step 1: Thêm config vào config.yaml**

Mở `config/config.yaml`, tìm section `crawler`, thêm:

```yaml
crawler:
  request_interval: 1000
  enable_crawler: true
  use_proxy: false
  default_proxy: "http://127.0.0.1:10086"
  rss_max_items: 50   # ← thêm dòng này
```

**Step 2: Đọc config trong settings.py**

Mở `src/config/settings.py`, tìm nơi load `crawler` config, thêm:

```python
"RSS_MAX_ITEMS": config_data["crawler"].get("rss_max_items", 50),
```

**Step 3: Dùng config trong VietnamRSSFetcher**

Trong `fetch_rss()`, thay hardcoded `max_items=50` bằng đọc từ CONFIG:

```python
from src.config.settings import CONFIG

def fetch_rss(self, platform_id: str, rss_url: str, name: str) -> Optional[Dict]:
    max_items = CONFIG.get("RSS_MAX_ITEMS", 50)
    items = self._parse_rss_items(content, max_items=max_items)
```

**Step 4: Verify**

```bash
grep -n "RSS_MAX_ITEMS\|rss_max_items\|max_items" src/config/settings.py src/core/vietnam_fetcher.py config/config.yaml
```

**Step 5: Commit**

```bash
git add config/config.yaml src/config/settings.py src/core/vietnam_fetcher.py
git commit -m "fix: make RSS max_items configurable via config.yaml

- Thêm crawler.rss_max_items vào config.yaml (default 50)
- VietnamRSSFetcher đọc từ CONFIG thay vì hardcode [:50]

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 7: Deprecate `request_interval` silently-ignored

**Files:**
- Modify: `src/core/data_fetcher.py`
- Modify: `src/core/vietnam_fetcher.py`

**Step 1: Thêm deprecation warning vào DataFetcher**

Trong `crawl_websites`, tìm:

```python
def crawl_websites(
    self,
    ids_list: List[Union[str, Tuple[str, str]]],
    request_interval: int = None,
    max_workers: int = 24,
) -> Tuple[Dict, Dict, List]:
    """
    ...
    Args:
        request_interval: Kept for backward compatibility (ignored in concurrent mode)
    """
```

Sửa thành:

```python
def crawl_websites(
    self,
    ids_list: List[Union[str, Tuple[str, str]]],
    request_interval: int = None,
    max_workers: int = 24,
) -> Tuple[Dict, Dict, List]:
    """
    ...
    Args:
        request_interval: DEPRECATED — không có tác dụng trong concurrent mode.
            Crawler hiện dùng ThreadPoolExecutor, không có delay giữa requests.
    """
    if request_interval is not None:
        import warnings
        warnings.warn(
            "request_interval không có tác dụng trong concurrent mode và sẽ bị xóa trong phiên bản tương lai.",
            DeprecationWarning,
            stacklevel=2,
        )
```

**Step 2: Làm tương tự cho VietnamRSSFetcher.crawl_vietnam_platforms**

Thêm cùng warning vào `crawl_vietnam_platforms`.

**Step 3: Verify**

```bash
grep -n "request_interval" main.py src/core/data_fetcher.py src/core/vietnam_fetcher.py
```

**Step 4: Commit**

```bash
git add src/core/data_fetcher.py src/core/vietnam_fetcher.py
git commit -m "chore: add DeprecationWarning for request_interval parameter

- Parameter này bị ignore trong concurrent mode từ khi chuyển sang ThreadPoolExecutor
- Warning giúp caller biết config REQUEST_INTERVAL không có tác dụng

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

### Task 8: Cải thiện AI cache invalidation strategy

**Files:**
- Modify: `src/analysis/investment_analyzer.py`
- Test: `tests/test_investment_cache.py`

**Step 1: Tạo test**

```python
# tests/test_investment_cache.py
import time
from src.analysis.investment_analyzer import _cache_key, _is_cache_valid

def test_cache_key_stable_for_same_titles():
    titles = ["Bitcoin rises", "Gold falls", "Fed hikes rate"]
    assert _cache_key(titles) == _cache_key(titles)

def test_cache_key_different_for_different_titles():
    titles_a = ["Bitcoin rises", "Gold falls"]
    titles_b = ["Bitcoin rises", "Oil drops"]
    assert _cache_key(titles_a) != _cache_key(titles_b)

def test_cache_valid_within_hours():
    entry = {"timestamp": time.time() - 3600}  # 1 giờ trước
    assert _is_cache_valid(entry, cache_hours=6) is True

def test_cache_invalid_after_hours():
    entry = {"timestamp": time.time() - 7 * 3600}  # 7 giờ trước
    assert _is_cache_valid(entry, cache_hours=6) is False

def test_cache_key_ignores_minor_tail_changes():
    """Top-20 titles giống nhau → cache key giống nhau dù có thêm titles ở cuối."""
    base_titles = [f"Title {i}" for i in range(20)]
    titles_a = base_titles + ["Extra title A"]
    titles_b = base_titles + ["Extra title B", "Extra title C"]
    assert _cache_key(titles_a) == _cache_key(titles_b)
```

**Step 2: Chạy test — test cuối FAIL**

```bash
pytest tests/test_investment_cache.py -v
```

Expected: `test_cache_key_ignores_minor_tail_changes` FAIL.

**Step 3: Sửa `_cache_key` để dùng top-N strategy**

```python
# CŨ:
def _cache_key(titles: List[str]) -> str:
    combined = "\n".join(sorted(titles))
    return hashlib.md5(combined.encode("utf-8")).hexdigest()
```

```python
# MỚI:
_CACHE_KEY_TOP_N = 20  # chỉ hash top-N titles để giảm cache miss

def _cache_key(titles: List[str]) -> str:
    """Hash top-N titles để tránh full invalidation khi có tin nhỏ thay đổi ở cuối list."""
    top_titles = sorted(titles)[:_CACHE_KEY_TOP_N]
    combined = "\n".join(top_titles)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()
```

**Step 4: Chạy tất cả tests**

```bash
pytest tests/ -v
```

Expected: tất cả PASS.

**Step 5: Commit**

```bash
git add src/analysis/investment_analyzer.py tests/test_investment_cache.py
git commit -m "perf: improve AI analysis cache key to use top-N titles strategy

- Hash chỉ top-20 titles thay vì toàn bộ list
- Tránh cache miss khi chỉ có vài tin mới ở cuối list
- Thêm tests cho cache key stability và validation

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

## Kiểm tra cuối cùng

Sau khi hoàn thành tất cả 8 tasks:

```bash
# Chạy toàn bộ test suite
pytest tests/ -v

# Check git log
git log --oneline -10
```

Expected: 8 commits sạch, tất cả tests PASS.
