from typing import List, Dict, Optional, Tuple
from src.config import CONFIG
from src.utils import is_first_crawl_today, format_time_display
from src.processors.frequency_words import _word_matches


def matches_word_groups(
    title: str, word_groups: List[Dict], filter_words: List
) -> bool:
    """检查标题là否khớp词组规则"""
    # Kiểm tra kiểu phòng thủ：đảm bảo title là chuỗi hợp lệ
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if not title.strip():
        return False

    # Nếu không cấu hình nhóm từ，thì khớp tất cả tiêu đề（hỗ trợ hiển thị tất cả tin tức）
    if not word_groups:
        return True

    title_lower = title.lower()

    # Kiểm tra từ lọc
    if any(_word_matches(filter_word, title_lower) for filter_word in filter_words):
        return False

    # Kiểm tra khớp nhóm từ
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]

        # Kiểm tra từ bắt buộc
        if required_words:
            all_required_present = all(
                _word_matches(req_word, title_lower) for req_word in required_words
            )
            if not all_required_present:
                continue

        # Kiểm tra từ thông thường
        if normal_words:
            any_normal_present = any(
                _word_matches(normal_word, title_lower)
                for normal_word in normal_words
            )
            if not any_normal_present:
                continue

        return True

    return False


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
) -> Tuple[List[Dict], int]:
    """统计词频，支持必须词、từ tần suất、lọc词，并标记mới标题"""

    # Nếu không cấu hình nhóm từ，tạomột包含所cómới闻của虚拟词组
    if not word_groups:
        print("Cấu hình từ tần suất trống，sẽ hiển thị tất cả tin tức")
        word_groups = [
            {
                "required": [],
                "normal": [],
                "group_key": "tất cả tin tức",
                "display_name": "Tất cả tin tức",
                "max_count": 0,
            }
        ]
        filter_words = []  # 清空lọc词，显示所cótin tức

    is_first_today = is_first_crawl_today()

    # Xác định nguồn dữ liệu xử lý và logic đánh dấu mới
    if mode == "incremental":
        if is_first_today:
            # Chế độ tăng dần + Lần đầu trong ngày：xử lý tất cả tin tức，đều đánh dấu là mới
            results_to_process = results
            all_news_are_new = True
        else:
            # Chế độ tăng dần + Không phải lần đầu trong ngày：chỉ xử lý tin tức mới
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # current Chế độ：chỉ xử lý tin tức lô hiện tại，nhưng thông tin thống kê từ toàn bộ lịch sử
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

            # 只Xử lý last_time tin tức bằng thời gian mới nhất
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles

                print(
                    f"bảng xếp hạng hiện tạichế độ：nhất新giờ间 {latest_time}，筛选出 {sum(len(titles) for titles in results_to_process.values())} tinbảng xếp hạng hiện tạitin tức"
                )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # Chế độ tổng hợp trong ngày：xử lý tất cả tin tức
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "hiển thị tất cả"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "tất cả tin tức"
            else "từ tần suấtlọc"
        )
        print(f"Chế độ tổng hợp trong ngày：Xử lý {total_input_news} tin tức，Chế độ：{filter_status}")

    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}

    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}

    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)

        if source_id not in processed_titles:
            processed_titles[source_id] = {}

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            # Sử dụng logic khớp thống nhất
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words
            )

            if not matches_frequency_words:
                continue

            # Nếu làChế độ tăng dầnhoặc current chế độ lần đầu，thống kê số lượng tin tức mới khớp
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1

            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")

            # Tìm nhóm từ khớp（chuyển đổi phòng thủ đảm bảo an toàn kiểu）
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]

                # Nếu là"tất cả tin tức"Chế độ，tất cả tiêu đề đều khớp cái đầu tiên（duy nhất）词组
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "tất cả tin tức":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # Logic khớp ban đầu
                    if required_words:
                        all_required_present = all(
                            _word_matches(req_word, title_lower)
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            _word_matches(normal_word, title_lower)
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url
                title_vi = title_data.get("title_vi", "")
                ai_tag = title_data.get("ai_tag", "")
                ai_tag_id = title_data.get("ai_tag_id", 999)
                ai_score = title_data.get("ai_score", 0.0)
                sources = title_data.get("sources", [source_id])
                source_count = title_data.get("source_count", 1)

                # Đối với current Chế độ，lấy dữ liệu đầy đủ từ thông tin thống kê lịch sử
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                    title_vi = info.get("title_vi", "") or title_vi
                    sources = info.get("sources", sources)
                    source_count = info.get("source_count", source_count)
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                    title_vi = info.get("title_vi", "") or title_vi
                    sources = info.get("sources", sources)
                    source_count = info.get("source_count", source_count)

                if not ranks:
                    ranks = [99]

                time_display = format_time_display(first_time, last_time)

                source_name = id_to_name.get(source_id, source_id)

                # Xác định có phải mới không
                is_new = False
                if all_news_are_new:
                    # Chế độ tăng dầndưới所cóXử lýcủamới闻đềulàmới增，hoặc者Lần đầu trong ngàycủa所cómới闻đềulàmới增
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # Kiểm tra có trong danh sách mới không
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source

                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "title_vi": title_vi,
                        "ai_tag": ai_tag,
                        "ai_tag_id": ai_tag_id,
                        "ai_score": ai_score,
                        "source_name": source_name,
                        "sources": sources,
                        "source_count": source_count,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                    }
                )

                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True

                break

    # Cuối cùng in thống nhất thông tin tổng hợp
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "hiển thị tất cả"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "tất cả tin tức"
                else "từ tần suấtkhớp"
            )
            print(
                f"Chế độ tăng dần：trong ngày第mộtlầnthu thập，{total_input_news} tintin tứctrongcó {matched_new_count} tin{filter_status}"
            )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "hiển thị tất cả"
                    if len(word_groups) == 1 and word_groups[0]["group_key"] == "tất cả tin tức"
                    else "từ tần suấtkhớp"
                )
                print(
                    f"Chế độ tăng dần：phát hiện {total_new_count} tinmới闻，trong đó {matched_new_count} tin{filter_status}"
                )
            else:
                print("Chế độ tăng dần：không phát hiện tin tức mới")

    # Chuyển đổi sang định dạng danh sách để sắp xếp
    # Map group_key -> group để lấy display_name/max_count
    group_map = {g["group_key"]: g for g in word_groups}
    sorted_stats = []
    for word, data in word_stats.items():
        count = data["count"]
        if count > 0:
            # Sắp xếp tin tức trong mỗi nhóm từ
            all_titles = []
            for source_id, titles in data["titles"].items():
                all_titles.extend(titles)

            # Sắp xếp tin tức：tin mới → viral xuyên nguồn (source_count) → rank → thời gian
            all_titles.sort(
                key=lambda x: (
                    not x.get("is_new", False),
                    -x.get("source_count", 1),
                    min(x["ranks"]) if x["ranks"] else 100,
                    x["last_time"],
                )
            )

            group_cfg = group_map.get(word, {})
            max_count = group_cfg.get("max_count", 0)
            if max_count > 0:
                all_titles = all_titles[:max_count]

            sorted_stats.append(
                {
                    "word": group_cfg.get("display_name") or word,
                    "count": count,
                    "titles": all_titles,
                }
            )

    # Sắp xếp nhóm từ theo số lượng tin tức giảm dần
    sorted_stats.sort(key=lambda x: x["count"], reverse=True)

    return sorted_stats, total_titles


def regroup_stats_by_ai_tag(stats: List[Dict]) -> List[Dict]:
    """
    Gom lại stats theo ai_tag (khi AI filter đã tag tin).

    - Mỗi tin chỉ thuộc ĐÚNG 1 nhóm tag (tag AI gán) → khử trùng lặp hiển thị
      giữa các keyword groups.
    - Thứ tự nhóm theo tag_id (= thứ tự ưu tiên trong ai_interests.txt),
      nhóm không có tag đi cuối.
    - Tin trong nhóm: ai_score → source_count → is_new → rank → last_time.

    Nếu không có title nào mang ai_tag → trả nguyên stats (fallback keyword).
    """
    tagged: Dict[str, Dict] = {}
    untagged: List[Dict] = []

    for stat in stats:
        for title_data in stat.get("titles", []):
            tag = title_data.get("ai_tag", "")
            entry = tagged.setdefault(
                tag if tag else "__untagged__",
                {"tag_id": title_data.get("ai_tag_id", 999), "titles": {}, "seen": set()},
            )
            # Khử trùng lặp: title có thể xuất hiện ở nhiều keyword groups
            if title_data["title"] in entry["seen"]:
                continue
            entry["seen"].add(title_data["title"])
            entry["titles"].setdefault(title_data["source_name"], []).append(title_data)

    if not tagged or "__untagged__" in tagged and len(tagged) == 1:
        return stats

    regrouped = []
    for tag, data in tagged.items():
        all_titles = []
        for titles in data["titles"].values():
            all_titles.extend(titles)

        all_titles.sort(
            key=lambda x: (
                -x.get("ai_score", 0.0),
                -x.get("source_count", 1),
                not x.get("is_new", False),
                min(x["ranks"]) if x["ranks"] else 100,
                x["last_time"],
            )
        )

        word = tag if tag != "__untagged__" else "Khác"
        regrouped.append(
            {"word": word, "count": len(all_titles), "titles": all_titles,
             "_tag_id": data["tag_id"]}
        )

    # Nhóm có tag theo thứ tự ưu tiên (tag_id), "Khác" luôn cuối
    regrouped.sort(key=lambda x: x["_tag_id"])
    for g in regrouped:
        g.pop("_tag_id", None)
    return regrouped
