# Project NORI

Một bạn đồng hành AI nói tiếng Việt, có trí nhớ dài hạn. Hiện chạy trên terminal; voice, Live2D và thế giới 2D đang trong kế hoạch.

Ngôn ngữ: [English](README.md) | Tiếng Việt

**Trạng thái:** v0 xong (brain core). v1 (dùng hằng ngày và chỉnh trí nhớ) đang làm.
Đây là dự án cá nhân. Nội dung chat được gửi tới các backend LLM bạn cấu hình; chỉ phần lưu trữ (lịch sử, ký ức, log) nằm ở máy.

## Bắt đầu nhanh

```powershell
git clone https://github.com/[username]/nori_ai.git
cd nori_ai
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy config.example.yaml config.yaml
copy persona.example.md persona.md
copy .env.example .env
```

1. Điền API key vào `.env`.
2. Trong `config.yaml`, điền `model` cho từng backend bạn dùng. Tên model free hay đổi, hãy xem danh sách hiện tại của nhà cung cấp.
3. Sửa `persona.md` (tên companion, tên người dùng, giọng điệu).
4. Chạy `python -m brain.cli`.

Phiên bản Python dùng khi phát triển: [chạy `python --version` rồi điền].

| Lệnh | Tác dụng |
|---|---|
| `/remember <nội dung>` | Lưu một ký ức dài hạn |
| `/stats` | Số request, tỉ lệ lỗi, độ trễ token đầu (trung vị) theo backend |
| `/q` | Thoát |

## Cách hoạt động

```
câu của bạn -> tìm ký ức (FTS5) + lịch sử gần nhất + persona -> LLM router -> trả lời
                                                                   |
                                    thử backend theo thứ tự: gemini -> openrouter -> local
```

- `brain/llm.py`: router. Thử backend theo thứ tự; chuyển sang backend sau khi gặp lỗi, giới hạn tốc độ (429) hoặc trả lời rỗng. Backend dính 429 bị bỏ qua 5 phút. Không bao giờ chuyển backend giữa chừng khi đang stream, vì sẽ lặp chữ.
- `brain/memory.py`: ký ức trong SQLite, tìm theo từ khóa bằng FTS5, không phân biệt dấu.
- `brain/core.py`: dựng prompt (persona + mục `KÝ ỨC` + `history_turns` lượt gần nhất). Mục ký ức luôn có mặt kể cả khi trống, để model biết mình không có gì để dựa vào.
- `brain/db.py`: schema, lịch sử chat, `llm_log` (backend, model thực tế, độ trễ, lỗi của từng lần gọi).
- `brain/bench.py`: bộ benchmark (xem bên dưới).

Dữ liệu nằm trong `companion.db` (đường dẫn theo `db_path`). Lượt chat chỉ được lưu khi có câu trả lời thành công.

## Cấu hình

Mọi thứ nằm trong `config.yaml` (bị git bỏ qua; `config.example.yaml` là file mẫu). Key để trong `.env` và được gọi bằng tên qua `api_key_env`.

Thêm backend bằng cách thêm một khối. Endpoint nào tương thích OpenAI cũng dùng được. Thứ tự là thứ tự ưu tiên.

```yaml
- name: my_provider
  base_url: "https://api.example.com/v1"
  api_key_env: MY_PROVIDER_API_KEY
  model: "model-name"
  timeout: 30
  max_tokens: 300
```

Backend thiếu key sẽ bị bỏ qua kèm cảnh báo; `enabled: false` để tắt. `temperature` và `strip_cjk` (cắt luồng ở ký tự Trung/Nhật đầu tiên) là tùy chọn theo từng backend.

## Quyết định và giới hạn đã biết

Đọc mục này trước khi đổi thiết kế.

- **Gemini là backend chính; local chỉ để khẩn cấp.** Trong benchmark, model local 3B kém xa các model API và trượt cả việc cơ bản (dùng lịch sử chat, tính toán, lẫn chữ Trung). Độ trễ của nó cũng loại khả năng dùng cho voice. Điểm cuối: [điền từ lần chạy `score` gần nhất, kèm ngày].
- **`openrouter/free` là router, không phải một model.** Mỗi request có thể do một model free khác nhau xử lý, nên chất lượng và độ trễ dao động. Cột `model` trong `llm_log` cho biết model nào đã trả lời. Đừng benchmark nó như một model cố định.
- **Free tier đổi chính sách không báo trước.** Điểm benchmark chỉ là ảnh chụp tại một thời điểm. Thứ bền là bộ harness: thêm một khối backend rồi chạy lại.
- **Truy xuất ký ức theo từ khóa.** Có thể bỏ sót ký ức liên quan ("tôi là ai") và cũng có thể kéo ký ức không liên quan vào. Hướng xử lý nếu cứ sai: luôn nạp các ký ức lưu bằng `/remember`, chỉ dùng FTS cho phần còn lại, hoặc chuyển sang embedding.
- **Thông tin chỉ sống trong lịch sử `history_turns` lượt** (mặc định 10). Cái gì cần nhớ lâu thì phải `/remember`.
- **Gemini stream theo khối lớn** (khoảng 3 chunk cho một câu ngắn), không chảy từng từ. Với voice, bộ cắt câu phải xử lý trường hợp một chunk chứa nhiều câu.
- **Ngân sách độ trễ cho voice:** token đầu của Gemini khoảng 1 đến 2,5 giây. STT và TTS tiếng Việt vẫn cần đo trên máy thật (RAM 8 GB, MX330 2 GB) trước khi cam kết làm v2.

## Benchmark

`brain/bench.py` chạy 20 câu tiếng Việt trên mọi backend đã cấu hình, ẩn và xáo tên backend, ghi câu trả lời ra `bench_out.md` để chấm tay (0 đến 3). Chạy lại khi đổi persona, prompt hoặc model.

```powershell
python -m brain.bench          # ghi bench_out.md và bench_key.json
# điền "score A: 3" v.v. trong bench_out.md
python -m brain.bench score    # tổng điểm theo backend
```

Quy tắc nhận model local, đặt trước khi xem kết quả: đạt từ 70% điểm của backend API tốt nhất và không có điểm 0 ở P5, P6, P12.

## Lộ trình

Là kế hoạch, không phải lời hứa.

- [x] v0: brain core, backend thay được, trí nhớ, benchmark
- [ ] v1: dùng hằng ngày 2 đến 3 tuần; ghi lại mọi chỗ gây khó chịu; chỉnh trí nhớ và persona
- [ ] v2: voice (STT, TTS) và Live2D, chỉ làm nếu v1 thực sự được dùng mỗi ngày và độ trễ STT/TTS chấp nhận được
- [ ] v3: companion trong thế giới 2D (hành vi bằng utility AI, gọi LLM thưa)

Các module cảm xúc, tò mò, self-model trong thiết kế ban đầu hoãn lại cho đến khi v1 chứng minh được giá trị.

## Ghi chú

- Phần lớn code được viết với sự hỗ trợ của AI (Claude), sau đó tác giả tự kiểm thử và chỉnh sửa.
- Chỉ phần code theo giấy phép MIT. Nhân vật, art, persona và model Live2D không nằm trong repo này.

## Giấy phép

MIT. Xem [LICENSE](LICENSE).
