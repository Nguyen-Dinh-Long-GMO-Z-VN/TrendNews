"""
Cross-source deduplication for TrendRadar.

Gom các tiêu đề trùng/near-duplicate xuất hiện trên NHIỀU nguồn khác nhau
(vd: cùng một tin trên VnExpress + Tuổi Trẻ + GenK) thành một entry canonical:

- normalize_title: NFKC, lowercase, bỏ dấu câu/ký hiệu/emoji, gộp whitespace
- Exact merge: cùng normalized title hoặc cùng normalized URL
- Fuzzy merge: sorted-neighborhood + difflib ratio (mặc định 0.88)
- Merge: giữ entry có rank tốt nhất làm canonical; gộp ranks/url/time/count;
  thêm "sources" (list source_id) và "source_count" — tín hiệu viral xuyên nguồn
- new_titles được remap theo canonical để badge "new" không bị mất
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

_PUNCT_RE = re.compile(r"[^\w\s]|_", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_TRACKING_PARAMS = {"fbclid", "gclid", "spm", "ref", "source"}


def normalize_title(title: str) -> str:
    """
    Chuẩn hóa tiêu đề để so sánh: NFKC → lowercase → bỏ dấu câu → gộp space.
    Kết quả rỗng (title toàn ký hiệu) → trả chuỗi rỗng, caller tự bỏ qua.
    """
    if not isinstance(title, str):
        return ""
    text = unicodedata.normalize("NFKC", title).lower()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_url(url: str) -> str:
    """Bỏ tracking params (utm_*, fbclid...) + fragment + trailing slash."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

        parts = urlparse(url.strip().lower())
        kept = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.startswith("utm_") and k not in _TRACKING_PARAMS
        ]
        clean = urlunparse(
            (parts.scheme, parts.netloc, parts.path.rstrip("/"),
             parts.params, urlencode(kept), "")
        )
        return clean
    except Exception:
        return url.strip().lower().split("#", 1)[0].rstrip("/")


class _UnionFind:
    """Union-find trên index để gom cluster trùng lặp (kể cả chuỗi bắc cầu)."""

    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _similar(a: str, b: str, threshold: float) -> bool:
    """So fuzzy 2 normalized title. Bỏ qua title quá ngắn (dễ trùng ngẫu nhiên)."""
    if not a or not b:
        return False
    # Title ngắn (<15 ký tự) chỉ merge khi gần như giống hệt
    if min(len(a), len(b)) < 15 and a != b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def deduplicate_results(
    all_results: Dict,
    title_info: Dict,
    new_titles: Optional[Dict] = None,
    similarity_threshold: float = 0.88,
    neighbor_window: int = 8,
) -> Dict:
    """
    Dedup xuyên nguồn, sửa trực tiếp all_results / title_info / new_titles.

    Args:
        all_results: {source_id: {title: {ranks, url, mobileUrl}}}
        title_info:  {source_id: {title: {first_time, last_time, count, ...}}}
        new_titles:  {source_id: {title: data}} — optional, remap sang canonical
        similarity_threshold: ngưỡng fuzzy (0.85–0.92 hợp lý)
        neighbor_window: số phần tử kề so sánh trong sorted-neighborhood

    Returns:
        Dict thống kê: {"merged": số entry bị gộp, "clusters": số cụm}
    """
    # 1. Thu thập mọi (source_id, title) entry
    entries: List[Tuple[str, str]] = []
    for source_id, titles in all_results.items():
        for title in titles.keys():
            entries.append((source_id, title))

    if len(entries) < 2:
        return {"merged": 0, "clusters": 0}

    norms = [normalize_title(t) for _, t in entries]
    uf = _UnionFind(len(entries))

    # 2a. Exact merge theo normalized title
    by_norm: Dict[str, int] = {}
    for i, norm in enumerate(norms):
        if not norm:
            continue
        if norm in by_norm:
            uf.union(i, by_norm[norm])
        else:
            by_norm[norm] = i

    # 2b. Exact merge theo normalized URL (RSS repost cùng link)
    by_url: Dict[str, int] = {}
    for i, (source_id, title) in enumerate(entries):
        url = normalize_url(all_results[source_id][title].get("url", ""))
        if not url:
            continue
        if url in by_url:
            uf.union(i, by_url[url])
        else:
            by_url[url] = i

    # 2c. Fuzzy: sorted-neighborhood — sort theo normalized, so mỗi phần tử
    #     với K phần tử liền sau (title tương tự sẽ đứng gần nhau)
    order = sorted(range(len(entries)), key=lambda i: norms[i])
    for pos in range(len(order)):
        i = order[pos]
        if not norms[i]:
            continue
        for ahead in range(1, neighbor_window + 1):
            if pos + ahead >= len(order):
                break
            j = order[pos + ahead]
            if not norms[j]:
                continue
            if _similar(norms[i], norms[j], similarity_threshold):
                uf.union(i, j)

    # 3. Gom cluster
    clusters: Dict[int, List[int]] = {}
    for i in range(len(entries)):
        clusters.setdefault(uf.find(i), []).append(i)

    merged = 0
    dup_clusters = 0

    for members in clusters.values():
        if len(members) < 2:
            continue
        dup_clusters += 1

        # Chọn canonical: rank tốt nhất → title dài hơn → source_id nhỏ hơn
        def _rank_key(idx: int):
            src, t = entries[idx]
            ranks = all_results[src][t].get("ranks", []) or [99]
            return (min(ranks), -len(t), src)

        canonical_idx = min(members, key=_rank_key)
        canon_src, canon_title = entries[canonical_idx]

        merged_ranks: List[int] = []
        merged_url = ""
        merged_mobile = ""
        sources: List[str] = []
        first_time = ""
        last_time = ""
        total_count = 0

        for idx in members:
            src, t = entries[idx]
            data = all_results.get(src, {}).get(t, {})
            info = title_info.get(src, {}).get(t, {})

            for r in data.get("ranks", []):
                if r not in merged_ranks:
                    merged_ranks.append(r)
            merged_url = merged_url or data.get("url", "")
            merged_mobile = merged_mobile or data.get("mobileUrl", "")

            if src not in sources:
                sources.append(src)

            ft = info.get("first_time", "")
            lt = info.get("last_time", "")
            if ft and (not first_time or ft < first_time):
                first_time = ft
            if lt and lt > last_time:
                last_time = lt
            total_count += info.get("count", 1)

            # Xóa entry không phải canonical
            if idx != canonical_idx:
                all_results.get(src, {}).pop(t, None)
                title_info.get(src, {}).pop(t, None)
                merged += 1

        merged_ranks.sort()
        canon_data = all_results[canon_src][canon_title]
        canon_data["ranks"] = merged_ranks
        canon_data["url"] = merged_url
        canon_data["mobileUrl"] = merged_mobile
        canon_data["sources"] = sources
        canon_data["source_count"] = len(sources)

        if canon_src in title_info and canon_title in title_info[canon_src]:
            info = title_info[canon_src][canon_title]
            info["first_time"] = first_time or info.get("first_time", "")
            info["last_time"] = last_time or info.get("last_time", "")
            info["count"] = total_count or info.get("count", 1)
            info["ranks"] = merged_ranks
            info["url"] = merged_url or info.get("url", "")
            info["mobileUrl"] = merged_mobile or info.get("mobileUrl", "")
            info["sources"] = sources
            info["source_count"] = len(sources)

        # Remap new_titles: dup ở source khác mà là "new" → canonical cũng là new
        if new_titles:
            canon_is_new = False
            for idx in members:
                src, t = entries[idx]
                if src in new_titles and t in new_titles[src]:
                    canon_is_new = True
                    if src != canon_src or t != canon_title:
                        new_titles[src].pop(t, None)
            if canon_is_new:
                new_titles.setdefault(canon_src, {})[canon_title] = (
                    all_results[canon_src][canon_title]
                )

    # Dọn source rỗng sau khi gỡ entry
    for src in list(all_results.keys()):
        if not all_results[src]:
            all_results.pop(src)
    if title_info:
        for src in list(title_info.keys()):
            if not title_info[src]:
                title_info.pop(src)

    return {"merged": merged, "clusters": dup_clusters}
