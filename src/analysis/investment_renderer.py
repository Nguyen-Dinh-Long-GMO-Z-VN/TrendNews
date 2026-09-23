"""
HTML renderer for investment analysis section.
Generates a self-contained HTML block with scoped ia- CSS classes.
"""

from typing import Dict
from .asset_classifier import ASSET_DISPLAY_NAMES

ASSET_ICONS: Dict[str, str] = {
    "gold": "🥇",
    "forex": "💱",
    "stocks_us": "🇺🇸",
    "stocks_vn": "🇻🇳",
    "stocks_cn": "🇨🇳",
    "crypto": "₿",
    "commodities": "🛢️",
}

SENTIMENT_CONFIG: Dict[str, Dict] = {
    "bullish": {"label": "Tăng", "color": "#22c55e", "bg": "#f0fdf4", "badge": "🟢"},
    "bearish": {"label": "Giảm", "color": "#ef4444", "bg": "#fef2f2", "badge": "🔴"},
    "neutral": {"label": "Trung tính", "color": "#f59e0b", "bg": "#fffbeb", "badge": "🟡"},
}

CONFIDENCE_LABELS: Dict[str, str] = {
    "high": "Độ tin cậy cao",
    "medium": "Độ tin cậy vừa",
    "low": "Độ tin cậy thấp",
}

CSS = """
<style>
.ia-section {
    margin: 16px 0;
    padding: 16px;
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.ia-section-title {
    font-size: 15px;
    font-weight: 700;
    color: #1f2937;
    margin: 0 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #f3f4f6;
    display: flex;
    align-items: center;
    gap: 8px;
}
.ia-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
}
.ia-card {
    border-radius: 10px;
    padding: 12px;
    border: 1px solid #e5e7eb;
    background: #fafafa;
}
.ia-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.ia-asset-name {
    font-size: 13px;
    font-weight: 700;
    color: #374151;
}
.ia-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    white-space: nowrap;
}
.ia-summary {
    font-size: 12px;
    color: #4b5563;
    margin-bottom: 8px;
    line-height: 1.5;
}
.ia-label {
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin: 6px 0 2px;
}
.ia-text {
    font-size: 12px;
    color: #374151;
    line-height: 1.5;
}
.ia-factors {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
}
.ia-factor-tag {
    font-size: 11px;
    background: #f3f4f6;
    color: #374151;
    padding: 2px 7px;
    border-radius: 6px;
}
.ia-no-key {
    font-size: 12px;
    color: #9ca3af;
    text-align: center;
    padding: 12px;
}
.ia-confidence {
    font-size: 10px;
    color: #9ca3af;
    margin-top: 6px;
}
@media (max-width: 480px) {
    .ia-grid { grid-template-columns: 1fr; }
}
</style>
"""


def render_investment_section(analyses: Dict, configured: bool = True) -> str:
    """
    Render the full investment analysis HTML section.

    Args:
        analyses: Dict mapping asset_id -> analysis result dict
        configured: False if no AI API key is set

    Returns:
        HTML string
    """
    html = CSS
    html += '\n<div class="ia-section">\n'
    html += '  <div class="ia-section-title">📊 Phân tích xu hướng đầu tư</div>\n'

    if not configured:
        html += (
            '  <div class="ia-no-key">'
            "Chưa cấu hình AI API key. Thêm <code>AI_API_KEY</code> vào file <code>.env</code> để bật tính năng này."
            "</div>\n"
        )
        html += "</div>\n"
        return html

    if not analyses:
        html += '  <div class="ia-no-key">Không đủ tin tức đầu tư để phân tích hôm nay.</div>\n'
        html += "</div>\n"
        return html

    html += '  <div class="ia-grid">\n'

    for asset_id, result in analyses.items():
        sentiment = result.get("sentiment", "neutral").lower()
        if sentiment not in SENTIMENT_CONFIG:
            sentiment = "neutral"
        sc = SENTIMENT_CONFIG[sentiment]

        asset_name = ASSET_DISPLAY_NAMES.get(asset_id, asset_id)
        icon = ASSET_ICONS.get(asset_id, "📈")
        summary = result.get("summary", "")
        short_term = result.get("short_term", "")
        long_term = result.get("long_term", "")
        confidence = result.get("confidence", "medium")
        key_factors = result.get("key_factors", [])

        html += f'    <div class="ia-card" style="background:{sc["bg"]};border-color:{sc["color"]}33">\n'
        html += '      <div class="ia-card-header">\n'
        html += f'        <span class="ia-asset-name">{icon} {_esc(asset_name)}</span>\n'
        html += (
            f'        <span class="ia-badge" style="background:{sc["color"]}22;color:{sc["color"]}">'
            f'{sc["badge"]} {sc["label"]}</span>\n'
        )
        html += "      </div>\n"

        if summary:
            html += f'      <div class="ia-summary">{_esc(summary)}</div>\n'

        if short_term:
            html += '      <div class="ia-label">Ngắn hạn (trading)</div>\n'
            html += f'      <div class="ia-text">{_esc(short_term)}</div>\n'

        if long_term:
            html += '      <div class="ia-label">Dài hạn (đầu tư)</div>\n'
            html += f'      <div class="ia-text">{_esc(long_term)}</div>\n'

        if key_factors:
            html += '      <div class="ia-label">Yếu tố chính</div>\n'
            html += '      <div class="ia-factors">\n'
            for factor in key_factors[:5]:
                html += f'        <span class="ia-factor-tag">{_esc(str(factor))}</span>\n'
            html += "      </div>\n"

        conf_label = CONFIDENCE_LABELS.get(confidence, "")
        if conf_label:
            html += f'      <div class="ia-confidence">{conf_label}</div>\n'

        html += "    </div>\n"

    html += "  </div>\n"
    html += "</div>\n"
    return html


def _esc(text) -> str:
    """Basic HTML escaping. Accepts any type and converts to string first."""
    if not isinstance(text, str):
        if isinstance(text, (dict, list)):
            import json as _json
            text = _json.dumps(text, ensure_ascii=False)
        else:
            text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
