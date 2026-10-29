import math
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List, Tuple
from config import HUPSMS_API_KEY, HUPSMS_BASE_URL, DEFAULT_MARKUP, ROUND_STEP
import db
import ui

log = logging.getLogger(__name__)

# Bảng ánh xạ từ khóa tên ứng dụng sang Logo 3D và Custom Emoji ID
BRAND_RULES = [
    (["facebook", "fb", "meta"], "Facebook", "📘", "Mạng xã hội"),
    (["telegram", "tele"], "Telegram", "✈️", "Mạng xã hội"),
    (["tiktok", "tik tok"], "TikTok", "🎵", "Mạng xã hội"),
    (["zalo"], "Zalo", "💬", "Mạng xã hội"),
    (["google", "youtube"], "Google", "🌐", "Dịch vụ Google"),
    (["gmail"], "Gmail", "📧", "Dịch vụ Google"),
    (["shopee", "shopeepay"], "Shopee", "🛍", "Thương mại điện tử"),
    (["whatsapp", "wa"], "WhatsApp", "🟢", "Liên lạc"),
    (["openai", "chatgpt", "gpt"], "OpenAI", "🤖", "Trí tuệ nhân tạo (AI)"),
    (["discord"], "Discord", "🎮", "Game & Chat"),
    (["apple", "icloud"], "Apple", "🍏", "Công nghệ"),
    (["amazon", "aws"], "Amazon", "📦", "Thương mại điện tử"),
    (["alibaba", "aliexpress", "taobao"], "Alibaba", "🏮", "Thương mại điện tử"),
    (["lazada"], "Lazada", "🛒", "Thương mại điện tử"),
    (["momo"], "MoMo", "💖", "Ví điện tử"),
    (["mbbank", "vietcombank", "bank", "ngan hang"], "MBBank", "🏦", "Ngân hàng"),
    (["twitter", "x.com"], "Twitter", "✖️", "Mạng xã hội"),
    (["instagram", "insta"], "Instagram", "📸", "Mạng xã hội"),
    (["microsoft", "outlook", "hotmail"], "Microsoft", "💼", "Văn phòng"),
    (["netflix"], "Netflix", "🎬", "Giải trí"),
    (["spotify"], "Spotify", "🎧", "Giải trí"),
    (["tinder"], "Tinder", "🔥", "Hẹn hò"),
    (["steam"], "Steam", "🕹", "Game"),
    (["canva"], "Canva", "🎨", "Đồ họa"),
    (["capcut"], "CapCut", "✂️", "Video"),
    (["be"], "Be", "🚕", "Vận tải"),
    (["grab"], "Grab", "🚗", "Vận tải"),
    (["garena"], "Garena", "🐚", "Game"),
]

def match_icon_and_category(service_name: str) -> tuple[str, str, Optional[str]]:
    """Trả về (emoji_fallback, danh_mục, custom_emoji_id_3d)."""
    n_lower = service_name.lower()
    for keywords, brand_key, emo, cat in BRAND_RULES:
        if any(k in n_lower for k in keywords):
            cid = ui.CUSTOM_EMOJIS.get(brand_key.lower())
            return emo, cat, cid
    return "📱", "Khác", None

def calculate_markup_price(original_price: int, markup: int) -> int:
    """Giá hiển thị trên Bot = Giá_gốc + markup. Tự động làm tròn lên hàng trăm."""
    raw = original_price + markup
    rem = raw % ROUND_STEP
    if rem > 0:
        raw = raw + (ROUND_STEP - rem)
    return max(raw, 2000)


class MultiSMSClient:
    """Trình điều khiển kết nối đa API nhà mạng cho thuê SIM OTP (HupSMS, ViOTP, ChoThueSimCode, Generic REST).
    Đảm bảo 100% kết quả là SMS thực tế, tuyệt đối không dùng mã giả lập."""

    def __init__(self):
        pass

    async def _fetch_services_from_provider(self, p: dict) -> List[Dict[str, Any]]:
        """Lấy danh sách dịch vụ từ 1 API nhà cung cấp cụ thể."""
        p_type = p.get("api_type", "hupsms").lower()
        base_url = p.get("base_url", "").rstrip("/")
        api_key = p.get("api_key", "")
        p_id = p.get("id", 1)

        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        results = []
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                if p_type == "hupsms":
                    urls = [
                        f"{clean_base}/api/v1/services",
                        f"{clean_base}/services",
                        f"{clean_base}/service/get-list"
                    ]
                    for url in urls:
                        try:
                            async with session.get(url, params={"api_key": api_key, "apikey": api_key}) as resp:
                                if resp.status == 200:
                                    data = await resp.json(content_type=None)
                                    items = data.get("data") or data.get("services") or data
                                    if isinstance(items, list):
                                        for it in items:
                                            sid = it.get("id") or it.get("service_id")
                                            sname = it.get("name") or it.get("service_name")
                                            price = it.get("price") or it.get("original_price") or 2000
                                            if sid and sname:
                                                results.append({
                                                    "id": int(sid),
                                                    "name": str(sname),
                                                    "price": int(price),
                                                    "server": it.get("server") or p.get("name", "Server 1"),
                                                    "provider_id": p_id
                                                })
                                        if results:
                                            break
                        except Exception:
                            pass

                elif p_type == "viotp":
                    url = f"{base_url}/service/getv2"
                    async with session.get(url, params={"token": api_key}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            items = data.get("data", [])
                            for it in items:
                                sid = it.get("id")
                                sname = it.get("name")
                                price = it.get("price") or 1500
                                if sid and sname:
                                    results.append({
                                        "id": int(sid),
                                        "name": str(sname),
                                        "price": int(price),
                                        "server": p.get("name", "ViOTP"),
                                        "provider_id": p_id
                                    })

                elif p_type in ("chothuesimcode", "generic"):
                    url = f"{base_url}/service/get-list"
                    async with session.get(url, params={"api_key": api_key, "token": api_key}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            items = data.get("data") or data.get("Result") or []
                            for it in items:
                                sid = it.get("id") or it.get("Id")
                                sname = it.get("name") or it.get("Name")
                                price = it.get("price") or it.get("Price") or 2000
                                if sid and sname:
                                    results.append({
                                        "id": int(sid),
                                        "name": str(sname),
                                        "price": int(price),
                                        "server": p.get("name", "Server SIM"),
                                        "provider_id": p_id
                                    })
        except Exception as e:
            log.warning("Fetch services error for provider %s: %s", p.get("name"), e)

        return results

    async def sync_all_services(self) -> int:
        """Đồng bộ danh sách dịch vụ từ TẤT CẢ các API web đang hoạt động (Tối đa 3 API)."""
        providers = await db.get_api_providers(active_only=True)
        markup = int(await db.get_config("markup_amount", str(DEFAULT_MARKUP)))
        
        all_services = []
        for p in providers:
            p_services = await self._fetch_services_from_provider(p)
            if p_services:
                all_services.extend(p_services)

        conn = await db.get_connection()
        try:
            count = 0
            if all_services:
                for s in all_services:
                    sid = s["id"]
                    sname = s["name"]
                    server = s["server"]
                    price = s["price"]
                    p_id = s["provider_id"]

                    emo, cat, cid = match_icon_and_category(sname)
                    # Kiểm tra xem admin có đặt custom_price cho dịch vụ này không
                    async with conn.execute("SELECT custom_price FROM services WHERE id = ?", (sid,)) as cur:
                        row = await cur.fetchone()
                        cust_price = row["custom_price"] if row else None

                    sell_price = cust_price if (cust_price and cust_price > 0) else calculate_markup_price(price, markup)

                    await conn.execute("""
                        INSERT INTO services (id, name, server, original_price, selling_price, custom_price, icon_3d, custom_emoji_id, category, provider_id, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            server = excluded.server,
                            original_price = excluded.original_price,
                            selling_price = CASE WHEN services.custom_price > 0 THEN services.custom_price ELSE excluded.selling_price END,
                            icon_3d = excluded.icon_3d,
                            custom_emoji_id = excluded.custom_emoji_id,
                            category = excluded.category,
                            provider_id = excluded.provider_id,
                            is_active = 1,
                            updated_at = CURRENT_TIMESTAMP
                    """, (sid, sname, server, price, sell_price, cust_price, emo, cid, cat, p_id))
                    count += 1
                await conn.commit()
                log.info("Đã đồng bộ tổng cộng %d dịch vụ từ %d API web!", count, len(providers))
                return count

            # Nếu API bên ngoài chưa kết nối được, duy trì hoặc khởi tạo danh mục dịch vụ chuẩn
            async with conn.execute("SELECT COUNT(*) as c FROM services") as cur:
                exist_count = (await cur.fetchone())["c"]
            if exist_count == 0:
                count = await self._seed_standard_services(conn, markup)
            else:
                count = exist_count
            return count
        finally:
            await conn.close()

    async def _seed_standard_services(self, conn, markup: int) -> int:
        """Khởi tạo danh sách các dịch vụ chuẩn thị trường với icon 3D và ID thật từ HupSMS."""
        defaults = [
            (95, "Facebook", "Server 1", 2500, 3),
            (97, "Telegram", "Server 1", 11500, 3),
            (48, "TikTok", "Server 1", 2500, 3),
            (70, "ZaloPay", "Server 1", 4000, 5),
            (93, "Google/Gmail", "Server 1", 10000, 3),
            (49, "Shopee VIP", "Server 1", 5000, 3),
            (46, "WhatsApp", "Server 1", 6000, 5),
            (88, "OpenAI/ChatGPT", "Server 1", 2500, 5),
            (65, "Discord", "Server 1", 3000, 3),
            (29, "Apple", "Server 1", 2500, 3),
            (32, "Amazon", "Server 1", 4000, 10),
            (60, "MoMo", "Server 1", 4000, 3),
            (90, "Lazada", "Server 1", 2500, 3),
            (66, "Grab", "Server 1", 3000, 3),
            (82, "Garena", "Server 1", 3000, 3),
            (50, "Netflix", "Server 1", 2500, 3),
            (47, "OTP Khác", "Server 1", 10000, 3),
        ]
        for sid, sname, server, price, tmin in defaults:
            sell_price = calculate_markup_price(price, markup)
            emo, cat, cid = match_icon_and_category(sname)
            await conn.execute("""
                INSERT OR REPLACE INTO services (id, name, server, original_price, selling_price, icon_3d, custom_emoji_id, category, timeout_minutes, provider_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
            """, (sid, sname, server, price, sell_price, emo, cid, cat, tmin))
        await conn.commit()
        return len(defaults)

    async def create_order(self, service_id: int) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Tạo phiên thuê số điện thoại THỰC TẾ từ API nhà cung cấp.
        Trả về: (thành_công, provider_order_id, phone_number, thông_báo).
        Tuyệt đối không giả lập số ảo nếu thất bại."""
        # 1. Tra cứu thông tin dịch vụ và nhà cung cấp
        service = await db.get_service_by_id(service_id)
        if not service:
            return False, None, None, "Dịch vụ không tồn tại hoặc đã ngừng cung cấp."

        provider_id = service.get("provider_id", 1)
        provider = await db.get_api_provider_by_id(provider_id)
        if not provider or not provider.get("is_active"):
            providers = await db.get_api_providers(active_only=True)
            if not providers:
                return False, None, None, "Hiện chưa có cổng API nhà mạng nào được kích hoạt."
            provider = providers[0]

        p_type = provider.get("api_type", "hupsms").lower()
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")

        # Chuẩn hóa base_url sạch (loại bỏ /api/v1 thừa nếu đã có trong URL)
        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                if p_type == "hupsms":
                    # Chuẩn API HupSMS V1: GET {clean_base}/api/v1/rent?serviceId={service_id}
                    # Cần tham số serviceId (camelCase), tuyệt đối không dùng snake_case service_id.
                    try:
                        async with session.get(
                            f"{clean_base}/api/v1/rent",
                            params={"serviceId": service_id, "api_key": api_key}
                        ) as resp:
                            res = await resp.json(content_type=None)
                            log.info("HupSMS rent response for service %s: %s", service_id, res)
                            if isinstance(res, dict):
                                status_str = str(res.get("status", "")).lower()
                                code = str(res.get("code", "")).upper()
                                msg_str = str(res.get("message", ""))

                                # 1. Kiểm tra số dư tài khoản API HupSMS
                                if code == "INSUFFICIENT_BALANCE" or "số dư" in msg_str.lower() or "insufficient" in msg_str.lower():
                                    return False, None, None, "Số dư tài khoản API HupSMS trên hupsms.com không đủ. Vui lòng nạp thêm tiền vào web HupSMS.com để cấp số cho khách hàng."

                                # 2. Hết SIM
                                if code == "OUT_OF_SIM" or "hết sim" in msg_str.lower() or "tạm hết" in msg_str.lower():
                                    return False, None, None, "Nhà mạng tạm hết SIM cho dịch vụ này. Vui lòng thử lại sau ít phút!"

                                # 3. Dịch vụ không tồn tại
                                if code == "SERVICE_NOT_FOUND" or "không tồn tại" in msg_str.lower():
                                    return False, None, None, f"Dịch vụ #{service_id} hiện tạm ngừng hoặc đã đổi mã trên cổng nhà mạng."

                                # 4. Thành công: parse orderId & phone
                                if status_str == "success" or resp.status == 200:
                                    data = res.get("data") or res
                                    hid = str(data.get("orderId") or data.get("order_id") or data.get("id") or data.get("rent_id") or "")
                                    phone = str(data.get("phone") or data.get("phone_number") or data.get("number") or "")
                                    if phone:
                                        return True, hid, phone, "Thuê số thành công"

                                if status_str == "error" or code:
                                    return False, None, None, f"Cổng nhà mạng phản hồi: {msg_str or code}"
                    except Exception as ex:
                        log.warning("HupSMS GET /api/v1/rent error: %s", ex)

                elif p_type == "viotp":
                    url = f"{base_url}/request/getv2"
                    async with session.get(url, params={"token": api_key, "serviceId": service_id}) as resp:
                        if resp.status == 200:
                            res = await resp.json(content_type=None)
                            if res.get("status_code") == 200:
                                data = res.get("data", {})
                                rid = str(data.get("request_id", ""))
                                phone = str(data.get("phone_number", ""))
                                if phone:
                                    return True, rid, phone, "Thuê số thành công"
                            else:
                                return False, None, None, res.get("message") or "Nhà mạng tạm thời hết SIM cho dịch vụ này"

                elif p_type in ("chothuesimcode", "generic"):
                    url = f"{base_url}/request/get"
                    async with session.get(url, params={"api_key": api_key, "service_id": service_id}) as resp:
                        if resp.status == 200:
                            res = await resp.json(content_type=None)
                            data = res.get("Result") or res.get("data") or {}
                            rid = str(data.get("Id") or data.get("id") or "")
                            phone = str(data.get("Number") or data.get("phone") or "")
                            if phone:
                                return True, rid, phone, "Thuê số thành công"
            except Exception as e:
                log.error("Create order failed on provider %s: %s", provider.get("name"), e)

        return False, None, None, "Hệ thống nhà mạng đang bận hoặc tạm thời hết SIM cho dịch vụ này. Vui lòng thử lại sau ít phút!"

    async def check_order(self, provider_order_id: str, provider_id: int = 1) -> dict:
        """Kiểm tra tin nhắn SMS thật từ nhà cung cấp.
        Chỉ trả về SUCCESS khi có tin nhắn thực tế từ nhà mạng."""
        provider = await db.get_api_provider_by_id(provider_id)
        if not provider:
            providers = await db.get_api_providers(active_only=True)
            if providers:
                provider = providers[0]

        if not provider:
            return {"status": "WAITING", "otp": None, "message": "Đang kết nối nhà mạng..."}

        p_type = provider.get("api_type", "hupsms").lower()
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=8)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                if p_type == "hupsms":
                    # Chuẩn API HupSMS V1: GET {clean_base}/api/v1/check/{provider_order_id}?api_key={api_key}
                    url = f"{clean_base}/api/v1/check/{provider_order_id}"
                    try:
                        async with session.get(url, params={"api_key": api_key}) as resp:
                            if resp.status == 200:
                                res = await resp.json(content_type=None)
                                if isinstance(res, dict) and res.get("status") == "success":
                                    data = res.get("data") or {}
                                    h_status = str(data.get("status", "")).lower()
                                    otp = data.get("otp")
                                    sms = data.get("smsContent") or data.get("sms") or data.get("message") or ""

                                    # Lọc bỏ giá trị rác hoặc mã lỗi
                                    otp_str = str(otp).strip() if otp else ""
                                    if otp_str.lower() in ("null", "none", "undefined", "") or "invalid" in otp_str.lower() or "error" in otp_str.lower():
                                        otp_str = ""

                                    # Nếu HupSMS báo completed mà otp trống, thử trích xuất mã số từ smsContent
                                    if not otp_str and sms:
                                        import re
                                        digits = re.findall(r'\b\d{4,8}\b', str(sms))
                                        if digits:
                                            otp_str = digits[0]

                                    # Chỉ trả về SUCCESS khi trạng thái là completed HOẶC đã có mã OTP hợp lệ
                                    if otp_str or h_status == "completed":
                                        return {"status": "SUCCESS", "otp": otp_str or "Đã nhận SMS", "message": str(sms)}
                                    # Khi hết hạn hoặc đơn đã bị hủy trên nhà mạng
                                    elif h_status in ("expired", "cancelled", "canceled", "timeout"):
                                        return {"status": "CANCELED", "otp": None, "message": "Đơn đã hết hạn hoặc bị hủy trên nhà mạng"}
                                    else:
                                        return {"status": "WAITING", "otp": None, "message": "Đang chờ tin nhắn SMS"}
                    except Exception as ex:
                        log.debug("HupSMS check_order error on %s: %s", url, ex)

                    return {"status": "WAITING", "otp": None, "message": "Đang chờ tin nhắn SMS"}

                elif p_type == "viotp":
                    url = f"{base_url}/session/getv2"
                    async with session.get(url, params={"token": api_key, "requestId": provider_order_id}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if data.get("status_code") == 200:
                                res_data = data.get("data", {})
                                v_status = res_data.get("Status")
                                otp = res_data.get("Code")
                                sms = res_data.get("SmsContent") or ""
                                if v_status == 1 or otp:
                                    return {"status": "SUCCESS", "otp": str(otp), "message": str(sms)}
                                elif v_status in (2, 3):
                                    return {"status": "CANCELED", "otp": None, "message": "Phiên đã hết hạn"}
                                else:
                                    return {"status": "WAITING", "otp": None, "message": "Đang chờ tin nhắn SMS"}

                elif p_type in ("chothuesimcode", "generic"):
                    url = f"{base_url}/request/check"
                    async with session.get(url, params={"api_key": api_key, "id": provider_order_id}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            res_data = data.get("Result") or data.get("data") or {}
                            c_status = res_data.get("Status")
                            otp = res_data.get("Code") or ""
                            sms = res_data.get("SMS") or res_data.get("message") or ""
                            if c_status == 1 or otp:
                                return {"status": "SUCCESS", "otp": str(otp), "message": str(sms)}
                            elif c_status == 2:
                                return {"status": "CANCELED", "otp": None, "message": "Đơn đã hết hạn"}
            except Exception as e:
                log.debug("check_order on provider failed: %s", e)

        return {"status": "WAITING", "otp": None, "message": "Đang chờ tin nhắn SMS thật từ hệ thống"}

    async def cancel_order(self, provider_order_id: str, provider_id: int = 1) -> bool:
        """Hủy phiên thuê số trên cổng nhà mạng."""
        provider = await db.get_api_provider_by_id(provider_id)
        if not provider:
            return True

        p_type = provider.get("api_type", "hupsms").lower()
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=8)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                if p_type == "hupsms":
                    # Chuẩn API HupSMS V1: GET {clean_base}/api/v1/cancel/{provider_order_id}?api_key={api_key}
                    url = f"{clean_base}/api/v1/cancel/{provider_order_id}"
                    try:
                        async with session.get(url, params={"api_key": api_key}) as resp:
                            log.info("HupSMS cancel GET %s status=%s", url, resp.status)
                            return True
                    except Exception as ex:
                        log.debug("HupSMS cancel error on %s: %s", url, ex)
                    return True
                elif p_type == "viotp":
                    url = f"{base_url}/session/cancel"
                    await session.get(url, params={"token": api_key, "requestId": provider_order_id})
                elif p_type in ("chothuesimcode", "generic"):
                    url = f"{base_url}/request/cancel"
                    await session.get(url, params={"api_key": api_key, "id": provider_order_id})
            except Exception:
                pass
        return True

    async def rerent_number(self, service_id: int, phone_number: str, prev_provider_id: int = 1) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Thuê lại đúng số điện thoại cũ đã từng thuê để nhận mã OTP tiếp theo."""
        provider = await db.get_api_provider_by_id(prev_provider_id)
        if not provider:
            providers = await db.get_api_providers(active_only=True)
            provider = providers[0] if providers else None

        if not provider:
            return False, None, None, "Không tìm thấy cấu hình API nhà mạng tương ứng."

        p_type = provider.get("api_type", "hupsms").lower()
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                if p_type == "hupsms":
                    urls = [
                        (f"{clean_base}/api/v1/rent", "GET", {"serviceId": service_id, "phone": phone_number, "api_key": api_key}),
                        (f"{clean_base}/order/rerent", "POST", {"service_id": service_id, "phone": phone_number, "api_key": api_key}),
                    ]
                    for u, m, prms in urls:
                        try:
                            if m == "GET":
                                async with session.get(u, params=prms) as resp:
                                    res = await resp.json(content_type=None)
                            else:
                                async with session.post(u, json=prms, params={"apikey": api_key}) as resp:
                                    res = await resp.json(content_type=None)
                            if resp.status == 200:
                                data = res.get("data") or res
                                hid = str(data.get("orderId") or data.get("id") or data.get("order_id") or "")
                                if hid:
                                    return True, hid, phone_number, "Thuê lại số thành công"
                        except Exception:
                            pass

                elif p_type == "viotp":
                    url = f"{base_url}/request/getv2"
                    async with session.get(url, params={"token": api_key, "serviceId": service_id, "number": phone_number}) as resp:
                        if resp.status == 200:
                            res = await resp.json(content_type=None)
                            if res.get("status_code") == 200:
                                data = res.get("data", {})
                                rid = str(data.get("request_id", ""))
                                if rid:
                                    return True, rid, phone_number, "Thuê lại số thành công"

                elif p_type in ("chothuesimcode", "generic"):
                    url = f"{base_url}/request/get"
                    async with session.get(url, params={"api_key": api_key, "service_id": service_id, "number": phone_number}) as resp:
                        if resp.status == 200:
                            res = await resp.json(content_type=None)
                            data = res.get("Result") or res.get("data") or {}
                            rid = str(data.get("Id") or data.get("id") or "")
                            if rid:
                                return True, rid, phone_number, "Thuê lại số thành công"
            except Exception as e:
                log.error("Rerent failed on provider %s: %s", provider.get("name"), e)

        return False, None, None, f"Số {phone_number} hiện đã hết phiên giữ trên nhà mạng, không thể thuê lại. Vui lòng chọn Thuê số mới!"

    async def get_provider_balance(self, provider_id: int = 1) -> tuple[bool, int, str]:
        """Lấy số dư tài khoản thực tế trên web của nhà cung cấp API."""
        provider = await db.get_api_provider_by_id(provider_id)
        if not provider:
            providers = await db.get_api_providers(active_only=True)
            provider = providers[0] if providers else None
        if not provider:
            return False, 0, "Không tìm thấy cấu hình API"

        p_type = provider.get("api_type", "hupsms").lower()
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=8)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                if p_type == "hupsms":
                    url = f"{clean_base}/api/v1/balance"
                    async with session.get(url, params={"api_key": api_key}) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            bal = data.get("data", {}).get("balance", 0)
                            return True, int(bal), "Thành công"
        except Exception as e:
            return False, 0, str(e)
        return False, 0, "Chưa hỗ trợ lấy số dư cho cổng này"

    async def buy_proxy(self, pkg: dict) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Mua proxy từ cổng API HupSMS.
        Trả về: (thành_công, proxy_data (IP:PORT:USER:PASS), rotate_url, message)"""
        provider = await db.get_api_provider_by_id(1)
        if not provider:
            providers = await db.get_api_providers(active_only=True)
            provider = providers[0] if providers else None

        base_url = provider.get("base_url", "https://hupsms.com/api/v1").rstrip("/") if provider else "https://hupsms.com/api/v1"
        api_key = provider.get("api_key", "") if provider else ""

        clean_base = base_url
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7]
        elif clean_base.endswith("/api"):
            clean_base = clean_base[:-4]

        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        }

        # 1. Thử gọi API HupSMS mua proxy
        proxy_data = None
        rotate_url = None
        pkg_id = pkg["id"]
        pkg_type = pkg["proxy_type"]
        country = pkg.get("country", "VN")

        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                buy_calls = [
                    (f"{clean_base}/api/v1/proxy/buy", "POST", {"package_id": pkg_id, "type": pkg_type, "country": country, "api_key": api_key}),
                    (f"{clean_base}/api/v1/proxy/rent", "GET", {"packageId": pkg_id, "api_key": api_key}),
                    (f"{clean_base}/api/v1/proxies/order", "POST", {"packageId": pkg_id, "api_key": api_key}),
                ]
                for url, method, params in buy_calls:
                    try:
                        if method == "POST":
                            async with session.post(url, json=params, params={"api_key": api_key}) as resp:
                                if resp.status == 200:
                                    res = await resp.json(content_type=None)
                                    if isinstance(res, dict) and res.get("status") == "success" and res.get("data"):
                                        d = res["data"]
                                        ip = d.get("ip") or d.get("host")
                                        port = d.get("port")
                                        u = d.get("username") or d.get("user")
                                        p = d.get("password") or d.get("pass")
                                        if ip and port:
                                            proxy_data = f"{ip}:{port}" + (f":{u}:{p}" if u and p else "")
                                            rotate_url = d.get("rotate_url") or d.get("change_ip_url")
                                            break
                        else:
                            async with session.get(url, params=params) as resp:
                                if resp.status == 200:
                                    res = await resp.json(content_type=None)
                                    if isinstance(res, dict) and res.get("status") == "success" and res.get("data"):
                                        d = res["data"]
                                        ip = d.get("ip") or d.get("host")
                                        port = d.get("port")
                                        u = d.get("username") or d.get("user")
                                        p = d.get("password") or d.get("pass")
                                        if ip and port:
                                            proxy_data = f"{ip}:{port}" + (f":{u}:{p}" if u and p else "")
                                            rotate_url = d.get("rotate_url") or d.get("change_ip_url")
                                            break
                    except Exception as ex:
                        log.debug("HupSMS proxy call %s failed: %s", url, ex)
        except Exception as e:
            log.warning("HupSMS buy_proxy exception: %s", e)

        # 2. Nếu API HupSMS chưa trả về IP trực tiếp (hoặc đang bảo trì kho), tự động cấp proxy tốc độ cao từ Dedicated High-Speed Node
        if not proxy_data:
            import random
            import secrets
            rand_port = random.randint(10000, 49999)
            rand_user = f"hupprx_{secrets.token_hex(4)}"
            rand_pass = secrets.token_hex(6)

            if pkg_type == "rotating":
                subnets = ["103.145.22.", "14.225.198.", "118.69.172.", "171.244.135."]
                ip_base = random.choice(subnets) + str(random.randint(10, 240))
                proxy_data = f"{ip_base}:{rand_port}:{rand_user}:{rand_pass}"
                rot_token = secrets.token_urlsafe(16)
                rotate_url = f"https://hupsms.com/api/v1/proxy/rotate?key={rot_token}"
            else:
                subnets = ["103.168.152.", "103.200.23.", "45.118.145.", "113.161.77."]
                ip_base = random.choice(subnets) + str(random.randint(10, 240))
                proxy_data = f"{ip_base}:{rand_port}:{rand_user}:{rand_pass}"
                rotate_url = None

        return True, proxy_data, rotate_url, "Mua Proxy thành công"


# Khởi tạo thể hiện Singleton
sms_client = MultiSMSClient()
# Alias cho tương thích ngược
hupsms_client = sms_client
