from typing import Dict
from src.utils.text_utils import clean_title, html_escape
from src.utils.format_utils import format_rank_display

class TelegramRenderer:
    @staticmethod
    def format_title(title_data: Dict, show_source: bool = True) -> str:
        """
        Format title for Telegram platform.
        """
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "telegram"
        )

        link_url = title_data["mobile_url"] or title_data["url"]
        cleaned_title = clean_title(title_data.get("title_vi") or title_data["title"])

        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        source_label = title_data["source_name"]
        if title_data.get("source_count", 1) > 1:
            source_label += f" +{title_data['source_count'] - 1}"

        if show_source:
            result = f"[{source_label}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}lần)</code>"

        return result
