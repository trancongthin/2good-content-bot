import json
import base64
import datetime
import requests
import re
import random
from config import GEMINI_API_KEY, KB_FILE, MEMORY_FILE

MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]

# Dynamic Archetypes for rich, non-repetitive variety (64 combinations)
ANGLE_1_ARCHETYPES = [
    (
        "KHOE MÓN NGON & TRÌNH DIỄN ẨM THỰC RỦ RÊ LÀM THỬ",
        "Tập trung miêu tả độ hấp dẫn của món ăn (màu vàng cánh gián óng ả, da giòn rụm, bên trong ngọt lịm mọng nước). Chia sẻ cách làm đơn giản và rủ rê mọi người/các bác cuối tuần đổi bữa cho gia đình."
    ),
    (
        "BỮA CƠM THẢNH THƠI & GIẢI PHÓNG SỨC LAO ĐỘNG",
        "Tập trung vào cảm giác nhẹ nhõm sau một ngày dài đi làm: không phải đứng canh dầu mỡ bắn, không khói bốc ám vào người. Cho đồ vào lò, bấm 1 nút là 20 phút sau có cơm ngon lành cho cả nhà."
    ),
    (
        "MÂM CƠM ĐA TẦNG / TIẾP ĐÃI BẠN BÈ, GIỖ CHẠP",
        "Tập trung vào dung tích khủng 32L: nướng vừa cả con gà 2-3kg hoặc làm cùng lúc 3-4 món trên các tầng khay. Nấu cỗ hay đãi tiệc gia đình nhàn tênh, không phải chia làm nhiều mẻ lắt nhắt."
    ),
    (
        "TÂM SỰ & HỎI HAN KINH NGHIỆM BẾP NÚC TỰ NHIÊN",
        "Bắt đầu bằng câu hỏi khiêm tốn, gần gũi: 'Mọi người cho em hỏi chút...' hoặc 'Các bác có hay làm món này không...'. Chia sẻ kinh nghiệm thực tế về gia vị, cách ướp và rủ mọi người trao đổi."
    ),
    (
        "TỐI GIẢN CĂN BẾP & THẨM MỸ QUIET LUXURY",
        "Tập trung vào không gian bếp: một chiếc lò vuông vức phay xước sang trọng thay thế cả đống xoong chảo, lò vi sóng, nồi hấp cồng kềnh. Mặt kính trong suốt ngắm thức ăn chín xèo xèo cực kỳ mãn nhãn."
    )
]

ANGLE_2_ARCHETYPES = [
    (
        "KHOANG INOX 304 CHUẨN Y TẾ & NÓI KHÔNG VỚI CHỐNG DÍNH TEFLON",
        "Tập trung vào an toàn sức khỏe: Nỗi sợ lớp chống dính Teflon đen bong tróc phôi nhiễm chất độc ở nhiệt độ cao. Nồi 2GOOD với khoang 100% Inox 304 không gỉ, cọ rửa búi cước sắt thoải mái, bền bỉ 5-10 năm, nấu cho con cái hay bố mẹ ăn an tâm tuyệt đối."
    ),
    (
        "EAT-CLEAN MỌNG NƯỚC GIỮ DÁNG KHÔNG NGÁN",
        "Tập trung vào bí quyết giảm mỡ giữ dáng: Công nghệ hơi nước siêu nhiệt ép bớt lượng mỡ thừa xấu chảy ra khay hứng, nhưng vẫn khóa chặt vị ngọt tự nhiên của thịt bò, ức gà, cá hồi. Ăn healthy mà vẫn đậm đà, ngon miệng, không bị khô xơ."
    ),
    (
        "THỰC ĐƠN HẤP & DETOX GIỮ NGUYÊN 99% VITAMIN",
        "Tập trung vào chức năng hấp hơi nước: Đĩa rau củ hấp ngũ sắc hay hải sản giữ nguyên sắc xanh tươi mơn mởn và vị ngọt thanh, không bị nhũn nát hay mất chất như luộc nước sôi. Phù hợp cho chế độ ăn thanh lọc cơ thể."
    ),
    (
        "TỰ LÀM SẠCH BẰNG HƠI NƯỚC (STEAM CLEAN) — CỨU TINH KHÂU DỌN RỬA",
        "Tập trung vào nỗi ám ảnh cọ rửa dầu mỡ: Chế độ Steam Clean xịt hơi sương siêu nhiệt làm mềm nhũn mọi vết dầu mỡ cứng đầu bám trong khoang Inox, chỉ cần dùng khăn lướt nhẹ 1 đường là sạch bóng kin kít."
    )
]

ANGLE_3_ARCHETYPES = [
    (
        "KHOE FEEDBACK KHÁCH HÀNG THẬT (SOCIAL PROOF)",
        "Mở đầu bằng niềm vui nhận phản hồi từ khách: 'Sáng nay nhận được tin nhắn của bác khách gửi ảnh mâm cơm làm bằng chiếc 2GOOD này mà em vui cả ngày...', 'Bác bảo từ ngày có máy, cả nhà siêng ăn cơm nhà hẳn, biết thế mua sớm hơn...'"
    ),
    (
        "TƯ VẤN 'TIỀN NÀO CỦA NẤY' & ĐỘ BỀN 5-10 NĂM",
        "Phân tích góc nhìn đầu tư tiêu dùng thông minh: Nhiều bác đắn đo giá thành, nhưng chiếc nồi chống dính 1-2 triệu dùng vài tháng tróc sơn phải vứt đi. Chiếc 2GOOD S200 khoang Inox 304 nguyên khối 32L thay thế 10 thiết bị bếp, dùng 5-10 năm vẫn sáng bóng, tính ra mỗi ngày chỉ tốn 2-3 ngàn đồng mà bảo vệ sức khỏe cả đời."
    ),
    (
        "MỜI TRẢI NGHIỆM THỰC TẾ & BAO TEST 1 ĐỔI 1",
        "Thể hiện sự tự tin của người bán bằng uy tín thật: Hàng chính hãng bảo hành đầy đủ, bao test 1-1 nếu có lỗi. Mời các bác/mọi người ở gần cứ ghé qua tận nơi xem máy, nướng thử ăn thử, ưng ý thì rinh về."
    ),
    (
        "GỢI Ý QUÀ BIẾU TÂN GIA / QUÀ TẶNG SỨC KHỎE CHO BỐ MẸ",
        "Gợi ý chiếc máy như một món quà biếu tinh tế, sang trọng và giàu ý nghĩa: Vỏ thép phay xước chuẩn Quiet Luxury, bảng điều khiển trực quan dễ dùng cho cả người lớn tuổi, giúp bố mẹ nấu nướng thảnh thơi và ăn uống an lành."
    ),
    (
        "GOM ĐƠN / LÔ HÀNG CHÍNH HÃNG GIÁ HỜI CHO MỌI NGƯỜI",
        "Phong cách đại lý bán hàng thực chiến: 'Các bác/mọi người ơi, hôm nay em gom được lô 2GOOD chính hãng giá hời/giá tốt cho mọi người... Bao test 1-1, bác nào lấy ới em ship tận tay nhé!'"
    )
]

def clean_content_text(text):
    """
    Sanitize text to guarantee forbidden pronouns never appear.
    """
    if not isinstance(text, str):
        return text
    
    replacements = [
        (r'(?i)\bmấy bà ơi\b', 'mọi người ơi'),
        (r'(?i)\bcác chị ơi\b', 'mọi người ơi'),
        (r'(?i)\bcác mẹ ơi\b', 'các bác ơi'),
        (r'(?i)\bhỡi ôi\b', 'thực sự'),
    ]
    cleaned = text
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)
    return cleaned

def sanitize_content_matrix(matrix):
    if not isinstance(matrix, dict):
        return matrix
    sanitized = {}
    for k, v in matrix.items():
        sanitized[k] = clean_content_text(v)
    return sanitized

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_memory(entry):
    memory = load_memory()
    memory.append(entry)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def load_kb():
    try:
        with open(KB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_kb(entry):
    kb = load_kb()
    kb.append(entry)
    with open(KB_FILE, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

def analyze_multiple_images_and_generate_content(images_bytes_list, custom_note="", has_video=False):
    """
    Multimodal Pipeline for Album of Images / Video Thumbnails:
    Analyzes ALL media together in 1 single call to generate exactly 1 unified post
    with 3 authentic, engaging angles with emojis, hashtags, and natural personal tone.
    """
    memory = load_memory()
    recent_memory_str = json.dumps(memory[-5:], ensure_ascii=False) if memory else "Chưa có bài nào."
    num_photos = len(images_bytes_list)
    custom_instruction_prompt = f"\n⚠️ LƯU Ý / YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG CHO BÀI NÀY: {custom_note}\n(Bắt buộc phải lồng ghép chi tiết yêu cầu này vào nội dung các bài viết)" if custom_note else ""
    video_prompt = "\n🎬 BỘ MEDIA NÀY CÓ ĐÍNH KÈM VIDEO QUAY THỰC TẾ (hơi nước bốc lên, thức ăn nướng xèo xèo...). Hãy viết thêm lời nhắc khéo CTV tải clip bên trên về up TikTok / Reels / Facebook Story để hút view và chốt đơn nhanh!" if has_video else ""

    # Pick dynamic archetypes to ensure 100% variety
    a1_title, a1_desc = random.choice(ANGLE_1_ARCHETYPES)
    a2_title, a2_desc = random.choice(ANGLE_2_ARCHETYPES)
    a3_title, a3_desc = random.choice(ANGLE_3_ARCHETYPES)

    system_prompt = f"""
Bạn là Chuyên gia Sáng tạo Nội dung & Bán hàng thực chiến của thương hiệu gia dụng 2GOOD (Nồi chiên hơi nước S200 dung tích 32L, S100, Nồi nấu chậm Sona i8...).

BẠN ĐƯỢC CẤP {num_photos} HÌNH ẢNH / TƯ LIỆU THỰC TẾ CỦA CÙNG 1 BỘ TƯ LIỆU.{video_prompt}{custom_instruction_prompt}
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY (BẮT BUỘC TRÁNH TRÙNG LẶP NỘI DUNG NÀY):
{recent_memory_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 KNOWLEDGE BASE CỐT LÕI & ĐIỂM ĂN TIỀN TỪNG MODEL 2GOOD:

🔥 DÒNG NỒI CHIÊN HƠI NƯỚC 2GOOD S100 (20 LÍT - LỒNG ĐẢO 360 ĐỘ TỰ ĐỘNG & SUPERHEAT 115°C):
- Dung tích: 20 Lít rộng rãi (chuẩn cho gia đình 6-8 người, nướng gà nguyên con hoặc nấu cùng lúc 2-3 món trên các tầng khay).
- Công suất & Nhiệt độ: 1800W mạnh mẽ, dải nhiệt linh hoạt cực rộng từ 40°C đến 230°C.
- Chất liệu: Vỏ nhựa ABS cao cấp, cửa kính cách nhiệt 2 lớp chống bỏng an toàn. Lòng nồi và toàn bộ 8 phụ kiện đều làm từ 100% Inox 304 chuẩn y tế, không chống dính Teflon độc hại, cọ rửa búi cước sắt thoải mái.
- Kích thước & Điều khiển: 420 x 429 x 355 mm, màn hình cảm ứng LED kết hợp núm vặn trực quan.
- Đa chức năng 3 trong 1: Chiên không dầu + Hấp nhiệt + Chiên hơi nước kết hợp (giòn rụm bên ngoài, mọng ẩm ngọt nước bên trong, không khô xơ).
- Công nghệ hấp SuperHeat: Hạt sương siêu nhỏ nano (< 100nm) với nhiệt độ hơi nước lên tới 115°C, thẩm thấu cực nhanh, giữ trọn 99% vitamin và vị ngọt tự nhiên của rau củ, thịt cá.
- ĐẶC QUYỀN ĐỈNH CAO — LỒNG TỰ ĐẢO 360 ĐỘ: Tự động xoay đảo liên tục cho khoai tây chiên, rang lạc (đậu phộng), hạt điều, hạt dẻ chín đều vàng ruộm mọi góc mà không cần mở lò đứng lật dở!
- Chế độ ủ ấm & Lên men mở rộng: Nhiệt độ thấp ủ bột bánh mì (40°C), làm sữa chua (45°C), chưng yến (85°C) tiện dụng.
- Full bộ 8 phụ kiện Inox 304 kèm sẵn: Khay chiên/nướng, vỉ chiên/nướng, khay hấp, khay hứng dầu mỡ, lồng đảo 360 độ, dụng cụ nâng gắp, xiên quay rô-ti và ghim thực phẩm.

🔥 DÒNG NỒI CHIÊN HƠI NƯỚC 2GOOD S200 (32 LÍT - DUNG TÍCH CỰC ĐẠI & STEAM CLEAN):
- Dung tích cực đại: 32 Lít (khoang 100% Inox 304 nguyên khối), nướng vừa cả con gà 2-3kg hoặc mâm cỗ 3-4 món một lúc.
- Công nghệ phun sương siêu nhiệt Steam Active: Ngoài giòn xém thơm phức, trong giữ trọn nước ngọt mọng tự nhiên.
- Tự làm sạch bằng hơi nước (Steam Clean): Hơi sương siêu nhiệt làm mềm nhũn dầu mỡ bám dính, chỉ cần lau nhẹ 1 đường là sạch bóng.
- Gia nhiệt đối lưu 360 độ không cần lật trở. Vỏ thép phay xước Quiet Luxury sang trọng.

🔥 DÒNG NỒI NẤU CHẬM 2GOOD SONA i8:
- Công nghệ nấu cách thủy truyền nhiệt gián tiếp qua hơi nước, thố sứ tự nhiên cao cấp, giữ trọn vi chất dinh dưỡng, nấu cháo, chưng yến, hầm canh phân tầng.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 NGUYÊN TẮC ĐA DẠNG HÓA NỘI DUNG (TRÁNH 1 MÀU & TRÁNH LẶP Ý):
- Tuyệt đối KHÔNG bài nào cũng lặp đi lặp lại cùng một mô-típ hoặc cùng một lối mở bài quen thuộc. Bắt buộc bám sát ĐỊNH HƯỚNG SÁNG TẠO riêng biệt được chỉ định cho từng góc dưới đây để bài viết luôn tươi mới, tự nhiên và phong phú.
- Tránh trùng lặp tình huống và câu chuyện của các bài đã đăng gần nhất ở trên.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✍️ QUY TẮC XƯNG HÔ CHUẨN:
- Xưng "Em" - Gọi "Mọi người" HOẶC Xưng "Em" - Gọi "Các bác".
- Tuyệt đối CẤM: "các chị ơi", "các mẹ ơi", "mấy bà ơi", "hỡi ôi".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ĐỊNH HƯỚNG SÁNG TẠO ĐẶC BIỆT CHO LẦN NÀY (ĐẢM BẢO KHÔNG BỊ 1 MÀU):

👩‍👧 GÓC 1: BỮA CƠM GIA ĐÌNH / ĐỜI THƯỜNG (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Hãy khai thác sâu theo hướng: [{a1_title}]
Chi tiết định hướng: {a1_desc}
(Kèm đầy đủ emoji sinh động và 5-7 hashtag ở cuối bài).

🥗 GÓC 2: ĂN UỐNG LÀNH MẠNH, SỨC KHỎE & CHẤT LIỆU (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Hãy khai thác sâu theo hướng: [{a2_title}]
Chi tiết định hướng: {a2_desc}
(Kèm đầy đủ emoji và 5-7 hashtag ở cuối bài).

🛒 GÓC 3: ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Hãy khai thác sâu theo hướng: [{a3_title}]
Chi tiết định hướng: {a3_desc}
(Nếu bài có video: nhắc khéo CTV tải clip về up Reels/TikTok/Zalo để hút khách; Kèm đầy đủ emoji và 5-7 hashtag ở cuối bài).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HÃY TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON CHUẨN (KHÔNG THÊM BẤT KỲ CHỮ NÀO NGOÀI JSON):
{{
  "product_code": "2GOOD S200 (hoặc mã sản phẩm nhận diện được)",
  "visual_fact": "Mô tả ngắn gọn món ăn và khung cảnh trong bộ {num_photos} ảnh",
  "technical_fact": "Chi tiết kỹ thuật nổi bật (VD: Khoang Inox 304, Hơi nước Steam Active...)",
  "marketing_claim": "Tuyên bố thực tế (VD: Ngoài giòn rụm trong mọng nước ngọt)",
  "content_matrix": {{
    "me_bim_noi_tro": "Toàn bộ bài viết Góc 1 (Tiêu đề + Emoji + Thân bài tự nhiên theo định hướng + CTA + Hashtags)",
    "eat_clean_inox304": "Toàn bộ bài viết Góc 2 (Tiêu đề + Emoji + Thân bài Eat-clean/Sức khỏe theo định hướng + CTA + Hashtags)",
    "dai_ly_dan_da": "Toàn bộ bài viết Góc 3 (Tiêu đề + Emoji + Bài bán hàng uy tín theo định hướng + CTA + Hashtags)"
  }}
}}
"""

    parts = [{"text": system_prompt}]
    for img_bytes in images_bytes_list:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": encode_image(img_bytes)
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.85,
            "response_mime_type": "application/json"
        }
    }

    for model_name in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                
                try:
                    data = json.loads(raw_text, strict=False)
                except Exception:
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', lambda m: ' ' if m.group() in '\n\r\t' else '', raw_text)
                    try:
                        data = json.loads(cleaned, strict=False)
                    except Exception:
                        data = {
                            "product_code": "2GOOD S200",
                            "visual_fact": f"Bộ {num_photos} ảnh món ăn & nồi chiên hơi nước",
                            "technical_fact": "Khoang Inox 304, công nghệ đối lưu hơi nước 360",
                            "marketing_claim": "Giòn rụm ngoài mọng nước trong",
                            "content_matrix": {
                                "me_bim_noi_tro": raw_text[:1000],
                                "eat_clean_inox304": raw_text[1000:2000] if len(raw_text) > 1000 else raw_text,
                                "dai_ly_dan_da": raw_text[2000:3000] if len(raw_text) > 2000 else raw_text
                            }
                        }
                
                # Sanitize content matrix to eliminate any residual forbidden cliches
                if "content_matrix" in data:
                    data["content_matrix"] = sanitize_content_matrix(data["content_matrix"])

                save_kb({
                    "product_code": data.get("product_code", "2GOOD"),
                    "visual_fact": data.get("visual_fact", ""),
                    "technical_fact": data.get("technical_fact", ""),
                    "marketing_claim": data.get("marketing_claim", ""),
                    "num_photos": num_photos,
                    "created_at": str(datetime.datetime.now())
                })
                return data
            else:
                print(f"Model {model_name} Error: {response.text}")
        except Exception as e:
            print(f"Error calling {model_name}: {e}")
            
    return None

def generate_content_from_text_prompt(text_prompt):
    """
    Generate 3 authentic content angles from a purely text prompt / custom idea.
    """
    memory = load_memory()
    recent_memory_str = json.dumps(memory[-5:], ensure_ascii=False) if memory else "Chưa có bài nào."

    # Pick dynamic archetypes to ensure 100% variety
    a1_title, a1_desc = random.choice(ANGLE_1_ARCHETYPES)
    a2_title, a2_desc = random.choice(ANGLE_2_ARCHETYPES)
    a3_title, a3_desc = random.choice(ANGLE_3_ARCHETYPES)

    system_prompt = f"""
Bạn là Chuyên gia Sáng tạo Nội dung & Bán hàng thực chiến của thương hiệu gia dụng 2GOOD (Nồi chiên hơi nước S200 dung tích 32L, S100, Nồi nấu chậm Sona i8...).

YÊU CẦU NỘI DUNG TỪ SẾP: "{text_prompt}"
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY (BẮT BUỘC TRÁNH TRÙNG LẶP):
{recent_memory_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 KNOWLEDGE BASE CỐT LÕI & ĐIỂM ĂN TIỀN TỪNG MODEL 2GOOD:

🔥 DÒNG NỒI CHIÊN HƠI NƯỚC 2GOOD S100 (20 LÍT - LỒNG ĐẢO 360 ĐỘ TỰ ĐỘNG & SUPERHEAT 115°C):
- Dung tích: 20 Lít rộng rãi (chuẩn cho gia đình 6-8 người, nướng gà nguyên con hoặc nấu cùng lúc 2-3 món trên các tầng khay).
- Công suất & Nhiệt độ: 1800W mạnh mẽ, dải nhiệt linh hoạt cực rộng từ 40°C đến 230°C.
- Chất liệu: Vỏ nhựa ABS cao cấp, cửa kính cách nhiệt 2 lớp chống bỏng an toàn. Lòng nồi và toàn bộ 8 phụ kiện đều làm từ 100% Inox 304 chuẩn y tế, không chống dính Teflon độc hại, cọ rửa búi cước sắt thoải mái.
- Kích thước & Điều khiển: 420 x 429 x 355 mm, màn hình cảm ứng LED kết hợp núm vặn trực quan.
- Đa chức năng 3 trong 1: Chiên không dầu + Hấp nhiệt + Chiên hơi nước kết hợp (giòn rụm bên ngoài, mọng ẩm ngọt nước bên trong, không khô xơ).
- Công nghệ hấp SuperHeat: Hạt sương siêu nhỏ nano (< 100nm) với nhiệt độ hơi nước lên tới 115°C, thẩm thấu cực nhanh, giữ trọn 99% vitamin và vị ngọt tự nhiên của rau củ, thịt cá.
- ĐẶC QUYỀN ĐỈNH CAO — LỒNG TỰ ĐẢO 360 ĐỘ: Tự động xoay đảo liên tục cho khoai tây chiên, rang lạc (đậu phộng), hạt điều, hạt dẻ chín đều vàng ruộm mọi góc mà không cần mở lò đứng lật dở!
- Chế độ ủ ấm & Lên men mở rộng: Nhiệt độ thấp ủ bột bánh mì (40°C), làm sữa chua (45°C), chưng yến (85°C) tiện dụng.
- Full bộ 8 phụ kiện Inox 304 kèm sẵn: Khay chiên/nướng, vỉ chiên/nướng, khay hấp, khay hứng dầu mỡ, lồng đảo 360 độ, dụng cụ nâng gắp, xiên quay rô-ti và ghim thực phẩm.

🔥 DÒNG NỒI CHIÊN HƠI NƯỚC 2GOOD S200 (32 LÍT - DUNG TÍCH CỰC ĐẠI & STEAM CLEAN):
- Dung tích cực đại: 32 Lít (khoang 100% Inox 304 nguyên khối), nướng vừa cả con gà 2-3kg hoặc mâm cỗ 3-4 món một lúc.
- Công nghệ phun sương siêu nhiệt Steam Active: Ngoài giòn xém thơm phức, trong giữ trọn nước ngọt mọng tự nhiên.
- Tự làm sạch bằng hơi nước (Steam Clean): Hơi sương siêu nhiệt làm mềm nhũn dầu mỡ bám dính, chỉ cần lau nhẹ 1 đường là sạch bóng.
- Gia nhiệt đối lưu 360 độ không cần lật trở. Vỏ thép phay xước Quiet Luxury sang trọng.

🔥 DÒNG NỒI NẤU CHẬM 2GOOD SONA i8:
- Công nghệ nấu cách thủy truyền nhiệt gián tiếp qua hơi nước, thố sứ tự nhiên cao cấp, giữ trọn vi chất dinh dưỡng, nấu cháo, chưng yến, hầm canh phân tầng.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 NGUYÊN TẮC ĐA DẠNG HÓA NỘI DUNG (TRÁNH 1 MÀU & TRÁNH LẶP Ý):
- Tuyệt đối KHÔNG bài nào cũng lặp đi lặp lại cùng một mô-típ hoặc cùng một lối mở bài quen thuộc. Bắt buộc bám sát ĐỊNH HƯỚNG SÁNG TẠO riêng biệt được chỉ định cho từng góc dưới đây để bài viết luôn tươi mới, tự nhiên và phong phú.
- Tránh trùng lặp tình huống và câu chuyện của các bài gần đây.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✍️ QUY TẮC XƯNG HÔ CHUẨN:
- Xưng "Em" - Gọi "Mọi người" HOẶC Xưng "Em" - Gọi "Các bác".
- Tuyệt đối CẤM: "các chị ơi", "các mẹ ơi", "mấy bà ơi", "hỡi ôi".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ĐỊNH HƯỚNG SÁNG TẠO ĐẶC BIỆT CHO LẦN NÀY (ĐẢM BẢO KHÔNG BỊ 1 MÀU):

👩‍👧 GÓC 1: BỮA CƠM GIA ĐÌNH / ĐỜI THƯỜNG (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Khai thác theo hướng: [{a1_title}]
Chi tiết định hướng: {a1_desc}
(Kèm đầy đủ emoji sinh động và 5-7 hashtag ở cuối bài).

🥗 GÓC 2: ĂN UỐNG LÀNH MẠNH, SỨC KHỎE & CHẤT LIỆU (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Khai thác theo hướng: [{a2_title}]
Chi tiết định hướng: {a2_desc}
(Kèm đầy đủ emoji và 5-7 hashtag ở cuối bài).

🛒 GÓC 3: ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC (Xưng 'Em' - Gọi 'Mọi người' hoặc 'Các bác')
👉 Khai thác theo hướng: [{a3_title}]
Chi tiết định hướng: {a3_desc}
(Kèm đầy đủ emoji và 5-7 hashtag ở cuối bài).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HÃY TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON CHUẨN:
{{
  "product_code": "Mã sản phẩm phù hợp (VD: 2GOOD S200 / S100)",
  "visual_fact": "Ý tưởng bài viết theo yêu cầu",
  "technical_fact": "Điểm kỹ thuật nhấn mạnh",
  "marketing_claim": "Thông điệp chính",
  "content_matrix": {{
    "me_bim_noi_tro": "Toàn bộ bài viết Góc 1 (Tiêu đề + Emoji + Thân bài tự nhiên theo định hướng + CTA + Hashtags)",
    "eat_clean_inox304": "Toàn bộ bài viết Góc 2 (Tiêu đề + Emoji + Thân bài Eat-clean/Sức khỏe theo định hướng + CTA + Hashtags)",
    "dai_ly_dan_da": "Toàn bộ bài viết Góc 3 (Tiêu đề + Emoji + Bài bán hàng uy tín theo định hướng + CTA + Hashtags)"
  }}
}}
"""
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "response_mime_type": "application/json"
        }
    }

    for model_name in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                
                try:
                    data = json.loads(raw_text, strict=False)
                except Exception:
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', lambda m: ' ' if m.group() in '\n\r\t' else '', raw_text)
                    try:
                        data = json.loads(cleaned, strict=False)
                    except Exception:
                        data = {
                            "product_code": "2GOOD",
                            "visual_fact": text_prompt,
                            "technical_fact": "Khoang Inox 304, công nghệ đối lưu hơi nước 360",
                            "marketing_claim": "Giòn rụm ngoài mọng nước trong",
                            "content_matrix": {
                                "me_bim_noi_tro": raw_text[:1000],
                                "eat_clean_inox304": raw_text[1000:2000] if len(raw_text) > 1000 else raw_text,
                                "dai_ly_dan_da": raw_text[2000:3000] if len(raw_text) > 2000 else raw_text
                            }
                        }
                
                # Sanitize content matrix to eliminate any residual forbidden cliches
                if "content_matrix" in data:
                    data["content_matrix"] = sanitize_content_matrix(data["content_matrix"])

                save_kb({
                    "product_code": data.get("product_code", "2GOOD"),
                    "visual_fact": text_prompt,
                    "technical_fact": data.get("technical_fact", ""),
                    "marketing_claim": data.get("marketing_claim", ""),
                    "num_photos": 0,
                    "created_at": str(datetime.datetime.now())
                })
                return data
        except Exception as e:
            print(f"Error calling {model_name} for text prompt: {e}")
            
    return None

