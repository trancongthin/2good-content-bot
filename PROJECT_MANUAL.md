# 📖 2GOOD CONTENT ENGINE & AUTO-PILOT TELEGRAM BOT (HỆ THỐNG VẬN HÀNH TOÀN DIỆN)

> **Tài liệu này lưu trữ toàn bộ kiến trúc, tư duy thiết kế, luồng dữ liệu và hướng dẫn nâng cấp của Bot.**
> Khi bắt đầu một phiên làm việc mới, bất kỳ Trợ lý AI nào đọc file này đều sẽ hiểu 100% bối cảnh và tiếp tục phát triển, cập nhật hoặc bảo trì hệ thống ngay lập tức.

---

## 🎯 1. TỔNG QUAN & MỤC TIÊU DỰ ÁN
- **Tên dự án:** 2GOOD Content Engine & Auto-Pilot Telegram Bot.
- **Mục đích:** Tự động hóa 100% khâu tạo và cung cấp tư liệu bán hàng (ảnh, video, content 3 góc tiếp cận) cho đội ngũ Cộng tác viên (CTV) và Đại lý của thương hiệu gia dụng **2GOOD** (các sản phẩm chủ lực: Nồi chiên hơi nước S200 32L, S100 20L, Nồi nấu chậm Sona i8...).
- **Cơ chế cốt lõi:**
  1. **Kho Media Thông minh (Media Vault):** Nhận cụm ảnh + clip từ Sếp, gom thành cụm và lưu trữ an toàn.
  2. **Hẹn giờ 08:00 AM mỗi sáng (Auto-Pilot Bất Tử Content):** Đúng 8h sáng, tự động bốc 1 cụm media từ kho, phân tích hình ảnh qua Gemini Vision, viết bài 3 góc và copy sạch sang Kênh CTV. Nếu hết bài mới, tự động xoay vòng bài cũ (> 7 ngày) và viết lại theo góc nhìn hoàn toàn mới lạ.
  3. **Không dấu vết (Zero Watermark):** Dùng Telegram API `copyMessages`, không hiện chữ "Forwarded from / Chuyển tiếp từ".

---

## ⚙️ 2. THÔNG SỐ KỸ THUẬT & TÀI KHOẢN HỆ THỐNG
- **Bot Username:** `@mr_morning_bot` (Trợ lý sếp Thìn).
- **Bot Token:** `8731818178:AAEkY02lSyPqt63I5l0tDuCTtIRj5QHRbx0`
- **Admin Chat ID (Sếp Thìn):** `6143441477` (Mọi đoạn chat 1-on-1 với Bot tự động nhận diện quyền Admin vĩnh viễn).
- **Kênh CTV đích:** `-1004318489942` (Q Kho Content & Tài Nguyên 2GOOD).
- **Mô hình AI:** Google Gemini Flash (`gemini-flash-latest`, fallback `gemini-flash-lite-latest`, `gemini-3.1-flash-lite`).
- **Mã nguồn GitHub:** `git@github.com:trancongthin/2good-content-bot.git` (Branch `main`).
- **Máy chủ Cloud 24/7:** Render.com (Web Service `srv-dalf2lm5vjqs73f5uhug`, tự động auto-deploy mỗi khi `git push origin main`).

---

## 🏗 3. CẤU TRÚC THƯ MỤC & CÁC FILE CHÍNH
```
2good_content_engine/
├── config.py             # Chứa Token, API Key Gemini (mã hóa Base64 tránh bị GitHub chặn), ID Admin, đường dẫn file data
├── ai_engine.py          # Não bộ AI: Prompt 3 góc chuẩn 2GOOD, tích hợp Vision đa ảnh/clip, ghi nhớ bài cũ tránh trùng lặp
├── bot.py                # File điều hành chính: Polling tin nhắn, HealthCheck server port 8080, Scheduler 8h sáng, Media Vault
├── PROJECT_MANUAL.md     # Tài liệu lưu trữ tri thức toàn diện này
├── data/
│   ├── media_vault.json    # KHO MEDIA: Lưu toàn bộ cụm ảnh/video (message_ids, ngày nạp, số lần đăng, ghi chú)
│   ├── content_memory.json # LỊCH SỬ ĐÃ ĐĂNG: Lưu 5-10 bài gần nhất để AI đối chiếu tránh lặp nội dung
│   ├── knowledge_base.json # Dữ liệu tính năng & thông số sản phẩm đã phân tích
│   └── target_channel.txt  # ID kênh CTV đích (-1004318489942)
├── Dockerfile & Procfile # Cấu hình môi trường chạy trên máy chủ Cloud Render
└── requirements.txt      # Thư viện Python (requests, urllib3...)
```

---

## 🧠 4. TƯ DUY CONTENT LÕI (3 GÓC TIẾP CẬN CHUẨN 2GOOD)
Mỗi bài viết AI tạo ra bắt buộc phải có:
1. **Icon / Emoji sinh động:** Tự nhiên, ngắt dòng thoáng mắt, phong cách Facebook/Zalo.
2. **5–7 Hashtag chuẩn ở cuối:** `#2GOOD #NoiChienHoiNuoc2GOOD #2GOOD_S200 #MeBimNoiTro #EatClean #Inox304...`
3. **Lời nhắc tải clip:** Nếu cụm bài có video, bài viết luôn có lời nhắc CTV tải clip về up TikTok/Reels để kéo tương tác.
4. **3 Góc tiếp cận chân thật:**
   - 👩‍👧 **Góc 1 (Mẹ bỉm sữa & Nội trợ):** Giọng tâm sự chị em, nấu nướng nhàn tênh, giải phóng sức lao động, mâm cơm đa món 15-20 phút, an toàn cho con.
   - 🥗 **Góc 2 (Eat-clean, Healthy & Inox 304 chuẩn y tế):** Phân tích lý trí, nói KHÔNG với chống dính Teflon độc hại, công nghệ hơi nước giữ trọn vị ngọt tự nhiên không khô xác, giảm dầu mỡ.
   - 🛒 **Góc 3 (Đại lý / CTV bán hàng dân dã):** Giọng xởi lởi, thân mật ("Em chào các bác / Các anh chị em ơi... hôm nay em gom được lô giá hời, bao test 1-1...").

---

## 🗄 5. CÁCH THỨC HOẠT ĐỘNG CỦA KHO MEDIA & AUTO-PILOT
1. **Nạp cụm media:** Sếp gửi ảnh hoặc video vào bot. Cơ chế Debounce 3.5s tự động gom tất cả tin nhắn gửi cùng lúc thành 1 cụm (`cluster_id`), lưu vào `data/media_vault.json`.
2. **Auto-Pilot 08:00 AM:**
   - Chạy nền bằng tiểu trình (thread) độc lập theo giờ Việt Nam.
   - **Ưu tiên 1:** Bốc cụm media chưa đăng (`post_count == 0`).
   - **Ưu tiên 2:** Khi kho hết bài mới, bốc cụm cũ đã đăng cách đây > 7 ngày, kích hoạt prompt **Tái sinh góc nhìn mới lạ hoàn toàn**.
   - Dùng Telegram `copyMessages` để nhân bản sạch sang Kênh CTV mà không hiện chữ "Chuyển tiếp".
   - Bắn bài viết 3 góc đi kèm.

---

## 🛠 6. HƯỚNG DẪN KHI MUỐN SỬA ĐỔI HOẶC NÂNG CẤP TRONG TƯƠNG LAI
Khi mở lại một cuộc trò chuyện mới:
1. **Cập nhật thêm sản phẩm mới (S100, Sona i8, v.v.):**
   - Mở `ai_engine.py`, tìm đoạn `🎯 KNOWLEDGE BASE CỐT LÕI VỀ 2GOOD:` và thêm thông số kỹ thuật của model mới vào danh sách.
2. **Sửa giờ hẹn phát sóng:**
   - Mở `bot.py`, tìm hàm `autopilot_scheduler_loop()`, chỉnh `now_vn.hour == 8` sang khung giờ mong muốn.
3. **Đẩy cập nhật lên Cloud:**
   - Chỉ cần chạy lệnh:
     ```bash
     git add .
     git commit -m "mô tả nội dung cập nhật"
     git push origin main
     ```
   - Render sẽ tự động bắt lấy commit mới và cập nhật bot trên đám mây trong vòng 1-2 phút!
