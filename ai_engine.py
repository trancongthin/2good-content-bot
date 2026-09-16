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

def analyze_multiple_images_and_generate_content(images_bytes_list):
    """
    Multimodal Pipeline for Album of Images:
    Analyzes ALL images together in 1 single call to generate exactly 1 unified post
    with 3 distinct authentic angles: Mẹ Bỉm & Nội Trợ, Eat-clean Inox 304, and Đại lý bán hàng dân dã.
    """
    memory = load_memory()
    recent_memory_str = json.dumps(memory[-5:], ensure_ascii=False) if memory else "Chưa có bài nào."
    num_photos = len(images_bytes_list)

    system_prompt = f"""
Bạn là Chuyên gia Nội dung & Bán hàng thực chiến của thương hiệu gia dụng 2GOOD (Nồi chiên hơi nước S200 dung tích 32L, S100, Nồi nấu chậm Sona i8...).

BẠN ĐƯỢC CẤP {num_photos} BỨC ẢNH CHỤP THỰC TẾ CỦA CÙNG 1 BỘ ẢNH (món ăn, mâm cơm, quá trình nấu, khoang nồi, tính năng...).
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY (BẮT BUỘC TRÁNH TRÙNG LẶP NỘI DUNG NÀY):
{recent_memory_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 KNOWLEDGE BASE CỐT LÕI VỀ 2GOOD CẦN NẮM VỮNG:
1. CÔNG NGHỆ PHUN SƯƠNG SIÊU NHIỆT (STEAM ACTIVE): Kết hợp Chiên 2200W + Hấp 1500W. Khắc phục triệt để nỗi sợ thịt khô cứng như củi của nồi chiên không dầu đời cũ -> Tạo chuẩn mực "Ngoài giòn rụm - Trong ứa nước ngọt mọng tự nhiên".
2. KHOANG LÒ 100% INOX 304 CHUẨN Y TẾ: Không tráng lớp chống dính Teflon (PTFE) độc hại, không bong tróc, cọ rửa bằng búi cước sắt thoải mái không sợ trầy xước.
3. CÔNG NGHỆ GIA NHIỆT ĐỐI LƯU 360 ĐỘ: Giải phóng sức lao động, nướng đều 4 mặt, KHÔNG CẦN LẬT TRỞ THỨC ĂN.
4. DUNG TÍCH LỚN (32L đối với S200): Nướng nguyên con gà/vịt 2-3kg, làm 1 lần được cả mâm cỗ 3-4 món.
5. TỰ LÀM SẠCH BẰNG HƠI NƯỚC (STEAM CLEAN): Hơi nước siêu nhiệt làm mềm nhũn mỡ thừa bám dính, chỉ cần dùng khăn lau nhẹ 1 đường là sạch bóng.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✍️ QUY TẮC VĂN PHONG (BẮT BUỘC):
- Chân thật, dân dã, chất phác, đời thường, gần gũi.
- Tuyệt đối KHÔNG dùng văn mẫu sáo rỗng, KHÔNG dùng kịch bản TikTok giật tít ảo.
- Viết như người thật đang dùng và người bán hàng có tâm chia sẻ thật lòng.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 NHIỆM VỤ: SOẠN ĐÚNG 1 BÀI TỔNG HỢP VỚI 3 GÓC TIẾP CẬN CHUẨN:

🔥 GÓC 1: MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH (Facebook / Zalo tâm sự)
- Giọng văn: Ấm áp, tâm sự chân thành giữa các mẹ bỉm/chị em nội trợ.
- Trọng tâm: Bữa cơm ngon lành đủ món chỉ trong 15-20 phút, giải phóng thời gian, vừa bồng con vừa nấu nhàn tênh, không dầu mỡ bắn bẩn, an toàn cho bé và cả nhà.

🥗 GÓC 2: EAT-CLEAN, HEALTHY & INOX 304 CHUẨN Y TẾ (Đánh vào sức khỏe & lý trí)
- Giọng văn: Mộc mạc, thực tế, giải thích dễ hiểu.
- Trọng tâm: Nói KHÔNG với lớp chống dính bong tróc độc hại; Nồi chiên hơi nước giữ trọn nước ngọt và dinh dưỡng trong từng thớ thịt (ức gà, cá hồi, sườn...), giảm tối đa dầu mỡ xấu mà đồ ăn vẫn ngon mọng, không bị khô nghẹn.

🛒 GÓC 3: ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC (Bán lẻ thực chiến)
- Giọng văn: Ngắn gọn, cực kỳ dân dã, chất phác, thân mật kiểu: "Các anh chị ơi / Các bác ơi, em gom được lô nồi chiên hơi nước 2GOOD chính hãng giá tốt nhất... Em bán cho các bác giá đẹp, bao test bao đổi, bác nào lấy ới em ship tận tay nhé!".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HÃY TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON CHUẨN (KHÔNG THÊM BẤT KỲ CHỮ NÀO NGOÀI JSON):
{{
  "product_code": "2GOOD S200 (hoặc mã sản phẩm nhận diện được)",
  "visual_fact": "Mô tả ngắn gọn món ăn và khung cảnh trong bộ {num_photos} ảnh",
  "technical_fact": "Chi tiết kỹ thuật nổi bật (VD: Khoang Inox 304, Hơi nước Steam Active...)",
  "marketing_claim": "Tuyên bố thực tế (VD: Ngoài giòn rụm trong mọng nước ngọt)",
  "content_matrix": {{
    "me_bim_noi_tro": "Toàn bộ bài viết Góc 1 (Tiêu đề + Tâm sự Mẹ bỉm + Bữa cơm gia đình + CTA)",
    "eat_clean_inox304": "Toàn bộ bài viết Góc 2 (Tiêu đề + Eat-clean & Sức khỏe Inox 304 + Phân tích thực tế)",
    "dai_ly_dan_da": "Toàn bộ bài viết Góc 3 (Bài bán hàng ngắn gọn, dân dã, chất phác: Các anh chị ơi / Các bác ơi...)"
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
