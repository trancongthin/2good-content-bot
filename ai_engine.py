import json
import base64
import datetime
import requests
import re
from config import GEMINI_API_KEY, KB_FILE, MEMORY_FILE

MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]

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

    system_prompt = f"""
Bạn là Chuyên gia Sáng tạo Nội dung & Bán hàng thực chiến của thương hiệu gia dụng 2GOOD (Nồi chiên hơi nước S200 dung tích 32L, S100, Nồi nấu chậm Sona i8...).

BẠN ĐƯỢC CẤP {num_photos} HÌNH ẢNH / TƯ LIỆU THỰC TẾ CỦA CÙNG 1 BỘ TƯ LIỆU.{video_prompt}{custom_instruction_prompt}
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY (BẮT BUỘC TRÁNH TRÙNG LẶP NỘI DUNG NÀY):
{recent_memory_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 KNOWLEDGE BASE CỐT LÕI VỀ 2GOOD:
1. CÔNG NGHỆ PHUN SƯƠNG SIÊU NHIỆT (STEAM ACTIVE): Kết hợp Chiên 2200W + Hấp 1500W. Khắc phục triệt để nỗi sợ thịt khô cứng như củi của nồi chiên không dầu đời cũ -> Tạo chuẩn mực "Ngoài giòn rụm - Trong ứa nước ngọt mọng tự nhiên".
2. KHOANG LÒ 100% INOX 304 CHUẨN Y TẾ TOÀN PHẦN: Không tráng lớp chống dính Teflon (PTFE) độc hại, không lo bong tróc, cọ rửa bằng búi cước sắt thoải mái không sợ trầy xước.
3. CÔNG NGHỆ GIA NHIỆT ĐỐI LƯU 360 ĐỘ: Giải phóng sức lao động, nướng đều 4 mặt, KHÔNG CẦN LẬT TRỞ THỨC ĂN.
4. DUNG TÍCH LỚN (32L đối với S200): Nướng vừa nguyên 2 con gà 2-3kg cùng lúc hoặc cả mâm cỗ 3-4 món một mẻ.
5. TỰ LÀM SẠCH BẰNG HƠI NƯỚC (STEAM CLEAN): Hơi nước làm mềm nhũn dầu mỡ bám dính, chỉ cần dùng khăn lau nhẹ 1 đường là sạch bong.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✍️ QUY TẮC BÀI ĐĂNG (BẮT BUỘC):
1. ICON / EMOJI SINH ĐỘNG: Điểm xuyết các icon/emoji phù hợp tự nhiên (🍗, 🥩, 🥦, 👩‍🍳, ✨, ⏰, ❤️, 💯, 🌿, 🛒...) để ngắt ý, làm nổi bật điểm nhấn, giúp bài viết trên Facebook/Zalo bắt mắt, cuốn hút và dễ đọc.
2. BỘ HASHTAGS CHUẨN: Ở cuối MỖI bài viết, BẮT BUỘC có 5–7 hashtag liên quan đến sản phẩm, món ăn, thương hiệu 2GOOD (Ví dụ: #2GOOD #NoiChienHoiNuoc2GOOD #2GOOD_S200 #MonNgonMoiNgay #Inox304 #MeBimNoiTro #EatClean).
3. VĂN PHONG TỰ NHIÊN, CHÂN THẬT: Giọng văn người thật việc thật, mộc mạc, gần gũi, chia sẻ từ trải nghiệm thực tế, tuyệt đối KHÔNG viết văn mẫu khô khan hay quảng cáo lộ liễu.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 SOẠN ĐÚNG 1 BÀI TỔNG HỢP VỚI 3 GÓC TIẾP CẬN (TUYỆT ĐỐI KHÔNG DÙNG GIỌNG KỊCH HAY VĂN MẪU):

👩‍👧 GÓC 1: TÂM SỰ NỘI TRỢ / MẸ BỈM SỮA (Gợi mở, khiêm tốn, hỏi han hoặc rủ rê chị em làm thử)
- Văn phong: Cực kỳ tự nhiên, mộc mạc, như một người mẹ/người vợ chia sẻ thật lòng trên trang cá nhân hoặc hội nhóm.
- Mở đầu bằng các câu hỏi tương tác hoặc gợi ý nhẹ nhàng:
  • "Các chị cho em hỏi chút..."
  • "Không biết có chị nào giống em khoản này không..."
  • "Hôm nay rảnh rảnh làm món này ăn cũng cuốn phết các chị ạ, con nhà em ăn tì tì hết sạch đĩa luôn, xứng đáng để mọi người làm thử đấy..."
- Nội dung chia sẻ: Kể chuyện thực tế, không dùng từ khoa trương (cấm tiệt "Hỡi ôi mấy bà", "chân ái cuộc đời", "nhàn tênh như đi chơi"). Kể chuyện con cái ăn khen ngon, thịt mềm mọng nước không bị khô khốc như nồi cũ, rửa nồi Inox 304 bật hơi nước lau nhẹ là xong. Điểm xuyết emoji nhẹ nhàng và 5-7 hashtag liên quan ở cuối.

🥗 GÓC 2: CHỊ EM ĂN UỐNG LÀNH MẠNH, GIỮ DÁNG & HEALTHY (Chia sẻ kinh nghiệm thực tế, hỏi ý kiến chị em)
- Văn phong: Nhẹ nhàng, thực tế, như hai người bạn cùng gu ăn uống rỉ tai nhau.
- Mở đầu tự nhiên:
  • "Chị em cảm thấy vấn đề này như thế nào..."
  • "Có chị nào đang ăn Eat-clean mà ngán ức gà hay cá hồi nướng bị khô xác như em hồi trước không?..."
- Nội dung chia sẻ: Chia sẻ cách nướng kết hợp hơi nước giúp thịt bên trong mọng nước ngọt tự nhiên mà không cần giọt dầu nào; tâm sự thật lòng về nỗi lo lớp chống dính Teflon đen bong tróc ở nồi cũ, đổi sang khoang Inox 304 chuẩn y tế cọ rửa búi sắt thoải mái thấy an tâm hơn hẳn cho sức khỏe cả nhà. Điểm xuyết emoji và 5-7 hashtag ở cuối.

🛒 GÓC 3: ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC (Bán lẻ thực chiến - Giữ nguyên phong độ cực tốt)
- Giọng văn: Cực kỳ dân dã, chất phác, xởi lởi: "Em chào các bác / Các anh chị em ơi, hôm nay em gom được lô nồi chiên hơi nước 2GOOD chính hãng giá siêu hời... Em bán giá đẹp, bao test bao đổi 1-1 cho các bác yên tâm, bác nào lấy ới em ship tận tay nhé!".
- Nếu cụm bài có video: Nhắc khéo CTV tải clip hơi nước bốc lên / thức ăn nướng xèo xèo về up TikTok / Reels để hút khách và chốt đơn nhanh.
- Đầy đủ icon emoji và 5-7 hashtag ở cuối.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HÃY TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON CHUẨN (KHÔNG THÊM BẤT KỲ CHỮ NÀO NGOÀI JSON):
{{
  "product_code": "2GOOD S200 (hoặc mã sản phẩm nhận diện được)",
  "visual_fact": "Mô tả ngắn gọn món ăn và khung cảnh trong bộ {num_photos} ảnh",
  "technical_fact": "Chi tiết kỹ thuật nổi bật (VD: Khoang Inox 304, Hơi nước Steam Active...)",
  "marketing_claim": "Tuyên bố thực tế (VD: Ngoài giòn rụm trong mọng nước ngọt)",
  "content_matrix": {{
    "me_bim_noi_tro": "Toàn bộ bài viết Góc 1 (Tiêu đề + Emoji + Thân bài tâm sự chị em cực kỳ tự nhiên + CTA + Hashtags)",
    "eat_clean_inox304": "Toàn bộ bài viết Góc 2 (Tiêu đề + Emoji + Thân bài Eat-clean mọng nước Inox 304 + CTA + Hashtags)",
    "dai_ly_dan_da": "Toàn bộ bài viết Góc 3 (Tiêu đề + Emoji + Bài bán hàng dân dã, chất phác + CTA + Hashtags)"
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
            "temperature": 0.7,
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

    system_prompt = f"""
Bạn là Chuyên gia Sáng tạo Nội dung & Bán hàng thực chiến của thương hiệu gia dụng 2GOOD (Nồi chiên hơi nước S200 32L, S100, Nồi nấu chậm Sona i8...).

YÊU CẦU NỘI DUNG TỪ SẾP: "{text_prompt}"
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY:
{recent_memory_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 KNOWLEDGE BASE CỐT LÕI VỀ 2GOOD:
1. CÔNG NGHỆ HƠI NƯỚC STEAM ACTIVE: Kết hợp Chiên + Hấp bù ẩm -> Ngoài giòn rụm, trong mọng nước ngọt tự nhiên, không bị khô xác.
2. KHOANG LÒ 100% INOX 304 CHUẨN Y TẾ TOÀN PHẦN: Không phủ chống dính Teflon độc hại, cọ rửa chà cước sắt thoải mái không sợ trầy xước.
3. ĐỐI LƯU 360 ĐỘ: Không cần lật trở thức ăn, giải phóng sức lao động.
4. TỰ LÀM SẠCH STEAM CLEAN: Hơi nước siêu nhiệt làm mềm dầu mỡ bám dính, lau nhẹ 1 đường là sạch bóng.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✍️ QUY TẮC BÀI ĐĂNG (BẮT BUỘC):
1. ICON / EMOJI SINH ĐỘNG: Điểm xuyết emoji phù hợp tự nhiên (🍗, 🥦, 👩‍🍳, ✨, ⏰, ❤️, 💯, 🌿, 🛒...).
2. BỘ HASHTAGS CHUẨN: Ở cuối MỖI bài viết, BẮT BUỘC có 5–7 hashtag liên quan (#2GOOD #NoiChienHoiNuoc2GOOD #2GOOD_S200 #MonNgonMoiNgay #Inox304 #MeBimNoiTro).
3. VĂN PHONG CHÂN THẬT, DÂN DÃ, CHẤT PHÁC: Tuyệt đối không viết văn mẫu khô khan.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 SOẠN 01 BÀI TỔNG HỢP VỚI 3 GÓC TIẾP CẬN BÁM SÁT YÊU CẦU (TUYỆT ĐỐI KHÔNG DÙNG TỪ NGỮ KỊCH CỠM HOẶC VĂN MẪU):
👩‍👧 GÓC 1: TÂM SỰ NỘI TRỢ / MẸ BỈM SỮA (Gợi mở khiêm tốn: "Các chị cho em hỏi...", "Hôm nay rảnh rảnh làm món này cũng ngon đấy, con nhà em ăn tì tì hết sạch đĩa luôn, xứng đáng để mọi người làm thử đấy...". Kể chuyện con cái ăn khen ngon, thịt mềm mọng nước không khô khốc như nồi cũ, khoang Inox 304 bật hơi nước lau nhẹ là sạch).
🥗 GÓC 2: HỘI CHỊ EM ĂN UỐNG LÀNH MẠNH, HEALTHY (Hỏi han & chia sẻ mẹo: "Chị em cảm thấy vấn đề này như thế nào...", "Có chị nào ăn Eat-clean mà sợ ức gà khô xác nuốt nghẹn rát họng như em không...". Kể cách nướng hơi nước mọng thịt không cần giọt dầu nào, an tâm vì khoang Inox 304 không sợ lớp chống dính Teflon độc hại).
🛒 GÓC 3: ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC (Bán lẻ thực chiến: "Các bác ơi / Các anh chị ơi, hôm nay em gom được lô chính hãng giá hời... Bao test 1-1, bác nào lấy ới em ship tận tay nhé!").

HÃY TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON CHUẨN:
{{
  "product_code": "Mã sản phẩm phù hợp (VD: 2GOOD S200 / S100)",
  "visual_fact": "Ý tưởng bài viết theo yêu cầu",
  "technical_fact": "Điểm kỹ thuật nhấn mạnh",
  "marketing_claim": "Thông điệp chính",
  "content_matrix": {{
    "me_bim_noi_tro": "Toàn bộ bài viết Góc 1 (Tiêu đề + Emoji + Thân bài tâm sự chị em cực kỳ tự nhiên + CTA + Hashtags)",
    "eat_clean_inox304": "Toàn bộ bài viết Góc 2 (Tiêu đề + Emoji + Thân bài Eat-clean mọng nước Inox 304 + CTA + Hashtags)",
    "dai_ly_dan_da": "Toàn bộ bài viết Góc 3 (Tiêu đề + Emoji + Bài bán hàng dân dã, chất phác + CTA + Hashtags)"
  }}
}}
"""
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
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
