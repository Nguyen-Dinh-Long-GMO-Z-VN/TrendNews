"""
AI title translator — dịch tiêu đề tin tức sang tiếng Việt.

Port ý tưởng từ upstream TrendRadar (ai/translator.py):
- Batch theo số thứ tự [N], parse response theo index trả về
  (tránh lệch vị trí khi AI bỏ sót/xáo thứ tự).
- Title nào dịch lỗi / trống → giữ nguyên bản gốc.
- Cache persistent theo md5(title) → lần crawl sau không tốn token lại.
- Bỏ qua title đã là tiếng Việt (detect bằng charset đặc trưng).
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from .ai_client import AIClient

# Ký tự đặc trưng tiếng Việt (dấu + chữ đặc biệt)
_VI_CHARS = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """Bạn là trợ lý dịch thuật chuyên nghiệp đa ngôn ngữ, chuyên tin công nghệ. Nhiệm vụ: dịch tiêu đề tin tức sang {target_language}, tự nhiên như báo công nghệ bản địa viết.

Yêu cầu:
1. Truyền tải đúng ý nghĩa gốc, không bỏ sót thông tin chính.
2. Giữ tiêu đề hấp dẫn nhưng không câu view.
3. Danh từ riêng (người, địa danh, tổ chức, sản phẩm, model AI, framework) có tên phổ biến thì dùng tên phổ biến (vd: OpenAI, ChatGPT, NVIDIA), nếu không giữ nguyên.
4. ⚠️ THUẬT NGỮ CÔNG NGHỆ — quy tắc bắt buộc:
   - Cộng đồng tech Việt Nam dùng nguyên tiếng Anh cho nhiều thuật ngữ. GIỮ NGUYÊN, TUYỆT ĐỐI KHÔNG dịch sát nghĩa đen:
     agent / AI agent / 智能体 / 智能代理 → "AI agent" hoặc "agent" (KHÔNG "tác nhân")
     coding agent / vibe coding → giữ nguyên
     prompt / context / context window / token / jailbreak → giữ nguyên
     benchmark / pipeline / framework / embedding / inference → giữ nguyên
     RAG / fine-tuning / LoRA / RLHF / MCP / function calling → giữ nguyên
     open source / closed source / self-hosted → "mã nguồn mở" / "mã đóng" / "tự host"
   - Thuật ngữ có từ Việt phổ biến thì dịch: model → "mô hình", training → "huấn luyện", reasoning → "suy luận", release → "ra mắt/phát hành", vulnerability → "lỗ hổng".
   - Khi phân vân giữa dịch và giữ nguyên một thuật ngữ kỹ thuật → chọn giữ nguyên tiếng Anh.
5. Input có đánh số [1], [2], [3]... thì output PHẢI giữ nguyên đánh số và thứ tự, mỗi số tương ứng một bản dịch. Không được bỏ sót, gộp, hay thêm mục nào.
6. ⚠️ Trọng điểm: input có thể chứa danh sách hỗn hợp nhiều ngôn ngữ. Kiểm tra TỪNG dòng. Dòng nào không phải {target_language} thì PHẢI dịch sang {target_language}. Tuyệt đối không giữ nguyên văn ngoại ngữ (trừ danh từ riêng và thuật ngữ quy tắc 4). Kể cả khi 99% đã là ngôn ngữ đích, vẫn không được bỏ qua 1% còn lại.
7. Chỉ xuất văn bản {target_language}. Cấm dạng "nguyên văn + bản dịch". Không thêm giải thích, không thêm nội dung ngoài các dòng đánh số."""

_USER_TEMPLATE = """Dịch các nội dung sau sang {target_language}:

{content}

Chỉ xuất kết quả dịch, mỗi dòng một mục với đúng đánh số."""


class TitleTranslator:
    """
    Dịch batch tiêu đề sang tiếng Việt (hoặc target_language khác).

    Usage:
        translator = TitleTranslator(client, cfg)
        vi_map = translator.translate_map(titles)  # {title: title_vi}
    """

    def __init__(self, client: AIClient, config: Dict = None):
        cfg = config or {}
        self.client = client
        self.enabled = cfg.get("ENABLED", True)
        self.target_language = cfg.get("LANGUAGE", "Vietnamese")
        self.batch_size = int(cfg.get("BATCH_SIZE", 50))
        self.batch_delay = float(cfg.get("BATCH_DELAY", 1.0))
        self.max_retries = int(cfg.get("MAX_RETRIES", 2))
        self.cache_file = Path(cfg.get("CACHE_FILE", "data/translation_cache.json"))
        self._cache = self._load_cache()

    # Tăng version khi đổi prompt/thuật ngữ — cache cũ tự invalidate
    CACHE_VERSION = 2

    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Format mới: {"version": N, "items": {md5: vi}}
                if isinstance(data, dict) and "items" in data:
                    if data.get("version") == self.CACHE_VERSION:
                        return data["items"]
                    return {}  # version cũ → bỏ cache
                # Format cũ (v1, prompt cũ): {md5: vi} phẳng → bỏ, dịch lại
                return {}
            except Exception:
                pass
        return {}

    def _save_cache(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(
                {"version": self.CACHE_VERSION, "items": self._cache},
                f,
                ensure_ascii=False,
            )

    @staticmethod
    def _key(title: str) -> str:
        return hashlib.md5(title.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _looks_vietnamese(text: str) -> bool:
        """Title có ký tự đặc trưng tiếng Việt → coi như đã là tiếng Việt."""
        return bool(_VI_CHARS.search(text))

    def translate_map(self, titles: List[str]) -> Dict[str, str]:
        """
        Dịch toàn bộ danh sách title. Trả về {title_gốc: title_vi}.
        Title không dịch được giữ nguyên bản gốc.
        """
        result = {}
        if not self.enabled or not self.client.is_configured() or not titles:
            return result

        pending = []
        for title in titles:
            if not title or not title.strip():
                continue
            key = self._key(title)
            cached = self._cache.get(key)
            if cached:
                result[title] = cached
            elif self._looks_vietnamese(title):
                # Đã là tiếng Việt → cache luôn, không tốn token
                self._cache[key] = title
                result[title] = title
            else:
                pending.append(title)

        if not pending:
            return result

        print(f"[Dịch] {len(result)} title có sẵn cache/tiếng Việt, {len(pending)} title cần dịch")

        for start in range(0, len(pending), self.batch_size):
            batch = pending[start : start + self.batch_size]
            translated = self._translate_batch(batch)
            for title, vi in zip(batch, translated):
                if vi and vi.strip():
                    self._cache[self._key(title)] = vi.strip()
                    result[title] = vi.strip()
                # Lỗi/trống → không cache → title giữ nguyên gốc, retry lần sau
            self._save_cache()  # lưu sau mỗi batch — crash vẫn giữ được tiến độ
            if start + self.batch_size < len(pending):
                time.sleep(self.batch_delay)

        return result

    def _translate_batch(self, batch: List[str]) -> List[str]:
        """Dịch 1 batch, trả list kết quả cùng độ dài (rỗng nếu thất bại)."""
        numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(batch, 1))
        system = _SYSTEM_PROMPT.replace("{target_language}", self.target_language)
        user = _USER_TEMPLATE.replace("{target_language}", self.target_language).replace(
            "{content}", numbered
        )

        max_output = max(4096, len(batch) * 80)
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.complete(
                    user, system=system, max_tokens=max_output
                )
                return self._parse_numbered(response, len(batch))
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.batch_delay * (attempt + 2))
        print(f"[Dịch] Batch thất bại sau {self.max_retries + 1} lần thử: {last_err}")
        return [""] * len(batch)

    @staticmethod
    def _parse_numbered(response: str, expected: int) -> List[str]:
        """
        Parse response định dạng [N] —回填 theo index AI trả về,
        không theo vị trí dòng (tránh lệch khi AI sót số).
        """
        results: Dict[int, str] = {}
        current_idx = None
        current_text: List[str] = []

        for line in response.strip().split("\n"):
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                bracket_end = stripped.index("]")
                try:
                    idx = int(stripped[1:bracket_end])
                    if current_idx is not None:
                        results[current_idx] = "\n".join(current_text).strip()
                    current_idx = idx
                    current_text = [stripped[bracket_end + 1 :].strip()]
                    continue
                except ValueError:
                    pass
            if current_idx is not None:
                current_text.append(line)

        if current_idx is not None:
            results[current_idx] = "\n".join(current_text).strip()

        return [results.get(i, "") for i in range(1, expected + 1)]
