# Design Doc: Sequential Bug Fix & Improvement Plan

**Date:** 2026-03-15
**Status:** Approved
**Approach:** Fix tuần tự theo thứ tự impact/effort

---

## Bối cảnh

Sau khi review toàn bộ codebase TrendRadar, phát hiện 8 vấn đề cần fix theo thứ tự ưu tiên:
- 2 bugs làm sai kết quả thực tế
- 1 bug logic (config không được dùng)
- 3 vấn đề performance/reliability
- 2 vấn đề code quality

Mỗi fix là **độc lập**, có thể commit riêng và rollback riêng.

---

## Fix 1 — RSS null bug

**File:** `src/core/vietnam_fetcher.py:89`
**Mức độ:** Bug 🔴
**Effort:** ~15 phút

### Vấn đề
```python
link_match = re.search(
    r"<link><!\[CDATA\[(.*?)\]\]></link>"     # group(1)
    r"|<link>(.*?)</link>"                     # group(2)
    r"|<link\s*/>"                             # group(3) — KHÔNG CÓ capture group!
    r"|<guid[^>]*>(https?://[^<]+)</guid>",    # group(4) — bị đẩy thành group(3)
    block, re.DOTALL
)
url = (link_match.group(1) or link_match.group(2) or link_match.group(3) or "").strip()
#                                                              ↑ luôn None với pattern 3
```

Pattern `<link\s*/>` không có capture group nhưng code vẫn đọc `group(3)` → trả `None`.
Pattern `<guid>` thực ra là group(4) nhưng đang được gọi là group(3) → URL từ guid bị bỏ sót.

### Solution
Tách pattern `<link\s*/>` (self-closing, không có URL) ra khỏi chain group matching. Dùng `group(1) or group(2) or group(3)` với 3 patterns có capture group thực sự.

---

## Fix 2 — Double `save_titles_to_file()`

**File:** `main.py:350,359`
**Mức độ:** Bug 🔴
**Effort:** ~10 phút

### Vấn đề
```python
# Dòng 350
title_file = save_titles_to_file(results, id_to_name, failed_ids)

# Dòng 359 — ghi lại file y hệt, chỉ để lấy tên file
time_info = Path(save_titles_to_file(results, id_to_name, failed_ids)).stem
```

File bị ghi 2 lần với cùng data. Lần 2 chỉ cần lấy `stem` từ `title_file` đã có.

### Solution
```python
title_file = save_titles_to_file(results, id_to_name, failed_ids)
time_info = Path(title_file).stem  # dùng lại biến đã có
```

---

## Fix 3 — Wire CONFIG weights vào analytics.py

**File:** `mcp_server/tools/analytics.py:47-49`
**Mức độ:** Bug 🟠
**Effort:** ~20 phút

### Vấn đề
`config.yaml` có section `weight` với `rank_weight: 0.6`, `frequency_weight: 0.3`, `hotness_weight: 0.1`.
`settings.py` load đúng vào `CONFIG["RANK_WEIGHT"]` etc.
Nhưng `calculate_news_weight()` trong analytics.py hardcode lại giá trị này:

```python
RANK_WEIGHT = 0.6       # hardcoded — không đọc CONFIG
FREQUENCY_WEIGHT = 0.3
HOTNESS_WEIGHT = 0.1
```

Người dùng thay đổi config.yaml → không có tác dụng.

### Solution
Import CONFIG và đọc từ đó. Nếu MCP server chạy độc lập không có CONFIG, fallback về giá trị mặc định.

### Scope
Pipeline chính (`statistics.py`) **giữ nguyên** sort đơn giản `(is_new, min_rank, last_time)` — intentional design, không cần weights phức tạp ở đây.

---

## Fix 4 — `requests.Session` cho DataFetcher

**File:** `src/core/data_fetcher.py`
**Mức độ:** Performance 🟠
**Effort:** ~20 phút

### Vấn đề
Mỗi request trong `fetch_data()` tạo một TCP connection mới. Với 20+ NewsNow platforms crawl đồng thời, đây là overhead không cần thiết.

### Solution
Khởi tạo `requests.Session` trong `__init__`, dùng lại cho tất cả request trong cùng instance. Session tự động reuse connections (HTTP keep-alive).

```python
def __init__(self, proxy_url=None):
    self.proxy_url = proxy_url
    self.session = requests.Session()
    self.session.headers.update({...})  # set headers 1 lần
```

**Lưu ý:** `VietnamRSSFetcher` cũng áp dụng tương tự.

---

## Fix 5 — RSS parser: regex → xml.etree

**File:** `src/core/vietnam_fetcher.py`
**Mức độ:** Reliability 🟠
**Effort:** ~30 phút

### Vấn đề
RSS parser dùng regex trên raw XML string — fragile với:
- Namespace (`<atom:link>`, `<media:content>`)
- Encoding issues
- Multiline attributes
- Malformed XML từ một số RSS feeds

### Solution
Dùng `xml.etree.ElementTree` (stdlib, không cần thêm dependency):

```python
import xml.etree.ElementTree as ET

def _parse_rss_items(self, content: str) -> List[Tuple[str, str]]:
    root = ET.fromstring(content)
    # handle namespaces, extract <title> and <link>
```

Fallback về regex nếu ET.fromstring fails (một số RSS feeds không valid XML).

---

## Fix 6 — Configurable RSS item limit

**File:** `src/core/vietnam_fetcher.py:74`
**Mức độ:** Quality 🟡
**Effort:** ~10 phút

### Vấn đề
```python
for block in item_blocks[:50]:  # hardcoded, không configurable
```

### Solution
Thêm `max_items` parameter với default `50`, hoặc đọc từ CONFIG nếu có.

---

## Fix 7 — Deprecate `request_interval` silently-ignored

**Files:** `src/core/data_fetcher.py`, `src/core/vietnam_fetcher.py`, `main.py`
**Mức độ:** Quality 🟡
**Effort:** ~10 phút

### Vấn đề
```python
def crawl_websites(self, ids_list, request_interval=None, ...):
    # request_interval: Kept for backward compatibility (ignored in concurrent mode)
```

Parameter này bị ignore hoàn toàn nhưng vẫn được truyền vào từ `main.py`. Config `REQUEST_INTERVAL: 1000` không có tác dụng gì.

### Solution
Thêm deprecation warning khi `request_interval` được truyền vào (khác None), ghi rõ trong docstring rằng concurrent mode không dùng delay.

---

## Fix 8 — AI cache invalidation strategy

**File:** `src/analysis/investment_analyzer.py`
**Mức độ:** Enhancement 🟡
**Effort:** ~45 phút

### Vấn đề
```python
cache_key = md5(sorted(titles))  # hash toàn bộ list
```

Nếu chỉ 1 trong 50+ titles thay đổi → cache miss hoàn toàn → gọi AI lại cho tất cả asset classes.

### Solution
Dùng **content-based sliding window**: thay vì hash toàn bộ list, hash top-N titles (ví dụ: 20 titles quan trọng nhất) cho mỗi asset class. Thay đổi nhỏ ở cuối list không trigger invalidation.

Hoặc đơn giản hơn: tăng `cache_hours` default lên 12h và document rõ behavior.

---

## Thứ tự thực hiện

| # | Fix | File | Effort | Commit message |
|---|-----|------|--------|----------------|
| 1 | RSS null bug | vietnam_fetcher.py | 15m | `fix: correct RSS link group matching in VietnamRSSFetcher` |
| 2 | Double save | main.py | 10m | `fix: remove duplicate save_titles_to_file call` |
| 3 | Wire weights | analytics.py | 20m | `fix: read weight config from CONFIG instead of hardcoded values` |
| 4 | Session reuse | data_fetcher.py | 20m | `perf: use requests.Session for connection reuse in DataFetcher` |
| 5 | XML parser | vietnam_fetcher.py | 30m | `refactor: replace regex RSS parser with xml.etree.ElementTree` |
| 6 | RSS limit | vietnam_fetcher.py | 10m | `fix: make RSS max_items configurable` |
| 7 | Deprecate param | data_fetcher.py | 10m | `chore: add deprecation warning for request_interval parameter` |
| 8 | Cache strategy | investment_analyzer.py | 45m | `perf: improve AI analysis cache invalidation strategy` |

**Tổng ước tính:** ~2.5 giờ

---

## Không nằm trong scope

- Refactor mixed Vietnamese/Chinese comments (lớn, ít impact thực tế)
- Thêm rate limiting cho RSS crawl (cần thêm logic phức tạp)
- Thêm weighted sort vào pipeline chính (intentional design hiện tại)
- Thêm cross-platform deduplication (feature mới, không phải bug fix)
