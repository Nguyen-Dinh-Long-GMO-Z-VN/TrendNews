"""
Investment trend analyzer.
Extracts news from stats, classifies by asset class, calls AI, returns HTML.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional

from .asset_classifier import ASSET_DISPLAY_NAMES, classify_news
from .ai_client import AIClient
from .investment_renderer import render_investment_section

CACHE_FILE = Path("data/analysis_cache.json")


def _load_cache() -> Dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


_CACHE_KEY_TOP_N = 20


def _cache_key(titles: List[str]) -> str:
    """Hash top-N titles để tránh full invalidation khi có tin nhỏ thay đổi ở cuối list."""
    top_titles = sorted(titles[:_CACHE_KEY_TOP_N])
    combined = "\n".join(top_titles)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def _is_cache_valid(entry: Dict, cache_hours: int) -> bool:
    ts = entry.get("timestamp", 0)
    return (time.time() - ts) < cache_hours * 3600


class InvestmentAnalyzer:
    """
    Main investment analysis orchestrator.
    Usage:
        analyzer = InvestmentAnalyzer(min_news_threshold=3, cache_hours=6)
        html = analyzer.analyze(stats)
    """

    def __init__(self, min_news_threshold: int = 3, cache_hours: int = 6):
        self.min_threshold = min_news_threshold
        self.cache_hours = cache_hours
        self.ai = AIClient()

    def analyze(self, stats: List[Dict]) -> str:
        """
        Main entry point. Takes stats list from count_word_frequency.
        Returns HTML string (empty string on failure).
        """
        if not self.ai.is_configured():
            return render_investment_section({}, configured=False)

        # Extract all titles from stats
        all_titles = self._extract_titles(stats)
        if not all_titles:
            return ""

        # Classify into asset classes
        classified = classify_news(all_titles)

        # Load cache
        cache = _load_cache()
        analyses: Dict[str, Dict] = {}

        for asset_id, titles in classified.items():
            if len(titles) < self.min_threshold:
                continue

            ck = _cache_key(titles)
            if ck in cache and _is_cache_valid(cache[ck], self.cache_hours):
                analyses[asset_id] = cache[ck]["result"]
                continue

            result = self._analyze_asset(asset_id, titles)
            if result:
                analyses[asset_id] = result
                cache[ck] = {"timestamp": time.time(), "result": result}

        _save_cache(cache)

        if not analyses:
            return ""

        return render_investment_section(analyses, configured=True)

    def _extract_titles(self, stats: List[Dict]) -> List[str]:
        """Extract all unique title strings from the stats structure."""
        titles = []
        seen = set()
        for group in stats:
            for title_data in group.get("titles", []):
                title = title_data.get("title", "").strip()
                if title and title not in seen:
                    titles.append(title)
                    seen.add(title)
        return titles

    def _analyze_asset(self, asset_id: str, titles: List[str]) -> Optional[Dict]:
        """Call AI for a single asset class. Returns parsed JSON dict or None."""
        asset_name = ASSET_DISPLAY_NAMES.get(asset_id, asset_id)
        news_list = "\n".join(f"- {t}" for t in titles[:80])

        prompt = f"""Bạn là chuyên gia phân tích tài chính và đầu tư, đang hỗ trợ một hệ thống trading tự động theo tin tức (news-driven trading system).

Dưới đây là {len(titles[:80])} tin tức liên quan đến **{asset_name}** được thu thập trong ngày hôm nay, bao gồm cả tin quốc tế và trong nước. Mỗi dòng có thể là tiêu đề, tóm tắt hoặc đoạn trích từ bài báo:

{news_list}

NHIỆM VỤ CỦA BẠN
- Chỉ được sử dụng thông tin có trong tập tin tức ở trên để suy luận. Không được dùng thêm bất kỳ kiến thức bên ngoài nào (kể cả giá hiện tại, mức P/E, dữ liệu lịch sử, biểu đồ, hoặc "common sense" nếu không xuất hiện trong tin).
- Nếu một thông tin nào đó không xuất hiện rõ ràng trong tin (ví dụ: mức giá cụ thể, vùng hỗ trợ/kháng cự chính xác, khối lượng giao dịch), hãy ghi rõ "Không thấy thông tin trong bộ tin tức hôm nay" thay vì tự ước lượng hoặc bịa số.
- Khi tin tức chỉ nói chung về vĩ mô/ngành (ví dụ: chiến tranh, lãi suất, giá dầu, chính sách nhà nước) chứ không nhắc trực tiếp tới {asset_name}, bạn vẫn phải phân tích ảnh hưởng GIÁN TIẾP tới {asset_name} dựa trên logic tài chính cơ bản, nhưng không được chèn số liệu cụ thể nếu tin không có.

YÊU CẦU VỀ THỜI HẠN VÀ ĐỐI TƯỢNG
- "short_term": dành cho TRADER ngắn hạn với khung thời gian 1–7 ngày tới. Tập trung vào biến động ngắn hạn, catalyst sắp diễn ra trong vài ngày (sự kiện, số liệu, phát biểu, quyết sách), mức biến động có thể cao, và khuyến nghị hành động cụ thể (mua/bán/chờ) có kèm điều kiện.
- "long_term": dành cho NHÀ ĐẦU TƯ theo dõi 1–3 tháng tới. Tập trung vào luận điểm (thesis) trung hạn, thay đổi cấu trúc cung cầu, chính sách, triển vọng ngành/doanh nghiệp, và đề xuất cách phân bổ tỷ trọng trong danh mục.

YÊU CẦU VỀ JSON
- Chỉ TRẢ LỜI BẰNG MỘT OBJECT JSON DUY NHẤT, KHÔNG THÊM BẤT KỲ TEXT NÀO NGOÀI JSON (không markdown, không ```).
- JSON phải HOÀN TOÀN HỢP LỆ: không comment, không trailing comma, không thêm trường ngoài schema, không xuống dòng bên trong key, và phải dùng dấu ngoặc kép ".
- GIỚI HẠN ĐỘ DÀI: Mỗi string field tối đa 80 từ. Mỗi phần tử array tối đa 40 từ. Tổng response phải dưới 800 từ.
- Nội dung (value) được viết bằng tiếng Việt, nhưng giữ nguyên tên các key đúng theo schema.
- Nếu cần trích dẫn câu hoặc tiêu đề từ tin tức, phải đảm bảo không làm hỏng cấu trúc JSON (tránh dùng dấu " không escape đúng cách).

Schema JSON BẮT BUỘC như sau (không được thêm hoặc bớt key):
{{
  "summary": "Mô tả toàn cảnh thị trường {asset_name} hôm nay trong 3-5 câu: bối cảnh vĩ mô, diễn biến chính từ các tin tức, bất kỳ mức giá/chỉ số cụ thể nào NẾU ĐƯỢC ĐỀ CẬP trong tin, và tâm lý nhà đầu tư (thận trọng/lạc quan/hoảng loạn/...)",
  "short_term": "Nhận định chi tiết cho trader trong 1-7 ngày tới: xu hướng kỳ vọng (tăng/giảm/dao động), vùng hỗ trợ/kháng cự quan trọng NẾU tin có gợi ý (ví dụ: nhắc đến các mốc giá, vùng giá, chỉ số), catalyst ngắn hạn cần theo dõi (sự kiện, báo cáo, phát biểu, chính sách), mức độ rủi ro, và khuyến nghị hành động cụ thể (mua/bán/chờ, có thể kèm điều kiện và mức ưu tiên). Nếu không có số liệu cụ thể trong tin thì chỉ mô tả định tính, KHÔNG tự tạo số mới.",
  "long_term": "Phân tích chiến lược cho nhà đầu tư dài hạn 1-3 tháng: thesis đầu tư chính dựa trên các tin tức (ví dụ: thay đổi cung cầu, chính sách, lợi thế cạnh tranh, rủi ro ngành), các kịch bản có thể xảy ra (tích cực/trung tính/tiêu cực) với mô tả ngắn gọn, các yếu tố nền tảng dài hạn (vĩ mô, ngành, doanh nghiệp nếu có), và gợi ý phân bổ tỷ trọng trong danh mục (ví dụ: 0-5-10-20 phần trăm) theo từng mức khẩu vị rủi ro. Nếu tin tức rất tiêu cực, có thể khuyến nghị đứng ngoài.",
  "sentiment": "Một trong ba giá trị: bullish, bearish hoặc neutral, phản ánh TỔNG HỢP cảm xúc từ toàn bộ tin tức liên quan đến {asset_name} hôm nay.",
  "confidence": "Mức độ tự tin vào đánh giá: high, medium hoặc low. Chỉ high khi tin tức rõ ràng, nhất quán và có nhiều nguồn trùng lặp; low khi tin ít, mâu thuẫn hoặc quá chung chung.",
  "key_factors": [
    "Yếu tố tác động TÍCH CỰC quan trọng nhất cùng giải thích ngắn, trích ra từ các tin liên quan (ví dụ: kết quả kinh doanh, nâng hạng, dòng vốn vào, chính sách hỗ trợ)",
    "Yếu tố tác động TIÊU CỰC quan trọng nhất cùng giải thích ngắn (ví dụ: rủi ro pháp lý, chiến tranh, suy giảm nhu cầu, bán tháo lớn)",
    "Yếu tố địa chính trị/kinh tế vĩ mô đang chi phối {asset_name} (ví dụ: chiến tranh, lãi suất, lạm phát, chính sách tiền tệ, kiểm soát vốn)",
    "Yếu tố kỹ thuật hoặc dòng vốn đáng chú ý NẾU có gợi ý trong tin (dòng tiền ETF, khối ngoại, khối tự doanh, tin đồn margin call, biến động volume/volatility) – nếu không có thì mô tả chung ở mức định tính, không bịa số",
    "Sự kiện/dữ liệu sắp tới cần theo dõi được đề cập trong tin (ví dụ: cuộc họp ngân hàng trung ương, báo cáo kinh tế, earnings, deadline chính sách). Nếu không có thông tin về sự kiện cụ thể, nêu các mốc vĩ mô chung cần chú ý."
  ],
  "risks": [
    "Rủi ro lớn nhất có thể đảo chiều xu hướng hiện tại đối với {asset_name}, dựa trên các tin tiêu cực hoặc bất ổn được nhắc đến",
    "Rủi ro từ chính sách hoặc địa chính trị (quy định mới, trừng phạt, chiến tranh, kiểm soát vốn, thay đổi thuế, can thiệp của cơ quan quản lý)",
    "Rủi ro thanh khoản hoặc kỹ thuật (ví dụ: biến động quá mạnh, gap lớn, thanh khoản suy giảm, nguy cơ margin call, ETF/whale có thể xả hàng) – chỉ nêu những gì có logic từ tin tức, không bịa thêm dữ liệu."
  ],
  "opportunities": [
    "Cơ hội đầu tư NGẮN HẠN cụ thể cho trader (ví dụ: giao dịch theo tin, theo đợt panic sell/pump, theo sự kiện sắp diễn ra) kèm mô tả cách tận dụng, nhưng không ghi mức giá cụ thể nếu tin không có",
    "Cơ hội TÍCH LŨY DÀI HẠN (nếu có) dựa trên các tin mang tính cấu trúc (ví dụ: xu hướng ngành, chuyển dịch chuỗi cung ứng, cải thiện cơ bản), hoặc ghi rõ nếu hiện tại không phù hợp để tích lũy dài hạn."
  ],
  "recommendation": "Khuyến nghị hành động cụ thể và rõ ràng cho nhà đầu tư ở thời điểm hiện tại dựa trên toàn bộ tin tức: nên làm gì ngay bây giờ với {asset_name} (mua/bán/giảm tỷ trọng/giữ/chờ thêm dữ liệu), nêu điều kiện (ví dụ: chỉ nên hành động nếu rủi ro A giảm bớt), gợi ý biên độ tỷ lệ danh mục (ví dụ: tối đa X phần trăm NAV), và nhắc lại các rủi ro chính cần chấp nhận khi làm theo khuyến nghị. Không ghi mức giá cụ thể nếu tin không cung cấp."
}}"""

        try:
            raw = self.ai.complete(prompt)
            result = self._parse_json_response(raw)
            if result is None:
                print(f"[InvestmentAnalyzer] JSON parse failed for {asset_id}, raw length={len(raw)}, first 100: {raw[:100]!r}, last 100: {raw[-100:]!r}")
            return result
        except Exception as e:
            print(f"[InvestmentAnalyzer] AI call failed for {asset_id}: {type(e).__name__}: {e}")
            return None

    def _parse_json_response(self, raw: str) -> Optional[Dict]:
        """Extract and parse JSON from AI response using multiple strategies."""
        raw = raw.strip()

        # Strategy 1: direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract from markdown code block
        for marker in ["```json", "```"]:
            if marker in raw:
                start = raw.find(marker) + len(marker)
                end = raw.find("```", start)
                if end > start:
                    try:
                        return json.loads(raw[start:end].strip())
                    except json.JSONDecodeError:
                        pass

        # Strategy 3: balanced-brace extraction (handles COT/extra text around JSON)
        first_brace = raw.find("{")
        if first_brace >= 0:
            depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(raw[first_brace:], start=first_brace):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\" and in_string:
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[first_brace : i + 1])
                        except json.JSONDecodeError:
                            break

        return None
