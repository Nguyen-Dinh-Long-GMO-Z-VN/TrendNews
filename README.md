# TrendRadar 📡

TrendRadar thu thập tin nóng và RSS, lọc theo chủ đề quan tâm, rồi tạo báo cáo HTML để đọc hoặc gửi qua Telegram và email. Cấu hình hiện tại khai báo **179 nguồn**: 20 bảng tin qua NewsNow và 159 RSS từ Việt Nam cùng nhiều khu vực khác.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)

## Có gì trong dự án?

- Thu thập song song từ [NewsNow](https://newsnow.busiyi.world/) và các RSS được khai báo trong [`config/config.yaml`](config/config.yaml). Nguồn RSS gồm báo Việt Nam, tin thế giới, AI, quốc phòng, tài chính và khoa học.
- Theo dõi từ khóa trong [`config/frequency_words.txt`](config/frequency_words.txt), đánh dấu tin mới, ưu tiên tin xuất hiện trên nhiều nguồn và có thứ hạng cao; gộp tiêu đề trùng giữa các nguồn.
- Tạo báo cáo HTML theo ba chế độ `daily`, `incremental` và `current`; lưu dữ liệu thô cùng báo cáo trong `output/`.
- Tùy chọn lọc tin bằng mô tả sở thích tự nhiên, dịch tiêu đề sang tiếng Việt và phân tích tin theo nhóm tài sản bằng AI. Các tính năng này cần cấu hình nhà cung cấp AI; riêng dịch và lọc AI mặc định tắt.
- Cung cấp MCP server để truy vấn tin mới, tìm kiếm tin cũ và phân tích xu hướng từ dữ liệu đã lưu.

## Chạy nhanh

Yêu cầu Python **3.10+** và kết nối mạng để lấy tin. Chạy từ thư mục gốc dự án:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

File `config/config.yaml` và `config/frequency_words.txt` đã có sẵn. Chương trình ghi báo cáo HTML và bản tin thô vào `output/<ngày>/html/` và `output/<ngày>/txt/`; khi chạy trên máy cá nhân, nó sẽ mở báo cáo trong trình duyệt.

### Cấu hình cơ bản

Chỉnh trực tiếp [`config/config.yaml`](config/config.yaml). Cấu trúc các mục chính:

```yaml
report:
  mode: daily                 # daily | incremental | current

notification:
  enable_notification: false # bật true sau khi cấu hình kênh gửi

translation:
  enabled: false

dedup:
  enabled: true

ai_filter:
  enabled: false

platforms:
  - id: weibo
    name: 微博
  - id: vnexpress
    name: VnExpress
    rss_url: https://vnexpress.net/rss/tin-moi-nhat.rss
```

Mỗi dòng trong [`config/frequency_words.txt`](config/frequency_words.txt) là một từ khóa cần theo dõi. Có thể chọn file cấu hình khác bằng biến môi trường `CONFIG_PATH`.

| Chế độ | Nội dung báo cáo |
| --- | --- |
| `daily` | Tổng hợp các tin khớp từ đầu ngày |
| `incremental` | Tập trung vào tin mới xuất hiện |
| `current` | Tin khớp từ bảng xếp hạng hiện tại |

### AI và thông báo

Sao chép [`.env.example`](.env.example) thành `.env` rồi điền khóa API nếu dùng AI. `src/analysis/ai_client.py` hỗ trợ Claude, OpenAI, DeepSeek, Gemini và Ollama; từng tính năng có thể chọn nhà cung cấp riêng qua các biến `AI_*`, `TRANSLATE_*` và `AIFILTER_*`.

- Dịch tiêu đề: đặt `translation.enabled: true` hoặc `TRANSLATION_ENABLED=true`.
- Lọc theo sở thích: sửa [`config/ai_interests.txt`](config/ai_interests.txt), rồi đặt `ai_filter.enabled: true` hoặc `AI_FILTER_ENABLED=true`.
- Phân tích nhóm tài sản: `investment_analysis.enabled` đang bật trong cấu hình; cần một nhà cung cấp AI được cấu hình để có kết quả phân tích.
- Gửi thông báo: đặt `notification.enable_notification: true`, rồi khai báo `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID`, hoặc `EMAIL_FROM`, `EMAIL_PASSWORD` và `EMAIL_TO` trong môi trường. Không commit khóa API hay thông tin đăng nhập vào repo.

## MCP server

Sau khi cài dependencies, có thể chạy server để trợ lý AI truy vấn dữ liệu đã thu thập:

```bash
python -m mcp_server.server                   # stdio
python -m mcp_server.server --transport http --host 127.0.0.1 --port 3333
```

Chế độ HTTP dùng endpoint `http://127.0.0.1:3333/mcp`. Các công cụ gồm lấy tin mới, tin theo ngày, chủ đề nổi bật, tìm kiếm lịch sử, phân tích và kích hoạt lượt thu thập mới. MCP đọc dữ liệu trong `output/`, nên hãy chạy `python main.py` ít nhất một lần trước khi truy vấn.

## Cấu trúc chính

| Đường dẫn | Vai trò |
| --- | --- |
| [`main.py`](main.py) | Điều phối thu thập, xử lý, tạo báo cáo và gửi thông báo |
| [`src/core/`](src/core/) | Lấy dữ liệu từ NewsNow và RSS, quản lý lịch sử gửi |
| [`src/processors/`](src/processors/) | Lọc từ khóa, thống kê, nhận diện tin mới và gộp tin trùng |
| [`src/analysis/`](src/analysis/) | AI client, dịch, lọc theo sở thích và phân tích nhóm tài sản |
| [`src/renderers/`](src/renderers/) | Tạo báo cáo HTML và nội dung Telegram |
| [`src/notifiers/`](src/notifiers/) | Gửi Telegram và email |
| [`mcp_server/`](mcp_server/) | MCP tools truy vấn dữ liệu đã lưu |

Workflow [`.github/workflows/crawler.yml`](.github/workflows/crawler.yml) chạy crawler mỗi giờ trên GitHub Actions. Thư mục `docker/` chứa cấu hình container, nhưng `docker/Dockerfile` hiện chưa chép thư mục `src/` vào image; vì vậy hướng dẫn chạy nhanh ở trên dùng Python trực tiếp.

## Giấy phép

Repo đi kèm văn bản [GNU GPL phiên bản 3](LICENSE).
