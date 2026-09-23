"""
Frequency words processor for TrendRadar.

Handles loading and matching frequency word configurations.

File syntax (ported & extended from upstream TrendRadar):
- Blank line separates word groups
- Lines starting with "#" are comments (skipped)
- [GroupName] as first line of a group: display alias for that group
- [GLOBAL_FILTER] / [WORD_GROUPS]: section markers (upstream compat)
- word: normal word (OR within group)
- +word: required word (AND, all required words must appear)
- !word: filter word — global exclusion
- @N: max titles displayed for this group in the report
- /pattern/: regex (case-insensitive) — usable for normal/required/filter words
- word => alias: display name used in place of the raw word when no group alias
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


def _parse_word(word: str) -> Dict:
    """
    Parse một dòng từ khóa thành cấu trúc match.

    Returns:
        Dict với keys: word (pattern text hoặc literal), is_regex,
        pattern (compiled regex hoặc None), display_name (alias hoặc None)
    """
    display_name = None

    # 1. Tách display name "=> alias" trước
    if "=>" in word:
        parts = word.split("=>")
        word_config = parts[0].strip()
        if len(parts) > 1 and parts[1].strip():
            display_name = parts[1].strip()
    else:
        word_config = word.strip()

    # 2. Regex /pattern/ (cho phép flags đuôi, luôn IGNORECASE)
    regex_match = re.match(r"^/(.+)/[a-z]*$", word_config)
    if regex_match:
        pattern_str = regex_match.group(1)
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            return {
                "word": pattern_str,
                "is_regex": True,
                "pattern": pattern,
                "display_name": display_name,
            }
        except re.error as e:
            print(f"Warning: regex không hợp lệ '/{pattern_str}/': {e}")

    return {
        "word": word_config,
        "is_regex": False,
        "pattern": None,
        "display_name": display_name,
    }


def _word_matches(word_config, title_lower: str) -> bool:
    """
    Kiểm tra một từ khóa (str hoặc dict đã parse) có khớp title không.

    Args:
        word_config: str (legacy) hoặc dict từ _parse_word
        title_lower: title đã lower()
    """
    if isinstance(word_config, str):
        return word_config.lower() in title_lower

    if word_config.get("is_regex") and word_config.get("pattern"):
        return bool(word_config["pattern"].search(title_lower))
    return word_config["word"].lower() in title_lower


def load_frequency_words(
    frequency_file: str = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Load frequency words configuration.

    Args:
        frequency_file: Path to frequency words file

    Returns:
        Tuple of (processed_groups, filter_words)
        - processed_groups: [{required, normal, group_key, display_name, max_count}]
        - filter_words: [word_config dict] — global exclusion (hỗ trợ regex)

    Raises:
        FileNotFoundError: If frequency words file doesn't exist
    """
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        # Thử tìm trong config/custom/keyword/ (upstream compat)
        custom_path = Path("config/custom/keyword") / frequency_file
        if custom_path.exists():
            frequency_path = custom_path
        else:
            raise FileNotFoundError(f"từ tần suấtfile {frequency_file} không tồn tại")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []

    # Mặc định khu vực WORD_GROUPS (tương thích file cũ)
    current_section = "WORD_GROUPS"

    for group in word_groups:
        # Bỏ dòng trống và comment (#) — comment giờ là comment thật
        lines = [
            line.strip()
            for line in group.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        if not lines:
            continue

        # Kiểm tra section marker
        if lines[0].startswith("[") and lines[0].endswith("]"):
            section_name = lines[0][1:-1].upper()
            if section_name in ("GLOBAL_FILTER", "WORD_GROUPS"):
                current_section = section_name
                lines = lines[1:]
                if not lines:
                    continue

        # Khu vực GLOBAL_FILTER: mọi dòng đều là từ lọc toàn cục
        if current_section == "GLOBAL_FILTER":
            for line in lines:
                if line.startswith(("!", "+", "@")):
                    continue
                if line:
                    filter_words.append(_parse_word(line))
            continue

        words = lines
        group_alias = None

        # Dòng đầu [Tên nhóm] → alias hiển thị của group
        if words and words[0].startswith("[") and words[0].endswith("]"):
            potential_alias = words[0][1:-1].strip()
            if potential_alias.upper() not in ("GLOBAL_FILTER", "WORD_GROUPS"):
                group_alias = potential_alias
                words = words[1:]

        group_required_words = []
        group_normal_words = []
        group_max_count = 0

        for word in words:
            if word.startswith("@"):
                # @N: giới hạn số tin hiển thị của group
                try:
                    count = int(word[1:])
                    if count > 0:
                        group_max_count = count
                except (ValueError, IndexError):
                    pass
            elif word.startswith("!"):
                filter_words.append(_parse_word(word[1:]))
            elif word.startswith("+"):
                group_required_words.append(_parse_word(word[1:]))
            else:
                group_normal_words.append(_parse_word(word))

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(w["word"] for w in group_normal_words)
            else:
                group_key = " ".join(w["word"] for w in group_required_words)

            # Tên hiển thị: [group alias] > nối alias/dòng > keywords
            if group_alias:
                display_name = group_alias
            else:
                display_parts = [
                    w.get("display_name") or w["word"]
                    for w in group_normal_words + group_required_words
                ]
                display_name = " / ".join(display_parts) if display_parts else None

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                    "display_name": display_name,
                    "max_count": group_max_count,
                }
            )

    return processed_groups, filter_words
