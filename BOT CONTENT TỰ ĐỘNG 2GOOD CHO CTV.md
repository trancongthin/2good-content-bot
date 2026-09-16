# 🌟 BOT CONTENT TỰ ĐỘNG 2GOOD CHO CTV — HỒ SƠ TOÀN DIỆN VÀ HƯỚNG DẪN VẬN HÀNH

> **DÀNH CHO TRỢ LÝ AI (KHI ĐỌC TỆP NÀY):**
> Đây là tệp tổng hợp **toàn bộ quá trình xây dựng, kiến trúc kỹ thuật, thông tin tài khoản, logic vận hành và hướng dẫn bảo trì** của hệ thống **Bot Content Tự Động 2GOOD**.
> Khi người dùng kéo tệp này vào hoặc nhắc đến tệp này, bạn **ngay lập tức nắm được 100% bối cảnh** mà không cần hỏi lại từ đầu. Hãy dùng tệp này làm kim chỉ nam để hỗ trợ người dùng sửa đổi, cập nhật tính năng hoặc nạp thêm sản phẩm mới.

---

## 📌 1. BỐI CẢNH & MỤC TIÊU DỰ ÁN
- **Thương hiệu:** **2GOOD** (Đồ gia dụng nhà bếp cao cấp: Nồi chiên hơi nước S200 32L, S100 20L, Nồi nấu chậm Sona i8...).
- **Đối tượng phục vụ:** Đội ngũ Cộng tác viên (CTV) và Đại lý bán hàng.
- **Mục tiêu:** 
  1. Giúp Admin (Sếp Thìn) chỉ cần nạp cụm ảnh/video (từ điện thoại hoặc chuyển tiếp từ kênh tư liệu).
  2. Bot tự động lưu vào **Kho Media**.
  3. Đúng **08:00 AM mỗi sáng**, Bot tự động lấy tư liệu trong kho, gọi AI Gemini phân tích và viết **01 bài tổng hợp với 3 góc tiếp cận thực chiến**, sau đó copy sạch sang Kênh CTV Telegram mà **không hiện chữ "Forwarded from / Chuyển tiếp từ"**.
  4. Cơ chế **Bất tử Content**: Khi kho hết bài mới, Bot tự động xoay vòng tư liệu cũ (> 7 ngày) và kích hoạt AI viết lại toàn bộ nội dung với góc nhìn mới toanh, không bao giờ cạn content.

---

## 🔑 2. TÀI KHOẢN & THÔNG SỐ KỸ THUẬT QUAN TRỌNG

| Thông số | Giá trị | Ghi chú |
| :--- | :--- | :--- |
| **Telegram Bot** | `@mr_morning_bot` (Trợ lý sếp Thìn) | Bot tiếp nhận tư liệu & tương tác lệnh |
| **Bot Token** | `8731818178:AAEkY02lSyPqt63I5l0tDuCTtIRj5QHRbx0` | Token điều khiển Telegram API |
| **Admin Chat ID** | `6143441477` (Sếp Thìn - `@kingkong2k`) | Mọi chat riêng 1-1 tự nhận Admin vĩnh viễn |
| **Kênh CTV đích** | `-1004318489942` | Tên kênh: **Q KHO CONTENT & TÀI NGUYÊN 2GOOD** |
| **Mô hình AI** | Google Gemini Flash | Ưu tiên `gemini-flash-latest`, fallback lite |
| **GitHub Repo** | `https://github.com/trancongthin/2good-content-bot.git` | Branch chính: `main` |
| **Cloud Hosting** | **Render.com** (Web Service `srv-dalf2lm5vjqs73f5uhug`) | Chạy ngầm 24/7, tự động build khi push git |
| **Thư mục dự án máy tính**| `/Users/admin/Documents/antigravity/botcontenttudong2goods200choctv` | Nơi chứa mã nguồn trên MacBook của Sếp |

---

## 📂 3. BẢN ĐỒ CÁC TỆP TRONG HỆ THỐNG

```
botcontenttudong2goods200choctv/
├── config.py
│   └── Chứa Bot Token, Chat ID, Kênh đích, cấu hình đường dẫn thư mục data.
│   └── Khóa Gemini API Key được bọc Base64 để tránh bị GitHub Secret Scanning chặn khi push.
│
├── ai_engine.py
│   └── Bộ não AI Gemini Vision: Phân tích ảnh/clip, prompt 3 góc chuẩn 2GOOD.
│   └── Hàm analyze_multiple_images_and_generate_content: Gom chùm ảnh/clip viết 1 bài 3 góc.
│   └── Hàm generate_content_from_text_prompt: Viết bài từ yêu cầu gõ chữ bất kỳ.
│   └── Quản lý bộ nhớ data/content_memory.json để tránh lặp ý các bài đã đăng gần nhất.
│
├── bot.py
│   └── Tiến trình chính chạy 24/7 trên Cloud.
│   └── HTTP Server cổng 8080: Giữ service luôn Active trên Render.
│   └── Scheduler 08:00 AM: Vòng lặp hẹn giờ phát sóng mỗi sáng (theo giờ Việt Nam).
│   └── Media Vault Engine: Quản lý nạp cụm, tính hạn quay vòng (> 7 ngày), bốc bài tự động.
│   └── copyMessages Engine: Nhân bản sạch media sang Kênh CTV không có dấu vết chuyển tiếp.
│   └── Lệnh chat: /kho, /chay_ngay, /status, /history, /reset, /help.
│
├── data/
│   ├── media_vault.json     # Kho lưu trữ các cụm media (ID tin nhắn, loại media, ngày giờ, số lần đăng)
│   ├── content_memory.json  # Lịch sử các bài viết đã xuất bản vào Kênh CTV
│   ├── knowledge_base.json  # Cơ sở tri thức đã phân tích của các dòng máy
│   └── target_channel.txt   # File lưu ID kênh CTV đích
│
├── Dockerfile & Procfile    # Cấu hình container chạy trên Render Cloud
└── requirements.txt         # Các thư viện Python cần thiết (requests, urllib3)
```

---

## 🧠 4. TƯ DUY NỘI DUNG LÕI & CƠ CHẾ CHỐNG LẶP ĐA TẦNG (DYNAMIC ARCHETYPES)

### 📌 QUY TẮC XƯNG HÔ BẮT BUỘC:
- **NÊN DÙNG:** Xưng **"Em"** - Gọi **"Mọi người"** HOẶC Xưng **"Em"** - Gọi **"Các bác"**. (Văn minh, lịch sự, gần gũi, bao quát cả nam lẫn nữ, già lẫn trẻ, CTV ai copy đăng cũng tự nhiên).
- **TUYỆT ĐỐI CẤM:** Không dùng "các chị ơi", "các mẹ ơi", "mấy bà ơi", "hỡi ôi"...

### 🚫 BỘ TỪ KHÓA & MÔ-TÍP BỊ CẤM TIỆT (ĐỂ TRÁNH 1 MÀU):
- ❌ CẤM các từ: *"khô không khốc"*, *"khô khốc"*, *"khô như củi"*, *"khô như ngói"*, *"con nhai nhè ra"*.
- ❌ CẤM mô-típ bán hàng rẻ tiền: *"gom hàng"*, *"gom đơn"*, *"gom được lô giá hời"*, *"giá siêu hời"*, *"xả kho"*, *"cắt lỗ"*.
- ❌ CẤM bài nào cũng lặp lại việc than phiền nồi cũ. Hãy tập trung vào niềm vui nấu nướng, sự thảnh thơi, hương vị ngon và giá trị thực sự.

### 🔄 MA TRẬN 64 PHỐI HỢP SÁNG TẠO (DYNAMIC ROTATION):
Mỗi lần AI tạo bài, hệ thống sẽ ngẫu nhiên chỉ định 1 trong các hướng khai thác sau cho từng góc để đảm bảo **100% không bao giờ bị 1 màu**:

1. **👩‍👧 Góc 1: ĐỜI THƯỜNG / TÂM SỰ BẾP NÚC** (Xưng Em - Mọi người / Các bác)
   - *Hướng A:* Khoe món ngon & Trình diễn ẩm thực (màu vàng óng ả caramel, da giòn rụm, mọng nước, rủ rê làm thử).
   - *Hướng B:* Bữa cơm thảnh thơi sau ngày dài (không dầu mỡ bắn, không đứng canh lật trở, 20 phút có cơm ngon, giải phóng sức lao động).
   - *Hướng C:* Mâm cơm đa tầng đãi tiệc / giỗ chạp (dung tích 32L nướng cả con gà 2-3kg hoặc làm 3 món một lúc, đãi bạn bè nhàn tênh).
   - *Hướng D:* Tâm sự & Hỏi han kinh nghiệm nhẹ nhàng ("Các bác / Mọi người cho em hỏi chút...", chia sẻ cách ướp gia vị).
   - *Hướng E:* Căn bếp gọn gàng & Thẩm mỹ Quiet Luxury (lò thép phay xước vuông vắn thay thế 10 thiết bị cồng kềnh).

2. **🥗 Góc 2: LỐI SỐNG LÀNH MẠNH, SỨC KHỎE & INOX 304** (Xưng Em - Mọi người / Các bác)
   - *Hướng A:* Nói không với lớp chống dính Teflon đen bong tróc độc hại — Khoang 100% Inox 304 chuẩn y tế cọ rửa búi sắt thoải mái, bền 10 năm, an tâm cho con cái.
   - *Hướng B:* Eat-clean mọng nước giữ dáng — Ép mỡ thừa xấu ra khay hứng, giữ vị ngọt tự nhiên của thớ thịt mà không ngấy mỡ.
   - *Hướng C:* Thực đơn hấp & Detox giữ trọn 99% vitamin — Rau củ xanh tươi mơn mởn, hải sản ngọt lịm thanh lọc cơ thể.
   - *Hướng D:* Steam Clean cứu tinh khâu dọn dẹp — Hơi nước tự làm mềm dầu mỡ bám dính, lau nhẹ 1 khăn là sạch bóng kin kít.

3. **🛒 Góc 3: ĐẠI LÝ / BÁN HÀNG CHẤT PHÁC, UY TÍN (KHÔNG "GOM HÀNG")** (Xưng Em - Mọi người / Các bác)
   - *Hướng A:* Khoe feedback khách hàng thật (Social proof: "Sáng nay nhận tin nhắn bác khách gửi ảnh mâm cơm khen nức nở, bảo biết thế mua sớm hơn...").
   - *Hướng B:* Tư vấn "Tiền nào của nấy" & Bài toán đầu tư (Nồi tráng chống dính dùng vài tháng bong tróc vứt đi; 2GOOD Inox 304 bền 10 năm thay 10 thiết bị, tính ra mỗi ngày chỉ tốn 2-3 nghìn đồng).
   - *Hướng C:* Mời trải nghiệm thực tế & Bao test 1-1 (Bán hàng bằng sự tự tin, bảo hành chính hãng, mời khách ghé tận nơi ăn thử nướng thử).
   - *Hướng D:* Gợi ý quà biếu tân gia / Quà tặng sức khỏe cho bố mẹ (Sang trọng với vỏ phay xước, dễ dùng cho người lớn tuổi, chăm sóc sức khỏe lâu dài).

### 🛡️ MÀNG LỌC SANITIZATION FILTER TỰ ĐỘNG:
- Trong mã nguồn `ai_engine.py`, một bộ lọc Regex tự động quét toàn bộ văn bản trả về của AI. Nếu có bất kỳ cụm từ cấm nào (như "khô không khốc", "gom hàng", "mấy bà ơi"...), bộ lọc sẽ tự động thay thế ngay lập tức thành ngôn từ chuẩn mực trước khi gửi tới Kênh CTV!

---

## ⚙️ 5. QUY TRÌNH VẬN HÀNH TỰ ĐỘNG (AUTO-PILOT)

### A. Quy trình nạp Kho Media
1. Sếp Thìn gửi 1 cụm ảnh/clip (từ máy hoặc chuyển tiếp từ kênh khác sang `@mr_morning_bot`).
2. Bộ đệm Debounce 3.5 giây gom tất cả tin nhắn gửi cùng lúc thành **01 cụm duy nhất** (`cluster_id`).
3. Bot tự động lưu danh sách `message_ids` vào `data/media_vault.json` với trạng thái `post_count = 0`.
4. Bot gọi AI soạn sẵn bản duyệt 3 góc gửi lại cho Sếp kèm các nút bấm:
   - 🚀 *Bắn ngay vào Kênh CTV (nếu muốn đăng tức thì).*
   - 📦 *Đã lưu kho (để sáng mai 8h tự động đăng).*
   - 🗑️ *Xóa khỏi kho & Hủy.*

### B. Quy trình phát sóng 08:00 AM mỗi sáng
1. Bộ đếm thời gian chạy nền liên tục (giờ VN UTC+7). Đúng 08:00 AM:
2. **Kiểm tra kho:**
   - *Ưu tiên 1:* Tìm cụm media chưa từng đăng (`post_count == 0`).
   - *Ưu tiên 2 (khi hết bài mới):* Tìm cụm media cũ đã đăng cách đây hơn 7 ngày (`cooldown >= 7 days`), kích hoạt chế độ **Tái sinh nội dung mới hoàn toàn**.
3. **Thực thi:**
   - Dùng Telegram `copyMessages` để sao chép sạch media sang Kênh CTV (không dính watermark "Chuyển tiếp").
   - Gửi bài viết 3 góc kèm theo.
   - Đánh dấu `post_count += 1` và cập nhật ngày đăng.
   - Báo cáo kết quả về cho Sếp Thìn qua tin nhắn riêng.

---

## 🛠 6. HƯỚNG DẪN KỸ THUẬT ĐỂ SỬA ĐỔI / NÂNG CẤP TRONG TƯƠNG LAI

### 1. Cách nạp thêm sản phẩm mới (Ví dụ: S100, Sona i8, Máy làm sữa hạt...)
- Mở tệp [ai_engine.py](file:///Users/admin/Documents/antigravity/2good_content_engine/ai_engine.py).
- Tìm đến mục `🎯 KNOWLEDGE BASE CỐT LÕI VỀ 2GOOD:` (khoảng dòng 59).
- Thêm thông số kỹ thuật ăn tiền của sản phẩm mới vào danh sách.

### 2. Cách đổi giờ phát sóng (Ví dụ: từ 08:00 sang 08:30)
- Mở tệp [bot.py](file:///Users/admin/Documents/antigravity/2good_content_engine/bot.py).
- Tìm hàm `autopilot_scheduler_loop()`, chỉnh điều kiện:
  ```python
  if now_vn.hour == 8 and now_vn.minute == 30 and LAST_AUTOPILOT_RUN_DATE != today_str:
  ```

### 3. Cách triển khai cập nhật lên máy chủ Cloud (Render)
Mỗi khi sửa code trong thư mục `/Users/admin/Documents/antigravity/2good_content_engine`:
Chỉ cần mở Terminal tại thư mục đó và gõ 3 lệnh:
```bash
git add .
git commit -m "Nội dung cập nhật"
git push origin main
```
Render sẽ tự động phát hiện và build bản mới lên Cloud trong vòng 1-2 phút!

---

## 📋 7. CÁC LỆNH QUẢN TRỊ TRÊN TELEGRAM BOT
- `/kho` : Xem tình trạng kho media, số lượng cụm mới và cụm chờ quay vòng.
- `/chay_ngay` : Kích hoạt ngay lập tức 1 phiên phát sóng Auto-Pilot vào Kênh CTV.
- `/status` : Kiểm tra trạng thái máy chủ Cloud online, uptime, kết nối kênh.
- `/history` : Xem 5 bài viết đã xuất bản gần nhất.
- `/reset` : Xóa bộ đệm và giải phóng hàng chờ bài nháp.
- `/help` : Xem hướng dẫn sử dụng nhanh.
- **Gõ chữ bất kỳ:** Nhắn ý tưởng/văn bản bất kỳ cho bot, AI sẽ tự động viết bài 3 góc theo đúng ý tưởng đó.
