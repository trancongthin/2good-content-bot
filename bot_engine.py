import json
import re
import requests
from pathlib import Path
from config import DATA_DIR, GEMINI_API_KEY
from ai_engine import MODELS

PRODUCTS_FILE = DATA_DIR / "products.json"
SCRIPTS_FILE = DATA_DIR / "scripts.json"
POLICIES_FILE = DATA_DIR / "policies.json"

def load_json_file(file_path: Path):
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    return {}

def detect_intent(query: str):
    q = query.lower()
    
    # 1. Objection handling
    objection_triggers = [
        "chê", "đắt", "mắc", "cao quá", "rẻ hơn", "to quá", "cồng kềnh", 
        "chiếm chỗ", "khó rửa", "ngại rửa", "khó vệ sinh", "dầu mỡ", 
        "chống dính", "ung thư", "ồn", "tiếng ồn", "chua", "chua sữa", "so sánh"
    ]
    if any(t in q for t in objection_triggers):
        return "OBJECTION"
    
    # 2. Policy & Warranty
    policy_triggers = [
        "bảo hành", "đổi trả", "1 đổi 1", "lỗi", "sửa chữa", "kiểm tra hàng", 
        "đồng kiểm", "ship", "vận chuyển", "giao hàng", "chính sách", "trả hàng"
    ]
    if any(t in q for t in policy_triggers):
        return "POLICY"
    
    # 3. Product info
    product_triggers = [
        "s200", "s100", "sona", "i8", "thông số", "công suất", "dung tích", 
        "phụ kiện", "kích thước", "bao nhiêu lít", "nồi chiên", "máy sữa hạt", "mấy lít"
    ]
    if any(t in q for t in product_triggers):
        return "PRODUCT_INFO"
        
    return "GENERAL"

def get_ground_truth_context(query: str, intent: str) -> str:
    products = load_json_file(PRODUCTS_FILE)
    scripts = load_json_file(SCRIPTS_FILE)
    policies = load_json_file(POLICIES_FILE)
    
    context_blocks = []
    
    # Check for specific product
    q = query.lower()
    target_products = []
    if "s200" in q:
        target_products.append("S200")
    if "s100" in q:
        target_products.append("S100")
    if "sona" in q or "i8" in q or "sữa hạt" in q:
        target_products.append("Sona_i8")
    if not target_products:
        # Default include all main products summary
        target_products = list(products.keys())
        
    for p_key in target_products:
        if p_key in products:
            p_data = products[p_key]
            context_blocks.append(f"--- THÔNG TIN SẢN PHẨM: {p_data.get('name')} ---\n" + json.dumps(p_data, ensure_ascii=False, indent=2))
            
    if intent in ["OBJECTION", "GENERAL"]:
        context_blocks.append("--- KỊCH BẢN XỬ LÝ TỪ CHỐI CHUẨN ---\n" + json.dumps(scripts.get("objections", []), ensure_ascii=False, indent=2))
        
    if intent in ["POLICY", "GENERAL"]:
        context_blocks.append("--- CHÍNH SÁCH BẢO HÀNH & HẬU MÃI 2GOOD ---\n" + json.dumps(policies, ensure_ascii=False, indent=2))
        
    return "\n\n".join(context_blocks)

def generate_ctv_advice(query: str) -> str:
    """
    Core RAG function: Takes CTV query, grounds in JSON facts, and generates tailored advice via Gemini.
    """
    intent = detect_intent(query)
    ground_truth = get_ground_truth_context(query, intent)
    
    system_prompt = f"""Bạn là Trợ lý bán hàng & Cố vấn chốt sale cấp cao của thương hiệu gia dụng 2GOOD dành riêng cho Cộng Tác Viên (CTV).

DƯỚI ĐÂY LÀ DỮ LIỆU SỰ THẬT (GROUND TRUTH) CHÍNH XÁC VỀ SẢN PHẨM & CHÍNH SÁCH CÔNG TY:
===
{ground_truth}
===

CÂU HỎI / TÌNH HUỐNG TỪ CTV:
"{query}"

YÊU CẦU TRẢ LỜI CHO CTV (Định dạng văn bản rõ ràng, chuyên nghiệp, súc tích, dùng ít icon ~3 icon):
1. Tuyệt đối tuân thủ sự thật trong Ground Truth (về Inox 304, dung tích, công suất, bảo hành, v.v.). Không tự bịa thông số.
2. Cung cấp câu trả lời theo đúng cấu trúc 3 phần:

🎯 **Điểm mấu chốt (Insight):** (1-2 câu ngắn giải thích tâm lý thật sự của khách)
💬 **Câu trả lời mẫu gửi khách:** (Lời thoại tự nhiên, lịch thiệp, tôn trọng khách, xưng hô 'Dạ em chào anh/chị' hoặc 'Dạ em hiểu...', làm nổi bật giá trị cốt lõi của 2GOOD, để CTV chỉ việc copy gửi luôn)
💡 **Mẹo thực chiến cho CTV:** (1-2 lưu ý ngắn: nên nhấn mạnh điểm nào, tránh tranh luận hay dìm đối thủ thô thiển)

Hãy viết câu trả lời xuất sắc, chân thành và mang tính thuyết phục cao!"""

    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }

    for model_name in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                return raw_text
            else:
                print(f"Model {model_name} HTTP {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Model {model_name} failed in bot_engine: {e}")
            continue
            
    # Fallback response if all AI models fail
    return """Dạ em đang gặp chút gián đoạn kết nối mạng AI. Nhưng nguyên tắc quan trọng khi tư vấn:
1. Luôn đồng cảm với khách, không tranh cãi về giá hay kích thước.
2. Nhấn mạnh 2GOOD dùng 100% Inox 304 chuẩn y tế an toàn trọn đời (không lo bong tróc độc hại như lớp chống dính nồi rẻ tiền).
3. Khách được kiểm tra hàng (đồng kiểm) trước khi thanh toán và lỗi 1 đổi 1 trong 7 ngày đầu!"""
