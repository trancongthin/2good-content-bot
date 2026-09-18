import json
import re
import requests
from pathlib import Path
from config import DATA_DIR, GEMINI_API_KEY
from ai_engine import get_active_models

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
    
    # 1. Objection handling, pricing & comparisons
    objection_triggers = [
        "chê", "đắt", "mắc", "cao quá", "rẻ hơn", "to quá", "cồng kềnh", 
        "chiếm chỗ", "khó rửa", "ngại rửa", "khó vệ sinh", "dầu mỡ", 
        "chống dính", "ung thư", "ồn", "tiếng ồn", "chua", "chua sữa", "so sánh",
        "lồng đảo", "lồng tự đảo", "quay", "đảo", "tapuho", "olivo", "kalite", "lumias", "20l", "20 lít", "hơn gì",
        "giá", "nhiêu tiền", "bao nhiêu tiền", "giá cả", "báo giá", "giá bn", "16l", "15l", "elmich", "panasonic", "kuchen", "chức năng", "menu", "đối thủ"
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
            
    # Always provide objections & battle scripts for comprehensive advice
    context_blocks.append("--- KỊCH BẢN XỬ LÝ TỪ CHỐI, BÁO GIÁ & SO SÁNH THỊ TRƯỜNG CHUẨN ---\n" + json.dumps(scripts.get("objections", []), ensure_ascii=False, indent=2))
        
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
1. BÁO GIÁ VÀ BẢO HÀNH CHÍNH XÁC:
   - 2GOOD S200 (Flagship 32L): 8.900.000 VNĐ (8tr900k) — Bảo hành chính hãng 3 NĂM (36 tháng).
   - 2GOOD S100 (Đa năng 20L có lồng đảo): 5.290.000 VNĐ (5tr290k) — Bảo hành chính hãng 1 NĂM (12 tháng).
   - 2GOOD Sona i8 (Máy làm sữa hạt tự rửa): Bảo hành chính hãng 1 NĂM (12 tháng).
2. TƯ DUY SO SÁNH THỊ TRƯỜNG (BATTLE MINDSET TỪ BẢN KHẢO SÁT 2026):
   - Phân khúc 16L vs 20L: Các nồi 15-16L trên thị trường (Elmich, Tapuho 16L, Olivo 16L) giá từ 5tr2 - 6tr (ngang ngửa S100 20L 5tr290k), nhưng khoang chật bí nhiệt và chỉ 1 nguồn nhiệt. Khách chọn 2GOOD S100 được dung tích 20L nướng gà nguyên con 2.5kg, 2 nguồn nhiệt mâm thủy nhiệt và lồng đảo độc quyền.
   - S200 là Flagship ĐỘC TÔN: Dung tích 32L cực đại (các nồi khác chỉ 16-20L), công suất 2200W nướng + 1500W hấp, khoang 100% Inox 304 nguyên khối nướng 2 gà cùng lúc hoặc cá to, trục quay Roti tải lớn 2-3kg. ĐẶC BIỆT: Bảo hành 3 năm (36 tháng) duy nhất trên thị trường!
   - Chức năng / Menu cài sẵn: 40, 70 hay 128 chức năng thực chất chỉ là phím tắt lưu sẵn thời gian/nhiệt độ. Nấu thực tế thịt dày mỏng khác nhau không ai dùng menu cài sẵn mà tự chỉnh. Cốt lõi chỉ có 3 cơ chế: Chiên - Hấp - Chiên hơi nước.
   - Khen/chê chân thật: Thừa nhận ngoại hình 2GOOD thiết kế cơ bản, không màu mè sặc sỡ như các mẫu mới ra, nhưng bù lại là sự lựa chọn an toàn nhất, bền bỉ nhất, ít lỗi vặt và giá trị thực dụng cao nhất.
3. Cung cấp câu trả lời theo đúng cấu trúc 3 phần:

🎯 **Điểm mấu chốt (Insight):** (1-2 câu ngắn giải thích tâm lý thật sự của khách)
💬 **Câu trả lời mẫu gửi khách:** (Lời thoại tự nhiên, lịch thiệp, tôn trọng khách, xưng hô 'Dạ em chào anh/chị' hoặc 'Dạ em hiểu...', làm nổi bật giá trị cốt lõi của 2GOOD, để CTV chỉ việc copy gửi luôn)
💡 **Mẹo thực chiến cho CTV:** (1-2 lưu ý ngắn: nên nhấn mạnh điểm nào, hướng khách sang dòng phù hợp ngân sách)

Hãy viết câu trả lời xuất sắc, chân thành và mang tính thuyết phục cao!"""

    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }

    models_to_try = list(get_active_models())
    for attempt in range(2):
        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            try:
                response = requests.post(url, json=payload, timeout=25)
                if response.status_code == 200:
                    result = response.json()
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return raw_text
                else:
                    print(f"Model {model_name} HTTP {response.status_code}: {response.text[:100]}")
            except Exception as e:
                print(f"Model {model_name} failed in bot_engine: {e}")
                continue

        if attempt == 0:
            models_to_try = get_active_models(force_refresh=True)
            
    # Fallback response if all AI models fail
    return """Dạ em đang gặp chút gián đoạn kết nối mạng AI. Nhưng nguyên tắc quan trọng khi tư vấn:
1. Luôn đồng cảm với khách, không tranh cãi về giá hay kích thước.
2. Nhấn mạnh 2GOOD dùng 100% Inox 304 chuẩn y tế an toàn trọn đời (không lo bong tróc độc hại như lớp chống dính nồi rẻ tiền).
3. Khách được kiểm tra hàng (đồng kiểm) trước khi thanh toán và lỗi 1 đổi 1 trong 7 ngày đầu!"""
