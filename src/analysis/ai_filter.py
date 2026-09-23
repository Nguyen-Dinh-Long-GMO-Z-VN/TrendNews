"""
AI natural-language news filter — port từ upstream TrendRadar (ai/filter.py).

2 giai đoạn:
- Phase A: đọc mô tả sở thích tự nhiên (ai_interests.txt) → AI extract
  structured tags [{tag, description}], cache theo content hash.
- Phase B: classify batch tiêu đề → mỗi tin gán đúng 1 tag điểm cao nhất.

Integration:
- mode="prefilter": chỉ giữ title AI match → word_groups tiếp tục tổ chức report
- mode="replace": bỏ qua word_groups, report gom "tất cả tin tức" (AI tag đi kèm)
- AI không khả dụng / lỗi → trả None → pipeline fallback keyword như cũ
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from .ai_client import AIClient

_EXTRACT_SYSTEM = """Bạn là trợ lý phân tích sở thích tin tức. Từ mô tả sở thích bằng ngôn ngữ tự nhiên của người dùng, trích xuất các nhóm chủ đề có cấu trúc.

Yêu cầu:
1. Mỗi chủ đề = 1 tag ngắn gọn + description mô tả rõ phạm vi.
2. Giữ NGUYÊN thứ tự ưu tiên người dùng liệt kê (tag đầu = quan trọng nhất).
3. Chỉ xuất JSON hợp lệ: {"tags": [{"tag": "...", "description": "..."}, ...]}
4. Không thêm giải thích ngoài JSON."""

_EXTRACT_USER = """Trích xuất tag từ mô tả sở thích sau:

{interests_content}

Chỉ xuất JSON."""

_CLASSIFY_SYSTEM = """Bạn là trợ lý phân loại tin tức chính xác. Gán mỗi tiêu đề tin vào ĐÚNG MỘT tag phù hợp nhất (nếu có), kèm điểm liên quan 0.0-1.0.

Quy tắc:
1. Tag có thứ tự ưu tiên: tin khớp nhiều tag → chọn tag SỚM NHẤT.
2. Điểm < 0.5 nghĩa là liên quan yếu — bỏ qua, không trả về.
3. Tuân thủ yêu cầu chất lượng tiêu đề trong mô tả sở thích (bỏ title câu view, quảng cáo, spam).
4. Chỉ xuất JSON array: [{"id": <số thứ tự tin>, "tag_id": <số thứ tự tag>, "score": <0.0-1.0>}, ...]
5. Không trả về tin không khớp. Không thêm giải thích."""

_CLASSIFY_USER = """Mô tả sở thích của người dùng:
{interests_content}

Danh sách tag (id. tag: mô tả):
{tags_list}

Danh sách {news_count} tiêu đề (id. [nguồn] tiêu đề):
{news_list}

Trả về JSON array các tin khớp."""


class AIInterestsFilter:
    """
    Lọc tin theo mô tả sở thích tự nhiên.

    Usage:
        f = AIInterestsFilter(client, cfg)
        tag_map = f.filter_titles(all_results)
        # → {title: {"tag": "...", "score": 0.9}} hoặc None nếu AI không khả dụng
    """

    def __init__(self, client: AIClient, config: Dict = None):
        cfg = config or {}
        self.client = client
        self.interests_file = Path(
            cfg.get("INTERESTS_FILE", "config/ai_interests.txt")
        )
        self.batch_size = int(cfg.get("BATCH_SIZE", 30))
        self.batch_delay = float(cfg.get("BATCH_DELAY", 1.0))
        self.max_retries = int(cfg.get("MAX_RETRIES", 2))
        self.min_score = float(cfg.get("MIN_SCORE", 0.5))
        self.criteria_cache_file = Path(
            cfg.get("CRITERIA_CACHE_FILE", "data/ai_criteria_cache.json")
        )
        self.debug = bool(cfg.get("DEBUG", False))

    def _load_interests(self) -> Optional[str]:
        if not self.interests_file.exists():
            print(f"[AI lọc] Không tìm thấy file sở thích: {self.interests_file}")
            return None
        content = self.interests_file.read_text(encoding="utf-8").strip()
        if not content:
            print("[AI lọc] File sở thích trống")
            return None
        return content

    @staticmethod
    def _interests_hash(content: str) -> str:
        """Hash nội dung (bỏ comment/blank) — đổi mô tả → invalidate cache."""
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()

    def _load_cached_tags(self, content_hash: str) -> Optional[List[Dict]]:
        if not self.criteria_cache_file.exists():
            return None
        try:
            data = json.loads(
                self.criteria_cache_file.read_text(encoding="utf-8")
            )
            if data.get("hash") == content_hash and data.get("tags"):
                return data["tags"]
        except Exception:
            pass
        return None

    def _save_cached_tags(self, content_hash: str, tags: List[Dict]) -> None:
        self.criteria_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.criteria_cache_file.write_text(
            json.dumps(
                {"hash": content_hash, "tags": tags}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

    def extract_tags(self, interests_content: str) -> List[Dict]:
        """Phase A: extract structured tags, cache theo hash nội dung."""
        content_hash = self._interests_hash(interests_content)

        cached = self._load_cached_tags(content_hash)
        if cached is not None:
            print(f"[AI lọc] Dùng {len(cached)} tag từ cache")
            return cached

        user = _EXTRACT_USER.replace("{interests_content}", interests_content)
        try:
            response = self.client.complete(user, system=_EXTRACT_SYSTEM)
        except Exception as e:
            print(f"[AI lọc] Extract tag thất bại: {e}")
            return []

        tags = self._parse_tags(response)
        if tags:
            for i, t in enumerate(tags, 1):
                t["id"] = i
            self._save_cached_tags(content_hash, tags)
            print(f"[AI lọc] Extract được {len(tags)} tag")
            for t in tags:
                print(f"   {t['id']}. {t['tag']}: {t.get('description', '')[:60]}")
        else:
            print("[AI lọc] Không extract được tag nào")
        return tags

    @staticmethod
    def _extract_json(response: str) -> Optional[str]:
        if not response or not response.strip():
            return None
        text = response.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1]
            end = text.find("```")
            text = text[:end] if end != -1 else text
        elif "```" in text:
            parts = text.split("```", 2)
            if len(parts) >= 2:
                text = parts[1]
        text = text.strip()
        return text or None

    def _parse_tags(self, response: str) -> List[Dict]:
        json_str = self._extract_json(response)
        if not json_str:
            return []
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []
        tags_raw = data.get("tags", []) if isinstance(data, dict) else []
        tags = []
        for t in tags_raw:
            if isinstance(t, dict) and t.get("tag"):
                tags.append(
                    {
                        "tag": str(t["tag"]).strip(),
                        "description": str(t.get("description", "")).strip(),
                    }
                )
        return tags

    def classify_batch(
        self,
        batch: List[Dict],
        tags: List[Dict],
        interests_content: str,
    ) -> Optional[Dict[int, Dict]]:
        """
        Phase B: classify 1 batch. Trả {title_idx: {tag, score}} hoặc
        None nếu gọi AI thất bại (phân biệt "không khớp" vs "lỗi").
        """
        if not batch or not tags:
            return {}

        tags_list = "\n".join(
            f"{t['id']}. {t['tag']}: {t.get('description', '')}" for t in tags
        )
        news_list = "\n".join(
            f"{t['id']}. [{t.get('source', '')}] {t['title']}" for t in batch
        )

        user = (
            _CLASSIFY_USER.replace("{interests_content}", interests_content)
            .replace("{tags_list}", tags_list)
            .replace("{news_count}", str(len(batch)))
            .replace("{news_list}", news_list)
        )

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.complete(
                    user, system=_CLASSIFY_SYSTEM, max_tokens=4096
                )
                return self._parse_classify(response, batch, tags)
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.batch_delay * (attempt + 2))
        print(f"[AI lọc] Classify batch lỗi sau retry: {last_err}")
        return None

    def _parse_classify(
        self, response: str, batch: List[Dict], tags: List[Dict]
    ) -> Dict[int, Dict]:
        """Parse JSON response; mỗi tin giữ tag điểm cao nhất hợp lệ."""
        json_str = self._extract_json(response)
        if not json_str:
            if self.debug:
                print(f"[AI lọc][DEBUG] Không extract được JSON: {(response or '')[:300]}")
            return {}
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, list):
            return {}

        valid_ids = {t["id"] for t in batch}
        tag_map = {t["id"]: t["tag"] for t in tags}

        best: Dict[int, Dict] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            news_id = item.get("id")
            tag_id = item.get("tag_id")
            if news_id not in valid_ids or tag_id not in tag_map:
                continue
            try:
                score = max(0.0, min(1.0, float(item.get("score", 0.5))))
            except (ValueError, TypeError):
                score = 0.5
            if score < self.min_score:
                continue
            existing = best.get(news_id)
            if existing is None or score > existing["score"]:
                best[news_id] = {
                    "tag": tag_map[tag_id],
                    "tag_id": tag_id,
                    "score": score,
                }
        return best

    def filter_titles(self, all_results: Dict) -> Optional[Dict[str, Dict]]:
        """
        Chạy full pipeline A+B trên tất cả title.

        Returns:
            {title: {"tag": str, "score": float}} — chỉ tin khớp;
            None nếu AI không khả dụng / không extract được tag
            (caller fallback keyword filter).
        """
        if not self.client.is_configured():
            print("[AI lọc] AI client chưa cấu hình → bỏ qua")
            return None

        interests = self._load_interests()
        if not interests:
            return None

        tags = self.extract_tags(interests)
        if not tags:
            return None

        # Gom title duy nhất (dedup đã chạy trước nên trùng cross-source đã gộp)
        unique_titles: List[Dict] = []
        seen = set()
        for source_id, titles in all_results.items():
            for title in titles.keys():
                if title not in seen:
                    seen.add(title)
                    unique_titles.append(
                        {"id": len(unique_titles) + 1, "title": title, "source": source_id}
                    )

        if not unique_titles:
            return {}

        print(f"[AI lọc] Classify {len(unique_titles)} title với {len(tags)} tag")

        result: Dict[str, Dict] = {}
        failed_batches = 0
        for start in range(0, len(unique_titles), self.batch_size):
            batch = unique_titles[start : start + self.batch_size]
            classified = self.classify_batch(batch, tags, interests)
            if classified is None:
                # Batch lỗi → giữ nguyên các tin trong batch (không loại oan)
                failed_batches += 1
                continue
            for item in batch:
                hit = classified.get(item["id"])
                if hit:
                    result[item["title"]] = hit
            if start + self.batch_size < len(unique_titles):
                time.sleep(self.batch_delay)

        if failed_batches:
            print(f"[AI lọc] {failed_batches} batch lỗi → giữ nguyên tin trong các batch đó")
        print(f"[AI lọc] Khớp {len(result)}/{len(unique_titles)} title")
        return result
