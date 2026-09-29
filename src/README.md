# Các module ứng dụng

`main.py` ở thư mục gốc là entry point và composition root của crawler. Thư mục `src/` chứa các module được entry point điều phối; MCP server nằm riêng ở `mcp_server/`. Xem sơ đồ đầy đủ tại [`../docs/architecture.md`](../docs/architecture.md).

| Module | Trách nhiệm thực tế |
| --- | --- |
| `config/` | Đọc `config/config.yaml`, biến môi trường và danh sách từ khóa; xuất cấu hình dùng chung `CONFIG`. |
| `core/` | Gọi NewsNow API, lấy RSS và quản lý lịch sử gửi; `main.py` điều phối hai bộ thu thập. `core/analyzer.py` là placeholder, không phải luồng chạy đầy đủ. |
| `processors/` | Lưu và đọc snapshot tin, phát hiện tin mới, khớp nhóm từ khóa, tính thống kê và gộp tin trùng. |
| `analysis/` | Tích hợp nhà cung cấp AI, lọc theo sở thích, dịch tiêu đề và phân tích nhóm tài sản. Từng tính năng phụ thuộc cấu hình và khả năng truy cập nhà cung cấp. |
| `renderers/` | `html_renderer.py` tạo báo cáo HTML một trang; `telegram_renderer.py` định dạng nội dung Telegram. |
| `notifiers/` | `manager.py` điều phối gửi Telegram và email theo cấu hình. |
| `utils/` | Tiện ích về tệp, thời gian, văn bản, định dạng và kiểm tra phiên bản. |

## Điểm vào và đầu ra

```bash
python main.py
```

`main.py` tải cấu hình, thu thập NewsNow và RSS song song, lưu snapshot dưới `output/<ngày>/txt/`, chạy pipeline phân tích, rồi tạo HTML dưới `output/<ngày>/html/`. Với báo cáo tổng hợp trong ngày, `HTMLRenderer` cũng cập nhật `index.html` ở thư mục gốc để dùng trên GitHub Pages.

MCP server được khởi chạy riêng bằng `python -m mcp_server.server`. Server cung cấp truy vấn, tìm kiếm, phân tích, đọc cấu hình/trạng thái và yêu cầu crawl qua `stdio` hoặc HTTP; dữ liệu lịch sử đến từ thư mục `output/` của môi trường chạy MCP.

Các kênh gửi hiện được cài đặt trong `src/notifiers/` là Telegram và email. Cấu hình có thể chứa thêm khóa cho nền tảng khác để tương thích với thành phần cũ, nhưng module hiện tại chưa có notifier tương ứng.
