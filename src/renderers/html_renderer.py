from typing import Dict, List, Optional
from pathlib import Path
from src.utils import (
    get_beijing_time,
    format_time_filename,
    html_escape,
    get_output_path,
)
from src.utils.format_utils import format_rank_display
from src.utils.text_utils import clean_title
from src.processors.report_processor import prepare_report_data


REPORT_CSS = """
        :root {
            --bg: #f2f4f7;
            --surface: #ffffff;
            --hover: #f8fafc;
            --border: #e4e7ec;
            --border-soft: #eef1f4;
            --text: #101828;
            --text-2: #475467;
            --text-3: #98a2b3;
            --accent: #d9480f;
            --accent-deep: #b63a08;
            --accent-soft: #fef0e7;
            --blue: #175cd3;
            --blue-soft: #eff5ff;
            --green: #067647;
            --green-soft: #ecfdf3;
            --teal: #0e7490;
            --teal-soft: #ecfdff;
            --danger: #b42318;
            --danger-soft: #fef3f2;
            --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
            --sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            --display: "Space Grotesk", "IBM Plex Sans", sans-serif;
        }

        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }

        body {
            font-family: var(--sans);
            margin: 0;
            padding: 0 16px 72px;
            background: var(--bg);
            color: var(--text);
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }

        .container { max-width: 860px; margin: 0 auto; }

        /* ── topbar ─────────────────────────────── */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 12px 0;
            background: rgba(242, 244, 247, 0.88);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-soft);
        }

        .brand {
            font-family: var(--mono);
            font-size: 12.5px;
            font-weight: 600;
            letter-spacing: 0.18em;
            color: var(--text);
            white-space: nowrap;
            user-select: none;
        }

        .brand-mark { color: var(--accent); }

        .search {
            flex: 1;
            min-width: 0;
            max-width: 340px;
            margin-left: auto;
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 13px;
            font-family: var(--sans);
            outline: none;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .search::placeholder { color: var(--text-3); }
        .search:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-soft);
        }

        .save-buttons { display: flex; gap: 8px; flex-shrink: 0; }

        .save-btn {
            font-family: var(--sans);
            font-size: 12px;
            font-weight: 500;
            padding: 8px 14px;
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text-2);
            border-radius: 8px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s ease;
        }

        .save-btn:hover {
            border-color: var(--accent);
            color: var(--accent-deep);
        }

        .save-btn:active { transform: translateY(1px); }
        .save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        /* ── masthead ───────────────────────────── */
        .header { padding: 44px 4px 26px; }

        .header-eyebrow {
            font-family: var(--mono);
            font-size: 11px;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--accent-deep);
            margin-bottom: 14px;
        }

        .header-title {
            font-family: var(--display);
            font-size: clamp(30px, 5.4vw, 44px);
            font-weight: 600;
            letter-spacing: -0.02em;
            line-height: 1.08;
            color: var(--text);
            margin: 0 0 22px;
        }

        .header-info {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .info-item {
            display: flex;
            align-items: baseline;
            gap: 8px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 7px 16px;
        }

        .info-label {
            font-size: 11.5px;
            font-weight: 500;
            color: var(--text-3);
        }

        .info-value {
            font-family: var(--mono);
            font-size: 14px;
            font-weight: 600;
            color: var(--text);
            font-variant-numeric: tabular-nums;
        }

        /* ── toc ────────────────────────────────── */
        .toc {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 0 4px 22px;
        }

        .toc a {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-2);
            text-decoration: none;
            padding: 6px 12px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 999px;
            transition: all 0.15s ease;
        }

        .toc a:hover {
            border-color: var(--accent);
            color: var(--accent-deep);
        }

        .toc a b {
            font-family: var(--mono);
            color: var(--text-3);
            font-weight: 500;
            font-size: 11px;
            margin-left: 6px;
            font-variant-numeric: tabular-nums;
        }

        .toc a:hover b { color: var(--accent); }

        /* ── cards ──────────────────────────────── */
        .content > * { scroll-margin-top: 64px; }

        .word-group,
        .top-picks,
        .new-section {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px 22px;
            margin-bottom: 16px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        }

        .top-picks {
            background: #fffaf3;
            border-color: #f0dfc2;
        }

        .word-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border-soft);
        }

        .word-info {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
        }

        .word-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 26px;
            height: 26px;
            padding: 0 6px;
            background: var(--accent);
            color: #fff;
            font-family: var(--mono);
            font-size: 12px;
            font-weight: 600;
            border-radius: 7px;
            flex-shrink: 0;
        }

        .word-name {
            font-family: var(--display);
            font-size: 18px;
            font-weight: 600;
            letter-spacing: -0.01em;
            color: var(--text);
        }

        .word-count {
            font-family: var(--mono);
            color: var(--text-3);
            font-size: 11.5px;
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
        }

        .word-count.hot { color: var(--accent-deep); font-weight: 600; }
        .word-count.warm { color: var(--accent); }

        .word-index {
            font-family: var(--mono);
            color: var(--text-3);
            font-size: 11px;
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
        }

        /* ── news rows: title trước, meta sau ────── */
        .news-item {
            padding: 12px 10px;
            border-bottom: 1px solid var(--border-soft);
            position: relative;
            border-radius: 8px;
            transition: background 0.15s ease;
        }

        .news-item:last-child { border-bottom: none; }
        .news-item:hover { background: var(--hover); }

        .news-title {
            font-size: 15px;
            font-weight: 500;
            line-height: 1.5;
            color: var(--text);
            margin: 0 0 5px;
            padding-right: 52px;
        }

        .news-item.new .news-title { padding-right: 64px; }

        .news-title-orig {
            font-size: 12.5px;
            line-height: 1.45;
            color: var(--text-3);
            margin-top: 3px;
        }

        .news-header {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .source-name {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-2);
        }

        .rank-num {
            font-family: var(--mono);
            font-size: 10.5px;
            font-weight: 500;
            padding: 1.5px 7px;
            border-radius: 5px;
            color: var(--text-2);
            background: var(--bg);
            font-variant-numeric: tabular-nums;
        }

        .rank-num.top {
            background: var(--accent);
            color: #fff;
            font-weight: 600;
        }

        .rank-num.high {
            background: var(--accent-soft);
            color: var(--accent-deep);
        }

        .time-info {
            font-family: var(--mono);
            color: var(--text-3);
            font-size: 11px;
            font-variant-numeric: tabular-nums;
        }

        .count-info {
            font-family: var(--mono);
            color: var(--text-3);
            font-size: 11px;
        }

        .source-count {
            font-family: var(--mono);
            font-size: 10.5px;
            font-weight: 500;
            padding: 1.5px 7px;
            border-radius: 5px;
            color: var(--blue);
            background: var(--blue-soft);
        }

        .ai-score {
            font-family: var(--mono);
            font-size: 10.5px;
            font-weight: 500;
            padding: 1.5px 7px;
            border-radius: 5px;
            color: var(--teal);
            background: var(--teal-soft);
        }

        .news-item.new::after {
            content: "MỚI";
            position: absolute;
            top: 14px;
            right: 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.06em;
            color: var(--green);
            background: var(--green-soft);
            padding: 2.5px 8px;
            border-radius: 5px;
        }

        .news-link {
            color: var(--text);
            text-decoration: none;
            transition: color 0.15s ease;
        }

        .news-link:hover {
            color: var(--accent-deep);
            text-decoration: underline;
            text-underline-offset: 3px;
        }

        .news-link:visited { color: var(--text-3); }

        /* ── top picks ──────────────────────────── */
        .top-picks-title {
            font-family: var(--mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--accent-deep);
            margin-bottom: 14px;
        }

        .top-pick-item {
            display: flex;
            gap: 14px;
            padding: 10px 10px;
            border-bottom: 1px solid #f3e8d4;
            border-radius: 8px;
            transition: background 0.15s ease;
        }

        .top-pick-item:last-child { border-bottom: none; }
        .top-pick-item:hover { background: rgba(255, 255, 255, 0.7); }

        .top-pick-num {
            font-family: var(--mono);
            color: var(--text-3);
            font-weight: 500;
            font-size: 13px;
            min-width: 22px;
            padding-top: 1px;
            font-variant-numeric: tabular-nums;
        }

        .top-pick-item:nth-child(-n+4) .top-pick-num {
            color: var(--accent-deep);
            font-weight: 700;
        }

        .top-pick-body { flex: 1; min-width: 0; }

        .top-pick-title {
            font-size: 15px;
            font-weight: 500;
            line-height: 1.5;
            color: var(--text);
            margin-bottom: 4px;
        }

        .top-pick-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .top-pick-source {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-2);
        }

        .top-pick-badges {
            display: inline-flex;
            gap: 6px;
        }

        .tp-chip {
            font-family: var(--mono);
            font-size: 10.5px;
            font-weight: 500;
            padding: 1.5px 7px;
            border-radius: 5px;
            font-variant-numeric: tabular-nums;
        }

        .tp-chip-src { color: var(--blue); background: var(--blue-soft); }
        .tp-chip-ai  { color: var(--teal); background: var(--teal-soft); }
        .tp-chip-rank{ color: var(--accent-deep); background: var(--accent-soft); }

        /* ── new section ────────────────────────── */
        .new-section-title {
            font-family: var(--mono);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--text-2);
            margin: 0 0 14px 0;
        }

        .new-source-group { margin-bottom: 18px; }
        .new-source-group:last-child { margin-bottom: 0; }

        .new-source-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-3);
            margin: 0 0 6px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-soft);
        }

        .new-item {
            display: flex;
            align-items: baseline;
            gap: 10px;
            padding: 7px 10px;
            border-bottom: 1px solid var(--border-soft);
            border-radius: 6px;
            transition: background 0.15s ease;
        }

        .new-item:last-child { border-bottom: none; }
        .new-item:hover { background: var(--hover); }

        .new-item-number {
            font-family: var(--mono);
            color: var(--text-3);
            font-size: 11px;
            min-width: 18px;
            text-align: right;
            flex-shrink: 0;
            font-variant-numeric: tabular-nums;
        }

        .new-item-rank {
            font-family: var(--mono);
            font-size: 10.5px;
            font-weight: 500;
            padding: 1px 6px;
            border-radius: 5px;
            color: var(--text-2);
            background: var(--bg);
            flex-shrink: 0;
            font-variant-numeric: tabular-nums;
        }

        .new-item-rank.top { background: var(--accent); color: #fff; font-weight: 600; }
        .new-item-rank.high { background: var(--accent-soft); color: var(--accent-deep); }

        .new-item-content { flex: 1; min-width: 0; }

        .new-item-title {
            font-size: 14px;
            line-height: 1.5;
            color: var(--text);
            margin: 0;
        }

        /* ── errors / footer ────────────────────── */
        .error-section {
            background: var(--danger-soft);
            border: 1px solid rgba(180, 35, 24, 0.22);
            border-radius: 12px;
            padding: 14px 18px;
            margin-bottom: 16px;
        }

        .error-title {
            font-size: 12px;
            font-weight: 700;
            color: var(--danger);
            margin: 0 0 6px 0;
        }

        .error-list { list-style: none; padding: 0; margin: 0; }

        .error-item {
            color: var(--text-2);
            font-size: 12px;
            padding: 2px 0;
            font-family: var(--mono);
        }

        .footer {
            margin-top: 32px;
            padding: 20px 0 8px;
            text-align: center;
        }

        .footer-content {
            font-size: 12px;
            color: var(--text-3);
            line-height: 1.7;
        }

        .footer-link {
            color: var(--text-2);
            text-decoration: none;
            border-bottom: 1px solid var(--border);
            transition: color 0.2s ease, border-color 0.2s ease;
        }

        .footer-link:hover {
            color: var(--accent-deep);
            border-color: var(--accent);
        }

        .project-name { font-weight: 600; color: var(--text-2); }

        .no-results {
            display: none;
            padding: 40px 0;
            text-align: center;
            font-size: 13px;
            color: var(--text-3);
        }

        .no-results.visible { display: block; }

        @media (max-width: 560px) {
            body { padding: 0 12px 56px; }
            .topbar { flex-wrap: wrap; gap: 10px; }
            .search { order: 3; flex-basis: 100%; max-width: none; margin-left: 0; }
            .header { padding: 30px 2px 20px; }
            .word-group, .top-picks, .new-section { padding: 16px 14px; }
            .toc { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 14px; }
            .toc a { flex-shrink: 0; }
            .news-title { padding-right: 46px; }
            .save-buttons { margin-left: auto; }
        }
"""


REPORT_JS = """
            // ── live search (không dấu-insensitive, phím "/" để focus) ──
            (function () {
                const input = document.getElementById('tn-search');
                if (!input) return;

                const norm = (s) => (s || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/đ/g, 'd');

                const items = document.querySelectorAll('.news-item, .new-item, .top-pick-item');
                const groups = document.querySelectorAll('.word-group, .new-source-group');
                const picksBox = document.querySelector('.top-picks');
                const newSection = document.querySelector('.new-section');
                const noResults = document.getElementById('tn-no-results');

                input.addEventListener('input', () => {
                    const q = norm(input.value.trim());
                    let visibleCount = 0;

                    items.forEach((el) => {
                        const show = !q || norm(el.textContent).includes(q);
                        el.style.display = show ? '' : 'none';
                        if (show) visibleCount++;
                    });

                    groups.forEach((g) => {
                        const anyVisible = Array.from(
                            g.querySelectorAll('.news-item, .new-item')
                        ).some((el) => el.style.display !== 'none');
                        g.style.display = anyVisible ? '' : 'none';
                    });

                    if (picksBox) {
                        const anyPick = Array.from(
                            picksBox.querySelectorAll('.top-pick-item')
                        ).some((el) => el.style.display !== 'none');
                        picksBox.style.display = !q || anyPick ? '' : 'none';
                    }
                    if (newSection) {
                        const anyNew = newSection.querySelector(
                            '.new-source-group:not([style*="none"])'
                        );
                        newSection.style.display = !q || anyNew ? '' : 'none';
                    }
                    if (noResults) {
                        noResults.classList.toggle('visible', !!q && visibleCount === 0);
                    }
                });

                document.addEventListener('keydown', (e) => {
                    if (e.key === '/' && document.activeElement !== input) {
                        e.preventDefault();
                        input.focus();
                    }
                    if (e.key === 'Escape' && document.activeElement === input) {
                        input.value = '';
                        input.dispatchEvent(new Event('input'));
                        input.blur();
                    }
                });
            })();

            // ── lưu ảnh (html2canvas) ──
            async function saveAsImage() {
                const button = event.target;
                const originalText = button.textContent;

                try {
                    button.textContent = 'Đang tạo...';
                    button.disabled = true;
                    window.scrollTo(0, 0);

                    await new Promise(resolve => setTimeout(resolve, 200));

                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

                    await new Promise(resolve => setTimeout(resolve, 100));

                    const container = document.querySelector('.container');

                    const canvas = await html2canvas(container, {
                        backgroundColor: '#f2f4f7',
                        scale: 1.5,
                        useCORS: true,
                        allowTaint: false,
                        imageTimeout: 10000,
                        removeContainer: false,
                        foreignObjectRendering: false,
                        logging: false,
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        x: 0,
                        y: 0,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: window.innerWidth,
                        windowHeight: window.innerHeight
                    });

                    buttons.style.visibility = 'visible';

                    const link = document.createElement('a');
                    const now = new Date();
                    const filename = `TrendNews_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}.png`;

                    link.download = filename;
                    link.href = canvas.toDataURL('image/png', 1.0);

                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    button.textContent = 'Đã lưu';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    button.textContent = 'Lưu thất bại';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                }
            }

            async function saveAsMultipleImages() {
                const button = event.target;
                const originalText = button.textContent;
                const container = document.querySelector('.container');
                const scale = 1.5;
                const maxHeight = 5000 / scale;

                try {
                    button.textContent = 'Đang phân tích...';
                    button.disabled = true;

                    const newsItems = Array.from(container.querySelectorAll('.news-item'));
                    const wordGroups = Array.from(container.querySelectorAll('.word-group'));
                    const newSection = container.querySelector('.new-section');
                    const errorSection = container.querySelector('.error-section');
                    const header = container.querySelector('.header');
                    const footer = container.querySelector('.footer');

                    const containerRect = container.getBoundingClientRect();
                    const elements = [];

                    elements.push({
                        type: 'header',
                        element: header,
                        top: 0,
                        bottom: header.offsetHeight,
                        height: header.offsetHeight
                    });

                    if (errorSection) {
                        const rect = errorSection.getBoundingClientRect();
                        elements.push({
                            type: 'error',
                            element: errorSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    wordGroups.forEach(group => {
                        const groupRect = group.getBoundingClientRect();
                        const groupNewsItems = group.querySelectorAll('.news-item');

                        const wordHeader = group.querySelector('.word-header');
                        if (wordHeader) {
                            const headerRect = wordHeader.getBoundingClientRect();
                            elements.push({
                                type: 'word-header',
                                element: wordHeader,
                                parent: group,
                                top: groupRect.top - containerRect.top,
                                bottom: headerRect.bottom - containerRect.top,
                                height: headerRect.height
                            });
                        }

                        groupNewsItems.forEach(item => {
                            const rect = item.getBoundingClientRect();
                            elements.push({
                                type: 'news-item',
                                element: item,
                                parent: group,
                                top: rect.top - containerRect.top,
                                bottom: rect.bottom - containerRect.top,
                                height: rect.height
                            });
                        });
                    });

                    if (newSection) {
                        const rect = newSection.getBoundingClientRect();
                        elements.push({
                            type: 'new-section',
                            element: newSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    const footerRect = footer.getBoundingClientRect();
                    elements.push({
                        type: 'footer',
                        element: footer,
                        top: footerRect.top - containerRect.top,
                        bottom: footerRect.bottom - containerRect.top,
                        height: footer.offsetHeight
                    });

                    const segments = [];
                    let currentSegment = { start: 0, end: 0, height: 0, includeHeader: true };
                    let headerHeight = header.offsetHeight;
                    currentSegment.height = headerHeight;

                    for (let i = 1; i < elements.length; i++) {
                        const element = elements[i];
                        const potentialHeight = element.bottom - currentSegment.start;

                        if (potentialHeight > maxHeight && currentSegment.height > headerHeight) {
                            currentSegment.end = elements[i - 1].bottom;
                            segments.push(currentSegment);

                            currentSegment = {
                                start: currentSegment.end,
                                end: 0,
                                height: element.bottom - currentSegment.end,
                                includeHeader: false
                            };
                        } else {
                            currentSegment.height = potentialHeight;
                            currentSegment.end = element.bottom;
                        }
                    }

                    if (currentSegment.height > 0) {
                        currentSegment.end = container.offsetHeight;
                        segments.push(currentSegment);
                    }

                    button.textContent = `Đang tạo (0/${segments.length})...`;

                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

                    const images = [];
                    for (let i = 0; i < segments.length; i++) {
                        const segment = segments[i];
                        button.textContent = `Đang tạo (${i + 1}/${segments.length})...`;

                        const tempContainer = document.createElement('div');
                        tempContainer.style.cssText = `
                            position: absolute;
                            left: -9999px;
                            top: 0;
                            width: ${container.offsetWidth}px;
                            background: #f2f4f7;
                        `;
                        tempContainer.className = 'container';

                        const clonedContainer = container.cloneNode(true);

                        const clonedButtons = clonedContainer.querySelector('.save-buttons');
                        if (clonedButtons) {
                            clonedButtons.style.display = 'none';
                        }

                        tempContainer.appendChild(clonedContainer);
                        document.body.appendChild(tempContainer);

                        await new Promise(resolve => setTimeout(resolve, 100));

                        const canvas = await html2canvas(clonedContainer, {
                            backgroundColor: '#f2f4f7',
                            scale: scale,
                            useCORS: true,
                            allowTaint: false,
                            imageTimeout: 10000,
                            logging: false,
                            width: container.offsetWidth,
                            height: segment.end - segment.start,
                            x: 0,
                            y: segment.start,
                            windowWidth: window.innerWidth,
                            windowHeight: window.innerHeight
                        });

                        images.push(canvas.toDataURL('image/png', 1.0));

                        document.body.removeChild(tempContainer);
                    }

                    buttons.style.visibility = 'visible';

                    const now = new Date();
                    const baseFilename = `TrendNews_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;

                    for (let i = 0; i < images.length; i++) {
                        const link = document.createElement('a');
                        link.download = `${baseFilename}_part${i + 1}.png`;
                        link.href = images[i];
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        await new Promise(resolve => setTimeout(resolve, 100));
                    }

                    button.textContent = `Đã lưu ${segments.length} ảnh`;
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    console.error('Lưu phân đoạn thất bại:', error);
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    button.textContent = 'Lưu thất bại';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                }
            }

            document.addEventListener('DOMContentLoaded', function() {
                window.scrollTo(0, 0);
            });
"""


class HTMLRenderer:
    @staticmethod
    def format_title(title_data: Dict, show_source: bool = True) -> str:
        """
        Format title for HTML platform.
        """
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]
        cleaned_title = clean_title(title_data["title"])

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}lần)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    @staticmethod
    def generate_report(
        stats: List[Dict],
        total_titles: int,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
        is_daily_summary: bool = False,
        update_info: Optional[Dict] = None,
        investment_html: str = "",
    ) -> str:
        """tạoHTMLbáo cáo"""
        if is_daily_summary:
            if mode == "current":
                filename = "bảng xếp hạng hiện tạitổng hợp.html"
            elif mode == "incremental":
                filename = "当ngàytăng dần.html"
            else:
                filename = "当ngàytổng hợp.html"
        else:
            filename = f"{format_time_filename()}.html"

        file_path = get_output_path("html", filename)

        report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

        html_content = HTMLRenderer.render_content(
            report_data, total_titles, is_daily_summary, mode, update_info,
            investment_html=investment_html,
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        if is_daily_summary:
            root_file_path = Path("index.html")
            with open(root_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return file_path

    @staticmethod
    def _collect_top_picks(stats: List[Dict], limit: int = 15) -> List[Dict]:
        """
        Chọn tin nổi bật nhất để đọc nhanh:
        source_count>=2 (viral xuyên nguồn) HOẶC ai_score>=0.85 HOẶC rank<=3.
        Sort: source_count → ai_score → rank. Khử trùng theo title.
        """
        seen = set()
        candidates = []
        for stat in stats or []:
            for t in stat.get("titles", []):
                if t["title"] in seen:
                    continue
                seen.add(t["title"])
                ranks = t.get("ranks", [])
                is_pick = (
                    t.get("source_count", 1) >= 2
                    or t.get("ai_score", 0.0) >= 0.85
                    or (ranks and min(ranks) <= 3)
                )
                if is_pick:
                    candidates.append(t)

        candidates.sort(
            key=lambda x: (
                -x.get("source_count", 1),
                -x.get("ai_score", 0.0),
                min(x["ranks"]) if x.get("ranks") else 100,
            )
        )
        return candidates[:limit]

    @staticmethod
    def _meta_chips(title_data: Dict) -> str:
        """Meta chips hiển thị dưới title: source · rank · time · count · nguồn · AI."""
        chips = f'<span class="source-name">{html_escape(title_data["source_name"])}</span>\n'

        ranks = title_data.get("ranks", [])
        if ranks:
            min_rank, max_rank = min(ranks), max(ranks)
            rank_threshold = title_data.get("rank_threshold", 10)
            if min_rank <= 3:
                rank_class = "top"
            elif min_rank <= rank_threshold:
                rank_class = "high"
            else:
                rank_class = ""
            rank_text = str(min_rank) if min_rank == max_rank else f"{min_rank}-{max_rank}"
            chips += f'<span class="rank-num {rank_class}">#{rank_text}</span>\n'

        time_display = title_data.get("time_display", "")
        if time_display:
            import re as _re
            simplified = (
                time_display.replace(" ~ ", "~").replace("[", "").replace("]", "")
            )
            # "14giờ44phút" (filename format) → "14:44"
            simplified = _re.sub(r"(\d{1,2})giờ(\d{2})phút", r"\1:\2", simplified)
            chips += f'<span class="time-info">{html_escape(simplified)}</span>\n'

        count_info = title_data.get("count", 1)
        if count_info > 1:
            chips += f'<span class="count-info">&times;{count_info}</span>\n'

        source_count = title_data.get("source_count", 1)
        if source_count > 1:
            chips += f'<span class="source-count">{source_count} nguồn</span>\n'

        ai_score = title_data.get("ai_score")
        if ai_score:
            chips += f'<span class="ai-score">AI {ai_score:.2f}</span>\n'

        return chips

    @staticmethod
    def render_content(
        report_data: Dict,
        total_titles: int,
        is_daily_summary: bool = False,
        mode: str = "daily",
        update_info: Optional[Dict] = None,
        investment_html: str = "",
    ) -> str:
        """renderHTMLnội dung"""
        now = get_beijing_time()

        # Nhãn chế độ báo cáo (tiếng Việt sạch)
        if is_daily_summary:
            if mode == "current":
                mode_label = "Bảng xếp hạng hiện tại"
            elif mode == "incremental":
                mode_label = "Tăng dần trong ngày"
            else:
                mode_label = "Tổng hợp trong ngày"
        else:
            mode_label = "Phân tích thời gian thực"

        hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendNews — Bản tin nóng</title>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='6' y='6' width='20' height='20' rx='5' fill='%23d9480f'/%3E%3C/svg%3E">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    <style>{REPORT_CSS}</style>
</head>
<body>
    <div class="container">
        <div class="topbar">
            <div class="brand"><span class="brand-mark">&#9632;</span> TRENDNEWS</div>
            <input id="tn-search" class="search" type="text" placeholder="Lọc tin&hellip;  ( / )" autocomplete="off" spellcheck="false">
            <div class="save-buttons">
                <button class="save-btn" onclick="saveAsImage()">Lưu ảnh</button>
                <button class="save-btn" onclick="saveAsMultipleImages()">Lưu từng đoạn</button>
            </div>
        </div>

        <div class="header">
            <div class="header-eyebrow">{mode_label} &middot; {now.strftime("%d/%m/%Y %H:%M")}</div>
            <h1 class="header-title">Bản tin nóng</h1>
            <div class="header-info">
                <div class="info-item">
                    <span class="info-label">Tổng tin</span>
                    <span class="info-value">{total_titles}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Nổi bật</span>
                    <span class="info-value">{hot_news_count}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Chủ đề</span>
                    <span class="info-value">{len(report_data["stats"])}</span>
                </div>
            </div>
        </div>
"""

        # TOC — nhảy nhanh tới từng section
        if report_data["stats"]:
            html += '        <nav class="toc">\n'
            for i, stat in enumerate(report_data["stats"], 1):
                html += (
                    f'            <a href="#sec-{i}">{html_escape(stat["word"])}'
                    f'<b>{stat["count"]}</b></a>\n'
                )
            html += '        </nav>\n'

        html += '        <div class="content">\n'

        # Section "Tin nổi bật" — top picks đọc nhanh trước khi vào chi tiết
        top_picks = HTMLRenderer._collect_top_picks(report_data["stats"])
        if top_picks:
            html += f"""            <div class="top-picks">
                <div class="top-picks-title">Tin nổi bật &middot; {len(top_picks)}</div>
"""
            for idx, tp in enumerate(top_picks, 1):
                display = tp.get("title_vi") or tp["title"]
                link = tp.get("mobile_url") or tp.get("mobileUrl") or tp.get("url", "")
                chips = ""
                if tp.get("source_count", 1) > 1:
                    chips += f'<span class="tp-chip tp-chip-src">{tp["source_count"]} nguồn</span>'
                if tp.get("ai_score"):
                    chips += f'<span class="tp-chip tp-chip-ai">AI {tp["ai_score"]:.2f}</span>'
                ranks = tp.get("ranks", [])
                if ranks and min(ranks) <= 3:
                    chips += f'<span class="tp-chip tp-chip-rank">top {min(ranks)}</span>'
                badge_html = (
                    f'<span class="top-pick-badges">{chips}</span>' if chips else ""
                )
                title_html = (
                    f'<a href="{html_escape(link)}" target="_blank" class="news-link">{html_escape(display)}</a>'
                    if link else html_escape(display)
                )
                html += f"""                <div class="top-pick-item">
                    <span class="top-pick-num">{idx:02d}</span>
                    <div class="top-pick-body">
                        <div class="top-pick-title">{title_html}</div>
                        <div class="top-pick-meta">
                            <span class="top-pick-source">{html_escape(tp["source_name"])}</span>
                            {badge_html}
                        </div>
                    </div>
                </div>
"""
            html += "            </div>\n"

        # Inject investment analysis section at the top of content
        if investment_html:
            html += investment_html

        # Xử lý thông tin lỗi ID thất bại
        if report_data["failed_ids"]:
            html += """            <div class="error-section">
                <div class="error-title">Nguồn lỗi</div>
                <ul class="error-list">
"""
            for id_value in report_data["failed_ids"]:
                html += f'                    <li class="error-item">{html_escape(id_value)}</li>\n'
            html += """                </ul>
            </div>
"""

        # Xử lý dữ liệu thống kê chính
        if report_data["stats"]:
            total_count = len(report_data["stats"])

            for i, stat in enumerate(report_data["stats"], 1):
                count = stat["count"]

                # Xác định cấp độ nóng
                if count >= 10:
                    count_class = "hot"
                elif count >= 5:
                    count_class = "warm"
                else:
                    count_class = ""

                escaped_word = html_escape(stat["word"])

                html += f"""            <div class="word-group" id="sec-{i}">
                <div class="word-header">
                    <div class="word-info">
                        <span class="word-num">{i:02d}</span>
                        <div class="word-name">{escaped_word}</div>
                        <div class="word-count {count_class}">{count} tin</div>
                    </div>
                    <div class="word-index">{i:02d}/{total_count:02d}</div>
                </div>
"""

                # Title trước, meta chips dưới — đọc dễ hơn
                for title_data in stat["titles"]:
                    is_new = title_data.get("is_new", False)
                    new_class = "new" if is_new else ""

                    display_title = title_data.get("title_vi") or title_data["title"]
                    escaped_title = html_escape(display_title)
                    link_url = (
                        title_data.get("mobile_url")
                        or title_data.get("mobileUrl")
                        or title_data.get("url", "")
                    )

                    html += f"""                <div class="news-item {new_class}">
                    <div class="news-title">
"""
                    if link_url:
                        escaped_url = html_escape(link_url)
                        html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>\n'
                    else:
                        html += escaped_title + "\n"

                    if title_data.get("title_vi") and title_data["title_vi"] != title_data["title"]:
                        html += f'<div class="news-title-orig">{html_escape(title_data["title"])}</div>\n'

                    html += """                    </div>
                    <div class="news-header">
"""
                    html += HTMLRenderer._meta_chips(title_data)

                    html += """                    </div>
                </div>
"""

                html += "            </div>\n"

        # Xử lý khu vực tin tức mới
        if report_data["new_titles"]:
            html += f"""            <div class="new-section">
                <div class="new-section-title">Tin mới lần này &middot; {report_data['total_new_count']} tin</div>
"""

            for source_data in report_data["new_titles"]:
                escaped_source = html_escape(source_data["source_name"])
                titles_count = len(source_data["titles"])

                html += f"""                <div class="new-source-group">
                    <div class="new-source-title">{escaped_source} &middot; {titles_count} tin</div>
"""

                for idx, title_data in enumerate(source_data["titles"], 1):
                    ranks = title_data.get("ranks", [])

                    rank_class = ""
                    if ranks:
                        min_rank = min(ranks)
                        if min_rank <= 3:
                            rank_class = "top"
                        elif min_rank <= title_data.get("rank_threshold", 10):
                            rank_class = "high"

                        if len(ranks) == 1:
                            rank_text = str(ranks[0])
                        else:
                            rank_text = f"{min(ranks)}-{max(ranks)}"
                    else:
                        rank_text = "?"

                    html += f"""                    <div class="new-item">
                        <div class="new-item-number">{idx:02d}</div>
                        <div class="new-item-rank {rank_class}">#{rank_text}</div>
                        <div class="new-item-content">
                            <div class="new-item-title">
"""

                    display_title = title_data.get("title_vi") or title_data["title"]
                    escaped_title = html_escape(display_title)
                    link_url = (
                        title_data.get("mobile_url")
                        or title_data.get("mobileUrl")
                        or title_data.get("url", "")
                    )

                    if link_url:
                        escaped_url = html_escape(link_url)
                        html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>\n'
                    else:
                        html += escaped_title + "\n"

                    if title_data.get("title_vi") and title_data["title_vi"] != title_data["title"]:
                        html += f'<div class="news-title-orig">{html_escape(title_data["title"])}</div>\n'

                    html += """                            </div>
                        </div>
                    </div>
"""

                html += "                </div>\n"

            html += "            </div>\n"

        html += """            <div id="tn-no-results" class="no-results">Không có tin nào khớp bộ lọc</div>
        </div>

        <div class="footer">
            <div class="footer-content">
                TrendNews &middot; fork của <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">TrendRadar</a>
"""

        if update_info:
            html += f"""                <br>
                <span style="color: var(--accent-deep);">
                    Phát hiện phiên bản mới {update_info['remote_version']}，phiên bản hiện tại {update_info['current_version']}
                </span>
"""

        html += f"""            </div>
        </div>
    </div>

    <script>{REPORT_JS}</script>
</body>
</html>
"""

        return html
