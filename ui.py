import html
from typing import List, Optional, Any
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import SUPPORT_USERNAME

# Bảng mã Custom Emoji 3D chính thức của Telegram (Tương thích Telegram Premium)
CUSTOM_EMOJIS = {
    # Menu Items
    "buy": "5431499171045581032",       # 🛒
    "profile": "5373012449597335010",   # 👤
    "history": "5426900601101374618",   # 🧿
    "wallet": "5472363448404809929",    # 👛
    "api": "5375129357373165375",       # 🔗
    "support": "5465300082628763143",   # 💬
    "warranty": "5375296873982604963",  # 💰
    "language": "5399898266265475100",  # 🌐
    
    # Visual Highlights
    "fire": "5420315771991497307",      # 🔥
    "target": "5350460637182993292",    # 🎯
    "diamond": "5471952986970267163",   # 💎
    "party": "5436040291507247633",     # 🎉
    "crown": "5467406098367521267",     # 👑
    "arrow": "5471978009449731768",     # 👉
    "soldout": "5465665476971471368",   # ❌
    "star": "5447410652846162601",      # ⭐
    "check": "5465665476971471368",     # ✅

    # Logo thương hiệu 3D chính hãng từ gói sms_icons_by_thueotpvip2026_bot
    "facebook": "6273931193402532337",  # Facebook Logo
    "telegram": "6271451588523468222",  # Telegram Logo
    "tiktok": "6273557148995690258",    # TikTok Logo
    "zalo": "6273962473649348197",      # Zalo Logo
    "google": "6271319123142123956",    # Google Logo
    "gmail": "6271728205892165984",     # Gmail Logo
    "shopee": "6271399477685265090",    # Shopee Logo
    "whatsapp": "6271507165400276513",  # WhatsApp Logo
    "openai": "6271768286526971864",    # OpenAI / ChatGPT Logo
    "discord": "6271481026229316019",   # Discord Logo
    "apple": "6271431565385933676",     # Apple Logo
    "amazon": "6271754306408424806",    # Amazon Logo
    "alibaba": "6271725525832573884",   # Alibaba Logo
    "taobao": "6271725525832573884",    # Taobao Logo
    "lazada": "6271756483956843223",    # Lazada Logo
    "momo": "6273613576276025603",      # MoMo Logo
    "mbbank": "6271340258676188729",    # MBBank Logo
    "twitter": "6273799681503928293",   # Twitter Logo
    "instagram": "6271349187913196114", # Instagram Logo
    "microsoft": "6273815083256651865", # Microsoft Logo
    "netflix": "6271671323345296987",   # Netflix Logo
    "spotify": "6273777798645556212",   # Spotify Logo
    "tinder": "6273796713681527022",    # Tinder Logo
    "steam": "6271317967795921238",     # Steam Logo
    "canva": "6273707700484316443",     # Canva Logo
    "capcut": "6273779615416722281",    # CapCut Logo
    "be": "6273816006674620874",        # Be Logo
    "grab": "6271804918303040431",      # Grab Logo
    "garena": "6271439017154190753",    # Garena Logo
}

def get_brand_emoji_id(name: str) -> Optional[str]:
    """Tìm custom_emoji_id theo tên app."""
    n = (name or "").lower()
    for k, cid in CUSTOM_EMOJIS.items():
        if k in n:
            return cid
    return None

def esc(text: Any) -> str:
    return html.escape(str(text or ""))

def fmt_vnd(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")

def ce(icon_key: str, fallback: str = "⭐") -> str:
    """Tạo thẻ <tg-emoji> hiển thị Icon 3D động trong nội dung tin nhắn."""
    cid = CUSTOM_EMOJIS.get(icon_key)
    if cid:
        return f'<tg-emoji emoji-id="{cid}">{fallback}</tg-emoji>'
    return fallback

def btn(
    text: str,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    icon: Optional[str] = None,
    style: str = "success",
) -> InlineKeyboardButton:
    """Nút bấm Inline với màu xanh lá style='success' và icon 3D chuẩn Bot API 7.0+."""
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    elif callback_data:
        kwargs["callback_data"] = callback_data
    else:
        kwargs["callback_data"] = "none"
    
    if icon:
        kwargs["icon_custom_emoji_id"] = str(icon)
        # Bỏ emoji thường ở đầu chữ để tránh hiển thị 2 icon
        parts = text.split(" ", 1)
        if len(parts) == 2 and parts[0] and not any(ch.isalnum() for ch in parts[0]):
            kwargs["text"] = parts[1]
    if style in ("success", "danger", "primary"):
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

def kb(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ==============================================================================
# MENU DƯỚI Ô CHAT (REPLY KEYBOARD PERSISTENT GRID)
# ==============================================================================
def reply_menu_kb() -> ReplyKeyboardMarkup:
    """Bàn phím menu cố định dưới ô chat y hệt trong ảnh thiết kế."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Mua hàng")],
            [KeyboardButton(text="👤 Hồ sơ"), KeyboardButton(text="🧿 Lịch sử mua"), KeyboardButton(text="👛 Ví")],
            [KeyboardButton(text="🔗 Liên kết API"), KeyboardButton(text="💬 Hỗ trợ"), KeyboardButton(text="📜 Điều khoản")],
            [KeyboardButton(text="🌐 Ngôn ngữ")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

# ==============================================================================
# INLINE KEYBOARD MENU CHÍNH (NÚT XANH LÁ + ICON 3D)
# ==============================================================================
def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Bố cục Menu chính 100% nút xanh lá style='success' với icon 3D như ảnh."""
    rows = [
        [btn("🛒 Mua hàng / Thuê OTP", "u:rent_menu", icon=CUSTOM_EMOJIS["buy"], style="success")],
        [
            btn("🌐 Thuê PROXY", "u:proxy:static", icon=CUSTOM_EMOJIS.get("target"), style="success"),
            btn("🔄 PROXY XOAY VIP", "u:proxy:rotating", icon=CUSTOM_EMOJIS.get("fire"), style="success"),
        ],
        [
            btn("👤 Hồ sơ", "u:profile", icon=CUSTOM_EMOJIS["profile"], style="success"),
            btn("🧿 Lịch sử mua", "u:history", icon=CUSTOM_EMOJIS["history"], style="success"),
        ],
        [
            btn("👛 Ví", "u:deposit", icon=CUSTOM_EMOJIS["wallet"], style="success"),
            btn("🔗 Liên kết API", "u:api_docs", icon=CUSTOM_EMOJIS["api"], style="success"),
        ],
        [
            btn("💬 Hỗ trợ", url=f"https://t.me/{SUPPORT_USERNAME}", icon=CUSTOM_EMOJIS["support"], style="success"),
            btn("📜 Điều khoản & Bảo hành", "u:warranty", icon=CUSTOM_EMOJIS["warranty"], style="success"),
        ],
        [btn("🌐 Ngôn ngữ", "u:language", icon=CUSTOM_EMOJIS["language"], style="success")],
    ]
    if is_admin:
        rows.append([btn("⚙️ Quản trị viên (Admin)", "adm:dashboard", style="primary")])
    return kb(rows)

# ==============================================================================
# NỘI DUNG GIỚI THIỆU CHÀO MỪNG (VĂN BẢN KÈM LOGO CHUẨN TỪNG APP)
# ==============================================================================
def render_welcome_card() -> str:
    """Giao diện chào mừng duy nhất, chuẩn xác, không bị lặp tin nhắn."""
    return (
        f"{ce('fire', '🔥')} <b>CHÀO MỪNG ĐẾN VỚI TÀI NGUYÊN MMO - SMS GIÁ RẺ</b> {ce('fire', '🔥')}\n"
        f"{ce('target', '🎯')} <i>Hệ thống cho thuê số điện thoại ảo nhận OTP tự động kết nối đa API nhà mạng hàng đầu!</i>\n\n"
        f"{ce('diamond', '💎')} <b>CÁC DỊCH VỤ NHẬN OTP ĐƯỢC ƯA CHUỘNG NHẤT:</b>\n"
        f"• {ce('facebook', '📘')} <b>Facebook</b>: Reg nick clone/via, mở checkpoint, xác minh 2FA\n"
        f"• {ce('telegram', '✈️')} <b>Telegram</b>: Nhận mã đăng nhập, tạo session tele số lượng lớn\n"
        f"• {ce('tiktok', '🎵')} <b>TikTok</b>: Tạo tài khoản TikTok Shop, Beta Creator, MMO\n"
        f"• {ce('zalo', '💬')} <b>Zalo</b>: Kích hoạt Zalo cá nhân, Zalo OA nhanh chóng\n"
        f"• {ce('google', '🌐')} <b>Google / Gmail</b>: Xác minh tài khoản Google Cloud, YouTube, Gmail cổ\n"
        f"• {ce('shopee', '🛍')} <b>Shopee</b>: Tạo tài khoản săn voucher Shopee, liên kết ví\n"
        f"• {ce('openai', '🤖')} <b>OpenAI / ChatGPT</b>: Xác thực đăng ký ChatGPT Plus, OpenAI API\n"
        f"• {ce('whatsapp', '🟢')} <b>WhatsApp</b>, {ce('apple', '🍏')} <b>Apple</b>, {ce('discord', '🎮')} <b>Discord</b>, {ce('amazon', '📦')} <b>Amazon</b>...\n\n"
        f"{ce('arrow', '👉')} Cam kết: <b>SMS thật 100% từ SIM nhà mạng</b> — Không dùng mã ảo!\n"
        f"{ce('arrow', '👉')} Hoàn tiền: <b>Hoàn 100% ví ngay lập tức</b> nếu không nhận được mã SMS!\n"
        f"{ce('arrow', '👉')} Hỗ trợ: <b>Thuê lại số cũ</b> tiện lợi cho việc gia hạn hoặc nhận mã lần 2!\n\n"
        f"{ce('crown', '👑')} <b>Admin hỗ trợ 24/7:</b> @{SUPPORT_USERNAME}\n\n"
        f"👇 <i>Vui lòng chọn dịch vụ từ menu bên dưới:</i>"
    )

# ==============================================================================
# MENU NẠP TIỀN VÍ & TẠO QR BANK TỰ ĐỘNG (MIN DO ADMIN CHỌN)
# ==============================================================================
def render_deposit_amount_selection(user: dict, min_deposit: int = 50000) -> tuple[str, InlineKeyboardMarkup]:
    bal = user.get("balance", 0)
    m = max(1000, min_deposit)
    text = (
        f"{ce('wallet', '👛')} <b>NẠP TIỀN VÀO TÀI KHOẢN (DUYỆT TỰ ĐỘNG QUA QR BANK)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Số dư ví hiện tại: <b>{fmt_vnd(bal)}</b>\n"
        f"• Mức nạp tối thiểu: <b>{fmt_vnd(m)}</b>\n"
        f"• Cơ chế: Quét mã QR Napas chuyển khoản, tiền tự động nhảy vào ví sau 1 - 3 phút.\n\n"
        f"👉 <b>Vui lòng chọn số tiền bạn muốn nạp:</b>"
    )
    if m <= 10000:
        presets = [10000, 20000, 50000, 100000, 200000, 500000]
    elif m <= 20000:
        presets = [20000, 50000, 100000, 200000, 500000, 1000000]
    elif m <= 50000:
        presets = [50000, 100000, 200000, 500000, 1000000, 2000000]
    else:
        presets = [m, m * 2, m * 4, m * 6, m * 10, m * 20]

    markup = kb([
        [btn(f"💵 {fmt_vnd(presets[0])} (Tối thiểu)", f"dep_amt:{presets[0]}", style="success"), btn(f"💵 {fmt_vnd(presets[1])}", f"dep_amt:{presets[1]}", style="success")],
        [btn(f"💵 {fmt_vnd(presets[2])}", f"dep_amt:{presets[2]}", style="success"), btn(f"💵 {fmt_vnd(presets[3])}", f"dep_amt:{presets[3]}", style="success")],
        [btn(f"💵 {fmt_vnd(presets[4])}", f"dep_amt:{presets[4]}", style="success"), btn(f"💵 {fmt_vnd(presets[5])}", f"dep_amt:{presets[5]}", style="success")],
        [btn(f"✍️ Nhập số tiền tùy ý (Từ {fmt_vnd(m)})", "dep_amt:custom", style="primary")],
        [btn("« Quay lại Menu chính", "u:home")],
    ])
    return text, markup

def render_deposit_qr_card(user_id: int, amount: int, bank_name: str, bank_acc: str, bank_owner: str) -> tuple[str, str, InlineKeyboardMarkup]:
    """Tạo thông tin thanh toán VietQR động theo đúng số tiền khách yêu cầu."""
    memo = f"NAP {user_id}"
    qr_url = f"https://img.vietqr.io/image/{bank_name}-{bank_acc}-compact2.png?amount={amount}&addInfo={memo}&accountName={bank_owner}"
    
    caption = (
        f"{ce('diamond', '💎')} <b>MÃ QR NẠP TIỀN: {fmt_vnd(amount)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Ngân hàng: <b>{esc(bank_name)}</b>\n"
        f"💳 Số tài khoản: <code>{esc(bank_acc)}</code> <i>(Chạm để sao chép)</i>\n"
        f"👤 Chủ tài khoản: <b>{esc(bank_owner)}</b>\n"
        f"💵 Số tiền thanh toán: <b>{fmt_vnd(amount)}</b>\n"
        f"📝 Nội dung chuyển khoản: <code>{memo}</code> <i>(Bắt buộc, chạm để copy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>HƯỚNG DẪN:</b>\n"
        f"1. Mở App Ngân hàng bất kỳ -> Chọn <b>Quét mã QR</b> hình trên.\n"
        f"2. Giữ nguyên số tiền và nội dung <code>{memo}</code> khi chuyển khoản.\n"
        f"3. Tiền sẽ tự động cộng vào ví của bạn sau 1 - 3 phút!"
    )
    markup = kb([
        [btn("🔄 Kiểm tra số dư ví", "u:profile", style="success")],
        [btn("💵 Chọn số tiền khác", "u:deposit", style="primary")],
        [btn("💬 Hỗ trợ CSKH", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [btn("« Menu chính", "u:home")],
    ])
    return qr_url, caption, markup

# ==============================================================================
# CARD CHỜ OTP & THÀNH CÔNG & THUÊ LẠI SỐ
# ==============================================================================
def render_order_waiting_card(order: dict, remaining_seconds: int) -> tuple[str, InlineKeyboardMarkup]:
    oid = order["order_id"]
    sname = order["service_name"]
    price = order["selling_price"]
    phone = order["phone_number"] or "Đang lấy số..."
    
    mins = remaining_seconds // 60
    secs = remaining_seconds % 60
    time_str = f"{mins:02d}:{secs:02d}"
    
    brand_icon = get_brand_emoji_id(sname)
    icon_tag = f'<tg-emoji emoji-id="{brand_icon}">📱</tg-emoji> ' if brand_icon else "📱 "
    
    text = (
        f"⚡️ <b>ĐƠN THUÊ OTP: #{oid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{icon_tag}Dịch vụ: <b>{esc(sname)}</b>\n"
        f"💰 Cước phí: <b>{fmt_vnd(price)}</b> (Đã tạm giữ ví)\n"
        f"📞 Số điện thoại: <code>{phone}</code> <i>(Chạm để sao chép)</i>\n"
        f"⏱ Thời gian chờ còn lại: <b>{time_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>Đang chờ tin nhắn SMS thật từ nhà mạng...</b>\n\n"
        f"💡 <i>Bạn hãy nhập số điện thoại trên vào ứng dụng để gửi mã OTP. Ngay khi có tin nhắn, mã sẽ tự động hiện tại đây!</i>\n\n"
        f"📜 <b>ĐIỀU KHOẢN SỬ DỤNG:</b>\n"
        f"• Nghiêm cấm các hành vì lừa đảo, sử dụng cho mục đích vi phạm pháp luật, lọc tài khoản cũ, spam lọc số không nhận mã, tạo nhiều tài khoản khác nhau lợi dụng (chúng tôi sẽ khóa tài khoản vĩnh viễn không cần cảnh báo)\n\n"
        f"• Khi thuê sim, bạn cũng đang đồng ý với việc chấp nhận rủi ro vì dịch vụ sim gửi/nhận SMS không may có thể bị nhà mạng chặn/dính vào mục spam, suy ra việc gửi hoặc nhận tin nhắn có thể sẽ thất bại!\n\n"
        f"• Sử dụng mục tìm kiếm để sử dụng dịch vụ bạn cần, bạn có thể thử nhiều kho để chọn dịch vụ nhận mã tốt nhất. Hệ thống chỉ có nhiệm vụ trả tin nhắn đúng nội dung nhận được, vui lòng lưu ý.\n\n"
        f"• Số SIM có thể bị trùng dịch vụ bạn dùng, bạn vui lòng thuê số khác hoặc chọn dịch vụ khác, số bạn không sử dụng sẽ hoàn tiền vào tài khoản của bạn ngay khi hết thời gian thuê số."
    )
    
    buttons = kb([
        [btn("🔄 Kiểm tra ngay", f"u:recheck:{oid}", style="primary")],
        [btn("❌ Hủy thuê & Hoàn tiền ví", f"u:cancel_order:{oid}", style="danger")],
        [btn("« Menu chính", "u:home")],
    ])
    return text, buttons

def render_order_success_card(order: dict) -> tuple[str, InlineKeyboardMarkup]:
    oid = order["order_id"]
    sname = order["service_name"]
    phone = order["phone_number"]
    otp = order["otp_code"]
    sms = order.get("sms_content") or "Tin nhắn xác thực nhận từ nhà mạng"
    
    brand_icon = get_brand_emoji_id(sname)
    icon_tag = f'<tg-emoji emoji-id="{brand_icon}">📱</tg-emoji> ' if brand_icon else "📱 "
    
    text = (
        f"🎉 <b>NHẬN MÃ OTP THÀNH CÔNG!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{icon_tag}Dịch vụ: <b>{esc(sname)}</b>\n"
        f"📞 Số điện thoại: <code>{phone}</code>\n"
        f"🔑 MÃ OTP XÁC NHẬN:\n"
        f"👉 <code>{esc(otp)}</code> 👈 <i>(Chạm vào mã để sao chép)</i>\n\n"
        f"📩 <b>Nội dung tin nhắn SMS gốc:</b>\n"
        f"<i>{esc(sms)}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <i>Giao dịch hoàn tất! Cảm ơn bạn đã tin tưởng sử dụng dịch vụ.</i>"
    )
    
    buttons = kb([
        [btn(f"📋 Sao chép mã OTP: {otp}", f"u:copy_otp:{otp}", style="success")],
        [btn(f"🔄 Thuê lại số này ({phone})", f"u:rerent:{oid}", style="success")],
        [btn("⚡️ Thuê số mới", "u:rent_menu", style="primary"), btn("« Menu chính", "u:home")],
    ])
    return text, buttons

def render_order_timeout_card(order: dict) -> tuple[str, InlineKeyboardMarkup]:
    oid = order["order_id"]
    sname = order["service_name"]
    price = order["selling_price"]
    
    text = (
        f"⚠️ <b>ĐƠN HÀNG HẾT HẠN - ĐÃ HOÀN TIỀN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Dịch vụ: <b>{esc(sname)}</b> (#{oid})\n"
        f"💰 Số tiền hoàn lại: <b>+{fmt_vnd(price)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡 Do hệ thống chưa nhận được SMS trong thời gian quy định, toàn bộ cước phí đã được <b>hoàn 100% vào số dư ví</b> của bạn.\n"
        f"👉 Bạn có thể bấm <b>Thuê lại số khác</b> để hệ thống cấp số mới!"
    )
    
    buttons = kb([
        [btn("🔄 Thuê lại số khác", f"u:rent_sid:{order['service_id']}", style="success")],
        [btn("« Menu chính", "u:home")],
    ])
    return text, buttons

# ==============================================================================
# GIAO DIỆN MUA PROXY & PROXY XOAY VIP (TÍCH HỢP HUPSMS)
# ==============================================================================
def render_proxy_catalog(packages: list, proxy_type: str, user_balance: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    type_name = "PROXY XOAY DÂN CƯ VIP" if proxy_type == "rotating" else "PROXY TĨNH IPV4/IPV6"
    icon = "🔄" if proxy_type == "rotating" else "🌐"
    
    text = (
        f"{icon} <b>BẢNG GIÁ {type_name}</b> {icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Số dư ví của bạn: <b>{fmt_vnd(user_balance)}</b>\n"
        f"• Nguồn cấp: Cổng máy chủ HupSMS tốc độ cao 100Mbps\n"
        f"• Hỗ trợ: Giao thức HTTP và SOCKS5 cho mọi tool/trình duyệt\n"
    )
    if proxy_type == "rotating":
        text += (
            f"• Tính năng Xoay VIP: Tự đổi IP theo chu kỳ hoặc click Link đổi IP tức thì không giới hạn lượt xoay!\n\n"
            f"👉 <i>Chạm vào gói bên dưới để xem chi tiết và mua ngay:</i>"
        )
    else:
        text += (
            f"• Tính năng Proxy Tĩnh: IP cố định riêng tư 100%, nuôi tài khoản, làm marketing cực trust!\n\n"
            f"👉 <i>Chạm vào gói bên dưới để xem chi tiết và mua ngay:</i>"
        )

    rows = []
    for p in packages:
        btn_text = f"{icon} {p['name']} — {fmt_vnd(p['selling_price'])}"
        rows.append([btn(btn_text, f"u:prx_dtl:{p['id']}", style="success")])

    nav_row = [
        btn("🔄 Proxy Xoay VIP" if proxy_type == "static" else "🌐 Proxy Tĩnh VIP", 
            "u:proxy:rotating" if proxy_type == "static" else "u:proxy:static", style="primary"),
        btn("📋 Proxy đã mua", "u:my_proxies", style="primary")
    ]
    rows.append(nav_row)
    rows.append([btn("👛 Nạp tiền ví", "u:deposit", style="success"), btn("« Menu chính", "u:home")])
    return text, kb(rows)

def render_proxy_package_detail(pkg: dict, user_balance: int) -> tuple[str, InlineKeyboardMarkup]:
    pid = pkg["id"]
    pname = pkg["name"]
    ptype = pkg["proxy_type"]
    price = pkg["selling_price"]
    country = pkg.get("country", "VN")
    proto = pkg.get("protocol", "HTTP/SOCKS5")
    duration = pkg.get("duration_days", 1)
    desc = pkg.get("description", "")
    type_label = "Proxy Xoay Dân Cư VIP (Đổi IP không giới hạn)" if ptype == "rotating" else "Proxy Tĩnh Riêng Tư (Dedicated IP)"

    text = (
        f"📦 <b>CHI TIẾT GÓI PROXY #{pid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Tên gói: <b>{esc(pname)}</b>\n"
        f"🏷 Phân loại: <b>{type_label}</b>\n"
        f"🏳️ Quốc gia: <b>{esc(country)}</b>\n"
        f"🔒 Giao thức: <b>{esc(proto)}</b>\n"
        f"⏱ Thời hạn sử dụng: <b>{duration} ngày</b>\n"
        f"📝 Mô tả: <i>{esc(desc)}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Giá thanh toán: <b>{fmt_vnd(price)}</b>\n"
        f"👛 Số dư ví hiện tại: <b>{fmt_vnd(user_balance)}</b>\n"
    )

    if user_balance < price:
        diff = price - user_balance
        text += f"\n⚠️ <i>Số dư ví không đủ (thiếu {fmt_vnd(diff)}). Vui lòng nạp tiền trước khi mua!</i>"
        buttons = kb([
            [btn(f"💵 Nạp tiền vào ví ngay (Thiếu {fmt_vnd(diff)})", "u:deposit", style="success")],
            [btn("« Quay lại danh sách", f"u:proxy:{ptype}")],
        ])
    else:
        buttons = kb([
            [btn(f"✅ Xác nhận thanh toán {fmt_vnd(price)}", f"u:prx_buy:{pid}", style="success")],
            [btn("« Quay lại danh sách", f"u:proxy:{ptype}")],
        ])
    return text, buttons

def render_proxy_order_success(order: dict) -> tuple[str, InlineKeyboardMarkup]:
    oid = order["order_id"]
    pname = order["package_name"]
    ptype = order["proxy_type"]
    price = order["selling_price"]
    data = order["proxy_data"]
    rot = order.get("rotate_url")
    proto = order.get("protocol", "HTTP/SOCKS5")
    exp = order.get("expires_at", "")

    text = (
        f"🎉 <b>MUA PROXY THÀNH CÔNG! #{oid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Gói dịch vụ: <b>{esc(pname)}</b>\n"
        f"💰 Cước phí đã trừ: <b>{fmt_vnd(price)}</b>\n"
        f"⏱ Hạn sử dụng đến: <b>{esc(exp)}</b>\n"
        f"🔒 Giao thức hỗ trợ: <b>{esc(proto)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>THÔNG TIN KẾT NỐI PROXY:</b>\n"
        f"👉 <code>{esc(data)}</code> 👈 <i>(Chạm vào để sao chép dạng IP:PORT:USER:PASS)</i>\n"
    )

    if rot:
        text += (
            f"\n🔄 <b>LINK ĐỔI IP (XOAY PROXY TỨC THÌ):</b>\n"
            f"👉 <code>{esc(rot)}</code> 👈\n"
            f"💡 <i>Chạm vào link trên hoặc dán vào trình duyệt / tool nuôi nick để đổi sang địa chỉ IP mới ngay lập tức!</i>\n"
        )

    text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Thông tin Proxy luôn được lưu trữ an toàn. Bạn có thể xem lại bất cứ lúc nào trong mục <b>Hồ sơ</b> hoặc <b>Proxy đã mua</b>!</i>"
    )

    btn_rows = [
        [btn(f"📋 Sao chép Proxy: {data}", f"u:copy_otp:{data}", style="success")],
    ]
    if rot:
        btn_rows.append([btn("🔄 Nhấp để đổi IP mới", url=rot, style="primary")])
    btn_rows.append([
        btn("🌐 Mua thêm Proxy", f"u:proxy:{ptype}", style="primary"),
        btn("📋 Proxy của tôi", "u:my_proxies")
    ])
    btn_rows.append([btn("« Menu chính", "u:home")])
    return text, kb(btn_rows)

def render_my_proxies(orders: list) -> tuple[str, InlineKeyboardMarkup]:
    if not orders:
        text = (
            "🌐 <b>DANH SÁCH PROXY CỦA BẠN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Bạn chưa mua gói Proxy nào trên hệ thống.\n\n"
            "👉 Hãy chọn mục <b>Thuê PROXY</b> hoặc <b>PROXY XOAY VIP</b> để bắt đầu sử dụng!"
        )
        markup = kb([
            [btn("🌐 Thuê PROXY Tĩnh", "u:proxy:static", style="success"), btn("🔄 PROXY XOAY VIP", "u:proxy:rotating", style="success")],
            [btn("« Menu chính", "u:home")]
        ])
        return text, markup

    text = (
        f"🌐 <b>DANH SÁCH PROXY ĐÃ MUA ({len(orders)} GÓI GẦN NHẤT)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    for i, o in enumerate(orders, 1):
        text += (
            f"<b>{i}. {esc(o['package_name'])}</b> (#{o['order_id']})\n"
            f"• Proxy: <code>{esc(o['proxy_data'])}</code>\n"
            f"• Hết hạn: <code>{esc(o['expires_at'])}</code>\n"
        )
        if o.get("rotate_url"):
            text += f"• Link đổi IP: <code>{esc(o['rotate_url'])}</code>\n"
        text += "────────────────────\n"

    markup = kb([
        [btn("🌐 Mua thêm Proxy Tĩnh", "u:proxy:static", style="success"), btn("🔄 Mua thêm Proxy Xoay", "u:proxy:rotating", style="success")],
        [btn("« Menu chính", "u:home")]
    ])
    return text, markup
