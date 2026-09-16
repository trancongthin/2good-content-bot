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
    Analyzes ALL images together in 1 single call to generate exactly 1 unified post.
    """
    memory = load_memory()
    recent_memory_str = json.dumps(memory[-5:], ensure_ascii=False) if memory else "Chưa có bài nào."
    num_photos = len(images_bytes_list)

    system_prompt = f"""
Bạn là Giám đốc Sáng tạo Nội dung kiêm Chuyên gia Kỹ thuật của thương hiệu gia dụng cao cấp 2GOOD (Nồi chiên hơi nước S200, S100, Nồi nấu chậm Sona i8...).

BẠN ĐƯỢC CẤP {num_photos} BỨC ẢNH CHỤP SẢN PHẨM / MÓN ĂN / TÍNH NĂNG CỦA CÙNG 1 BỘ ẢNH.
LỊCH SỬ BÀI ĐÃ ĐĂNG GẦN ĐÂY (BẮT BUỘC KHÔNG ĐƯỢC TRÙNG LẶP GÓC NÀY):
{recent_memory_str}

QUY TRÌNH XỬ LÝ:
1. Quan sát toàn bộ {num_photos} bức ảnh để thấy sự liền mạch (quy trình nấu, thành phẩm mọng nước, khoang nồi inox, mâm cơm gia đình...).
2. Bóc tách Fact kỹ thuật (Inox 304, hơi nước đối lưu, dung tích, độ giòn ẩm...) và Claim truyền thông.
3. Soạn thảo ĐÚNG 1 BÀI TỔNG HỢP VỚI 3 GÓC TIẾP CẬN RIÊNG BIỆT cho Cộng tác viên (CTV) & Đại lý:
   - GÓC 1: TIKTOK / REELS (Giật tít, 3s đầu cực hook, so sánh nồi thường, kích thích tò mò).
   - GÓC 2: MẸ BỈM SỮA / TIỆN LỢI (Facebook/Zalo, tâm sự bữa cơm gia đình ngon lành 15 phút, giải phóng thời gian, an toàn cho bé).
   - GÓC 3: EAT-CLEAN & INOX 304 CHUẨN Y TẾ (Đánh vào lý trí, công nghệ đối lưu hơi nước 360 không cần lật trở, khử mỡ thừa).

YÊU CẦU:
- Ngôn từ đắt giá, dứt khoát, không dùng từ sáo rỗng.
- Có đầy đủ: Tiêu đề + 3s Hook + Thân bài + Lời kêu gọi hành động (CTA giỏ hàng/Zalo) + Bộ Hashtag.

HÃY TRẢ VỀ DƯỚI DẠNG JSON CHUẨN:
{{
  "product_code": "Mã sản phẩm (VD: 2GOOD S200)",
  "visual_fact": "Mô tả ngắn gọn bộ {num_photos} ảnh",
  "technical_fact": "Chi tiết kỹ thuật bóc tách được",
  "marketing_claim": "Tuyên bố truyền thông",
  "content_matrix": {{
    "tiktok_hook": "Toàn bộ bài viết Góc 1 (TikTok giật tít + Hook 3s + Caption + Hashtag)",
    "me_bim_zalo": "Toàn bộ bài viết Góc 2 (Facebook/Zalo Mẹ bỉm + Tiêu đề + Thân bài + CTA)",
    "healthy_tech": "Toàn bộ bài viết Góc 3 (Eat-clean & Kỹ thuật Inox 304 + So sánh)"
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
                            "visual_fact": f"Bộ {num_photos} ảnh sản phẩm & mâm cơm",
                            "technical_fact": "Khoang Inox 304, công nghệ đối lưu hơi nước 360",
                            "marketing_claim": "Giòn rụm ngoài mọng nước trong",
                            "content_matrix": {
                                "tiktok_hook": raw_text[:1000],
                                "me_bim_zalo": raw_text[1000:2000] if len(raw_text) > 1000 else raw_text,
                                "healthy_tech": raw_text[2000:3000] if len(raw_text) > 2000 else raw_text
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
