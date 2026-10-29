import math
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import db
import ui
from ui import btn, kb, esc, fmt_vnd, ce, CUSTOM_EMOJIS, get_brand_emoji_id
from config import ADMIN_IDS, SUPPORT_USERNAME, is_admin as is_admin_check
import services

router = Router(name="user")

class UserSearchState(StatesGroup):
    waiting_for_keyword = State()

class DepositState(StatesGroup):
    waiting_for_amount = State()

# ==============================================================================
# LỆNH /START & GIAO DIỆN CHÀO MỪNG (CHUẨN XÁC, SẠCH ĐẸP, KHÔNG BỊ TRÙNG LẶP)
# ==============================================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = message.from_user.id
    uname = message.from_user.username or message.from_user.full_name
    user = await db.get_or_create_user(uid, uname)
    is_admin = is_admin_check(uid, message.from_user.username)

    # 1. Bật bàn phím menu cố định dưới ô chat
    reply_kb = ui.reply_menu_kb()
    await message.answer(
        f"Xin chào <b>{esc(uname)}</b>! Chào mừng bạn đến với hệ thống {ce('party', '🎉')}\n"
        f"<i>Bàn phím menu nhanh dưới ô chat đã được kích hoạt.</i>",
        reply_markup=reply_kb,
        parse_mode="HTML"
    )

    # 2. Gửi thẻ giao diện chính chào mừng với đầy đủ logo từng app và menu nút xanh lá
    welcome_text = ui.render_welcome_card()
    inline_kb = ui.main_menu_kb(is_admin)
    sent_pin = await message.answer(welcome_text, reply_markup=inline_kb, parse_mode="HTML")
    try:
        await bot.pin_chat_message(message.chat.id, sent_pin.message_id)
    except Exception:
        pass

@router.callback_query(F.data == "u:home")
async def cb_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    uname = cb.from_user.username or cb.from_user.full_name
    user = await db.get_or_create_user(uid, uname)
    is_admin = is_admin_check(uid, cb.from_user.username)

    text = ui.render_welcome_card()
    markup = ui.main_menu_kb(is_admin)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

# ==============================================================================
# XỬ LÝ SỰ KIỆN TỪ BÀN PHÍM CỐ ĐỊNH DƯỚI Ô CHAT (REPLY KEYBOARD)
# ==============================================================================
@router.message(F.text.in_({"🛒 Mua hàng", "🛒 Mua hàng / Thuê OTP", "Mua hàng"}))
async def handle_reply_buy(message: Message, state: FSMContext):
    await cb_rent_menu_msg(message, state)

@router.message(F.text.in_({"👤 Hồ sơ", "Hồ sơ"}))
async def handle_reply_profile(message: Message):
    await show_profile_msg(message)

@router.message(F.text.in_({"🧿 Lịch sử mua", "📜 Lịch sử thuê", "Lịch sử mua"}))
async def handle_reply_history(message: Message):
    await show_history_msg(message)

@router.message(F.text.in_({"👛 Ví", "Ví"}))
async def handle_reply_wallet(message: Message):
    await show_deposit_msg(message)

@router.message(F.text.in_({"🔗 Liên kết API", "Liên kết API"}))
async def handle_reply_api(message: Message):
    await show_api_msg(message)

@router.message(F.text.in_({"💬 Hỗ trợ", "Hỗ trợ"}))
async def handle_reply_support(message: Message):
    await show_support_msg(message)

@router.message(F.text.in_({"💰 Bảo hành", "Bảo hành", "📜 Điều khoản", "Điều khoản", "📜 Điều khoản & Bảo hành"}))
async def handle_reply_warranty(message: Message):
    await show_warranty_msg(message)

@router.message(F.text.in_({"🌐 Ngôn ngữ", "Ngôn ngữ"}))
async def handle_reply_language(message: Message):
    await show_language_msg(message)

# ==============================================================================
# MENU THUÊ OTP & DANH SÁCH DỊCH VỤ (LOGO CHUẨN XÁC TỪNG APP)
# ==============================================================================
@router.callback_query(F.data == "u:rent_menu")
async def cb_rent_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = get_rent_menu_content()
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

async def cb_rent_menu_msg(message: Message, state: FSMContext):
    await state.clear()
    text, markup = get_rent_menu_content()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

def get_rent_menu_content() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"{ce('buy', '🛒')} <b>DANH MỤC THUÊ SIM OTP SMS TỰ ĐỘNG</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• Toàn bộ số điện thoại là SIM thật từ nhà mạng Việt Nam.\n"
        "• Cam kết <b>hoàn tiền 100%</b> vào ví nếu không nhận được mã OTP.\n"
        "• Nhận mã tự động sau 5 - 30 giây.\n\n"
        "👉 <i>Chạm vào ứng dụng bên dưới để vào phần nhận SMS OTP ngay:</i>"
    )
    markup = kb([
        [
            btn("🌐 Thuê PROXY", "u:proxy:static", icon=CUSTOM_EMOJIS.get("target"), style="success"),
            btn("🔄 PROXY XOAY VIP", "u:proxy:rotating", icon=CUSTOM_EMOJIS.get("fire"), style="success"),
        ],
        [btn("🔥 CÁC DỊCH VỤ ĐƯỢC THUÊ NHIỀU NHẤT", "u:hot_services", style="success")],
        [
            btn("Facebook", "u:rent_sid:95", icon=CUSTOM_EMOJIS.get("facebook"), style="success"),
            btn("Telegram", "u:rent_sid:97", icon=CUSTOM_EMOJIS.get("telegram"), style="success"),
            btn("TikTok", "u:rent_sid:48", icon=CUSTOM_EMOJIS.get("tiktok"), style="success"),
        ],
        [
            btn("Zalo", "u:rent_sid:70", icon=CUSTOM_EMOJIS.get("zalo"), style="success"),
            btn("Google", "u:rent_sid:93", icon=CUSTOM_EMOJIS.get("google"), style="success"),
            btn("Shopee", "u:rent_sid:49", icon=CUSTOM_EMOJIS.get("shopee"), style="success"),
        ],
        [
            btn("OpenAI", "u:rent_sid:88", icon=CUSTOM_EMOJIS.get("openai"), style="success"),
            btn("WhatsApp", "u:rent_sid:46", icon=CUSTOM_EMOJIS.get("whatsapp"), style="success"),
            btn("Apple", "u:rent_sid:29", icon=CUSTOM_EMOJIS.get("apple"), style="success"),
        ],
        [
            btn("Discord", "u:rent_sid:65", icon=CUSTOM_EMOJIS.get("discord"), style="success"),
            btn("Amazon", "u:rent_sid:32", icon=CUSTOM_EMOJIS.get("amazon"), style="success"),
            btn("MoMo", "u:rent_sid:60", icon=CUSTOM_EMOJIS.get("momo"), style="success"),
        ],
        [
            btn("Lazada", "u:rent_sid:90", icon=CUSTOM_EMOJIS.get("lazada"), style="success"),
            btn("Grab", "u:rent_sid:66", icon=CUSTOM_EMOJIS.get("grab"), style="success"),
            btn("OTP Khác", "u:rent_sid:47", icon=CUSTOM_EMOJIS.get("target"), style="success"),
        ],
        [btn("📋 Xem tất cả danh sách dịch vụ", "u:all_services:1", style="primary")],
        [btn("🔍 Tìm kiếm theo tên ứng dụng", "u:search_srv", style="primary")],
        [btn("« Quay lại Menu chính", "u:home")],
    ])
    return text, markup

@router.callback_query(F.data.startswith("u:rent_by_name:"))
async def cb_rent_by_name(cb: CallbackQuery):
    name = cb.data.split(":", 2)[2]
    conn = await db.get_connection()
    try:
        async with conn.execute("SELECT * FROM services WHERE is_active = 1 AND name LIKE ? LIMIT 1", (f"%{name}%",)) as cur:
            row = await cur.fetchone()
    finally:
        await conn.close()

    if row:
        await show_rent_detail(cb, row["id"])
    else:
        await cb.answer(f"Dịch vụ {name} đang được cập nhật thêm số mới.", show_alert=True)

@router.callback_query(F.data == "u:hot_services")
async def cb_hot_services(cb: CallbackQuery):
    conn = await db.get_connection()
    try:
        async with conn.execute("""
            SELECT id, name, server, selling_price, custom_emoji_id FROM services 
            WHERE is_active = 1 
            GROUP BY name
            ORDER BY CASE 
                WHEN name LIKE '%Facebook%' THEN 1
                WHEN name LIKE '%Telegram%' THEN 2
                WHEN name LIKE '%TikTok%' THEN 3
                WHEN name LIKE '%Zalo%' THEN 4
                WHEN name LIKE '%Google%' THEN 5
                WHEN name LIKE '%Shopee%' THEN 6
                WHEN name LIKE '%WhatsApp%' THEN 7
                WHEN name LIKE '%OpenAI%' THEN 8
                WHEN name LIKE '%Apple%' THEN 9
                ELSE 10 END, id ASC
            LIMIT 10
        """) as cur:
            services_list = [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    text = (
        f"{ce('fire', '🔥')} <b>TOP DỊCH VỤ THUÊ OTP ĐƯỢC DÙNG NHIỀU NHẤT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Tất cả số điện thoại đều có logo chuẩn từng ứng dụng • Chạm để thuê ngay:</i>"
    )
    rows = []
    for s in services_list:
        lbl = f"{s['name']} • {fmt_vnd(s['selling_price'])}"
        icon_id = s.get("custom_emoji_id") or get_brand_emoji_id(s["name"])
        rows.append([btn(lbl, f"u:rent_sid:{s['id']}", icon=icon_id, style="success")])

    rows.append([btn("🔍 Tìm kiếm dịch vụ khác", "u:search_srv", style="primary"), btn("« Menu", "u:rent_menu")])
    await cb.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("u:all_services:"))
async def cb_all_services(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    page_size = 8
    offset = (page - 1) * page_size

    conn = await db.get_connection()
    try:
        async with conn.execute("SELECT COUNT(*) as c FROM services WHERE is_active = 1") as cur:
            total_items = (await cur.fetchone())["c"]
        total_pages = max(1, math.ceil(total_items / page_size))
        page = min(page, total_pages)

        async with conn.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY name ASC LIMIT ? OFFSET ?", (page_size, offset)) as cur:
            services_list = [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    text = (
        f"📋 <b>TẤT CẢ DỊCH VỤ OTP (Trang {page}/{total_pages})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tổng cộng có <b>{total_items} dịch vụ</b> sẵn sàng nhận OTP:\n"
    )
    rows = []
    for s in services_list:
        lbl = f"{s['name']} ({s['server']}) — {fmt_vnd(s['selling_price'])}"
        icon_id = s.get("custom_emoji_id") or get_brand_emoji_id(s["name"])
        rows.append([btn(lbl, f"u:rent_sid:{s['id']}", icon=icon_id, style="success")])

    nav_row = []
    if page > 1:
        nav_row.append(btn("◀️ Trước", f"u:all_services:{page-1}"))
    nav_row.append(btn(f"Trang {page}/{total_pages}", "u:rent_menu"))
    if page < total_pages:
        nav_row.append(btn("Sau ▶️", f"u:all_services:{page+1}"))
    rows.append(nav_row)

    rows.append([btn("🔍 Tìm kiếm nhanh", "u:search_srv", style="primary"), btn("« Menu", "u:home")])
    await cb.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    await cb.answer()

# ==============================================================================
# XÁC NHẬN THUÊ VÀ TẠO PHIÊN NHẬN SMS OTP
# ==============================================================================
@router.callback_query(F.data.startswith("u:rent_sid:"))
async def cb_rent_detail(cb: CallbackQuery):
    try:
        sid = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        return await cb.answer("⚠️ Mã dịch vụ không hợp lệ.", show_alert=True)
    await show_rent_detail(cb, sid)

async def show_rent_detail(cb: CallbackQuery, sid: int):
    try:
        uid = cb.from_user.id
        user = await db.get_or_create_user(uid)

        srv = await db.get_service_by_id(sid)
        if not srv or not srv.get("is_active"):
            return await cb.answer("⚠️ Dịch vụ hiện đang bảo trì hoặc tạm hết số.", show_alert=True)

        price = srv["selling_price"]
        bal = user["balance"]
        is_enough = bal >= price

        brand_icon = srv.get("custom_emoji_id") or get_brand_emoji_id(srv["name"])
        icon_tag = f'<tg-emoji emoji-id="{brand_icon}">📱</tg-emoji> ' if brand_icon else "📱 "

        text = (
            f"⚡️ <b>DỊCH VỤ NHẬN SMS OTP: {icon_tag}<b>{esc(srv['name'])}</b></b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Cụm máy chủ: <code>{esc(srv['server'])}</code>\n"
            f"• Thời hạn giữ SIM: <b>{srv['timeout_minutes']} phút</b>\n"
            f"• Cước phí trọn gói: <b>{fmt_vnd(price)}</b>\n"
            f"• Số dư ví của bạn: <b>{fmt_vnd(bal)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        if is_enough:
            text += (
                "📶 <b>Trạng thái:</b> Sẵn sàng cấp số điện thoại thật và nhận mã SMS!\n"
                "🛡 <b>Cam kết uy tín:</b> Chỉ trừ tiền khi có SMS thật. Quá hạn tự động hoàn 100% tiền vào ví!\n\n"
                "👉 <i>Bấm nút bên dưới để lấy số điện thoại và chờ mã SMS ngay:</i>"
            )
            markup = kb([
                [btn(f"⚡️ LẤY SỐ & NHẬN SMS NGAY ({fmt_vnd(price)})", f"u:confirm_rent:{sid}", icon=brand_icon, style="success")],
                [btn("« Chọn dịch vụ khác", "u:rent_menu")],
            ])
        else:
            diff = price - bal
            text += (
                f"⚠️ <b>Số dư ví không đủ!</b> Bạn còn thiếu <b>{fmt_vnd(diff)}</b> để nhận SMS dịch vụ này.\n"
                f"👉 <i>Vui lòng nạp tiền vào ví qua VietQR tự động để lấy số ngay (Tối thiểu 50.000đ):</i>"
            )
            markup = kb([
                [btn(f"💰 Nạp tiền vào ví ngay (Thiếu {fmt_vnd(diff)})", "u:deposit", style="success")],
                [btn("« Chọn dịch vụ khác", "u:rent_menu")],
            ])

        try:
            await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    finally:
        try:
            await cb.answer()
        except Exception:
            pass

@router.callback_query(F.data.startswith("u:confirm_rent:"))
async def cb_confirm_rent(cb: CallbackQuery, bot: Bot):
    sid = int(cb.data.split(":")[2])
    uid = cb.from_user.id
    user = await db.get_or_create_user(uid)

    await cb.answer("⏳ Đang lấy SIM thật từ nhà mạng...")
    try:
        await cb.message.delete()
    except Exception:
        pass

    success, msg, ord_data = await services.rent_otp_service(bot, user, sid, cb.message.chat.id)
    if not success:
        await cb.message.answer(
            f"❌ <b>KHÔNG THỂ THUÊ SỐ:</b>\n{msg}",
            reply_markup=kb([[btn("🔄 Thử lại", f"u:rent_sid:{sid}"), btn("« Menu", "u:home")]]),
            parse_mode="HTML"
        )

# ==============================================================================
# CHỨC NĂNG THUÊ LẠI SỐ ĐÃ SỬ DỤNG TRƯỚC ĐÓ (RERENT NUMBER)
# ==============================================================================
@router.callback_query(F.data.startswith("u:rerent:"))
async def cb_rerent_order(cb: CallbackQuery, bot: Bot):
    oid = cb.data.split(":")[2]
    uid = cb.from_user.id
    user = await db.get_or_create_user(uid)

    await cb.answer("⏳ Đang gửi yêu cầu thuê lại số cũ đến nhà mạng...")
    try:
        await cb.message.delete()
    except Exception:
        pass

    success, msg, ord_data = await services.rerent_otp_service(bot, user, oid, cb.message.chat.id)
    if not success:
        await cb.message.answer(
            f"⚠️ <b>KHÔNG THỂ THUÊ LẠI SỐ:</b>\n{msg}",
            reply_markup=kb([[btn("⚡️ Thuê số mới", "u:rent_menu", style="success"), btn("« Menu", "u:home")]]),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("u:cancel_order:"))
async def cb_cancel_order(cb: CallbackQuery, bot: Bot):
    oid = cb.data.split(":")[2]
    uid = cb.from_user.id
    success, msg = await services.user_cancel_order(bot, oid, uid)
    if success:
        await cb.answer(msg, show_alert=True)
        try:
            await cb.message.edit_text(
                f"❌ <b>ĐÃ HỦY ĐƠN HÀNG #{oid}</b>\n\n"
                f"{msg}\n\n"
                f"👉 Số dư của bạn đã được hoàn trả 100% vào ví ngay lập tức.",
                reply_markup=kb([[btn("⚡️ Thuê số mới", "u:rent_menu", style="success"), btn("« Menu chính", "u:home")]]),
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        await cb.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("u:recheck:"))
async def cb_recheck_order(cb: CallbackQuery, bot: Bot):
    oid = cb.data.split(":")[2]
    order = await db.get_order_by_id(oid)
    if not order:
        return await cb.answer("Không tìm thấy đơn hàng.", show_alert=True)

    if order["status"] == "SUCCESS":
        text, markup = ui.render_order_success_card(order)
        try:
            await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
        return await cb.answer("Mã OTP đã về thành công!", show_alert=True)

    if order["status"] in ("TIMEOUT", "CANCELED"):
        return await cb.answer(f"Đơn hàng này đã kết thúc ({order['status']}).", show_alert=True)

    await cb.answer("Đang tiếp tục đợi tin nhắn SMS từ hệ thống...", show_alert=False)

@router.callback_query(F.data.startswith("u:copy_otp:"))
async def cb_copy_otp(cb: CallbackQuery):
    otp = cb.data.split(":", 2)[2]
    await cb.answer(f"Đã sao chép: {otp}", show_alert=True)

# ==============================================================================
# TÌM KIẾM DỊCH VỤ
# ==============================================================================
@router.callback_query(F.data == "u:search_srv")
async def cb_search_service(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UserSearchState.waiting_for_keyword)
    text = (
        "🔍 <b>TÌM KIẾM DỊCH VỤ THUÊ OTP</b>\n\n"
        "Vui lòng nhập tên ứng dụng bạn muốn tìm kiếm (Ví dụ: <code>Facebook</code>, <code>Telegram</code>, <code>TikTok</code>, <code>Zalo</code>):"
    )
    markup = kb([[btn("« Quay lại Menu", "u:rent_menu")]])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(UserSearchState.waiting_for_keyword)
async def handle_search_keyword(message: Message, state: FSMContext):
    kw = message.text.strip()
    await state.clear()

    conn = await db.get_connection()
    try:
        async with conn.execute(
            "SELECT * FROM services WHERE is_active = 1 AND name LIKE ? ORDER BY name ASC LIMIT 10",
            (f"%{kw}%",)
        ) as cur:
            results = [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    if not results:
        return await message.answer(
            f"❌ Không tìm thấy dịch vụ nào phù hợp với từ khóa '<b>{esc(kw)}</b>'.",
            reply_markup=kb([[btn("🔍 Tìm từ khóa khác", "u:search_srv"), btn("« Menu", "u:rent_menu")]]),
            parse_mode="HTML"
        )

    text = f"🔍 <b>KẾT QUẢ TÌM KIẾM CHO:</b> '<b>{esc(kw)}</b>'\n━━━━━━━━━━━━━━━━━━━━\n"
    rows = []
    for s in results:
        lbl = f"{s['name']} — {fmt_vnd(s['selling_price'])}"
        icon_id = s.get("custom_emoji_id") or get_brand_emoji_id(s["name"])
        rows.append([btn(lbl, f"u:rent_sid:{s['id']}", icon=icon_id, style="success")])

    rows.append([btn("🔍 Tìm kiếm khác", "u:search_srv", style="primary"), btn("« Menu", "u:rent_menu")])
    await message.answer(text, reply_markup=kb(rows), parse_mode="HTML")

# ==============================================================================
# MENU NẠP TIỀN VÍ & TẠO QR BANK TỰ ĐỘNG (MIN 50.000đ)
# ==============================================================================
@router.callback_query(F.data == "u:deposit")
async def cb_deposit(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    user = await db.get_or_create_user(uid)
    min_dep = await db.get_min_deposit()
    text, markup = ui.render_deposit_amount_selection(user, min_dep)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

async def show_deposit_msg(message: Message):
    uid = message.from_user.id
    user = await db.get_or_create_user(uid)
    min_dep = await db.get_min_deposit()
    text, markup = ui.render_deposit_amount_selection(user, min_dep)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("dep_amt:"))
async def cb_deposit_amount_picked(cb: CallbackQuery, state: FSMContext):
    val_str = cb.data.split(":")[1]
    min_dep = await db.get_min_deposit()
    
    if val_str == "custom":
        await state.set_state(DepositState.waiting_for_amount)
        text = (
            "✏️ <b>NHẬP SỐ TIỀN BẠN MUỐN NẠP (VNĐ)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"• Mức nạp tối thiểu: <b>{fmt_vnd(min_dep)}</b>\n"
            f"• Bạn có thể gõ số tiền (VD: <code>{min_dep}</code> hoặc <code>100k</code>, <code>200k</code>, <code>1m</code>)\n\n"
            "👉 <b>Hãy gửi tin nhắn chứa số tiền muốn nạp vào đây:</b>"
        )
        markup = kb([[btn("« Quay lại chọn mức nạp", "u:deposit")]])
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        return await cb.answer()

    amount = int(val_str)
    if amount < min_dep:
        return await cb.answer(f"⚠️ Mức nạp tối thiểu là {fmt_vnd(min_dep)}!", show_alert=True)

    await cb.answer("⏳ Đang tạo mã VietQR theo số tiền...")
    await send_dynamic_bank_qr(cb.message, cb.from_user.id, amount, is_edit=True)

@router.message(DepositState.waiting_for_amount)
async def handle_custom_deposit_amount(message: Message, state: FSMContext):
    raw_text = message.text.strip().lower().replace(",", "").replace(".", "").replace("đ", "").replace("vnd", "")
    min_dep = await db.get_min_deposit()
    
    if raw_text.endswith("k"):
        num_part = raw_text[:-1]
        amount = int(float(num_part) * 1_000) if num_part.replace(".", "").isdigit() else 0
    elif raw_text.endswith("m"):
        num_part = raw_text[:-1]
        amount = int(float(num_part) * 1_000_000) if num_part.replace(".", "").isdigit() else 0
    elif raw_text.isdigit():
        amount = int(raw_text)
    else:
        return await message.answer(
            "⚠️ <b>Số tiền không hợp lệ!</b>\n"
            f"Vui lòng nhập số tiền từ <b>{fmt_vnd(min_dep)}</b> trở lên (Ví dụ: <code>{min_dep}</code> hoặc <code>100k</code>):",
            parse_mode="HTML"
        )

    if amount < min_dep:
        return await message.answer(
            f"⚠️ <b>Số tiền nạp tối thiểu là {fmt_vnd(min_dep)}!</b> (Bạn vừa nhập {fmt_vnd(amount)}).\n"
            f"👉 Vui lòng nhập lại số tiền từ <b>{fmt_vnd(min_dep)}</b> trở lên:",
            parse_mode="HTML"
        )

    await state.clear()
    await send_dynamic_bank_qr(message, message.from_user.id, amount, is_edit=False)

async def send_dynamic_bank_qr(target_msg: Message, user_id: int, amount: int, is_edit: bool = False):
    """Gửi QR MoMo của Admin kèm số tiền và nội dung chuyển khoản."""
    import os
    from aiogram.types import FSInputFile
    memo = f"NAP {user_id}"
    caption = (
        f"{ce('momo', '💖')} <b>NẠP TIỀN QUA MOMO: {fmt_vnd(amount)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Chủ tài khoản: <b>NGUYEN LE HOANG NHAT</b>\n"
        f"💵 Số tiền cần chuyển: <b>{fmt_vnd(amount)}</b>\n"
        f"📝 Nội dung chuyển khoản: <code>{memo}</code> <i>(Bắt buộc, chạm để copy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>HƯỚNG DẪN:</b>\n"
        f"1. Mở app MoMo hoặc app ngân hàng → <b>Quét mã QR</b> phía trên.\n"
        f"2. Nhập đúng số tiền <b>{fmt_vnd(amount)}</b> và nội dung <code>{memo}</code>.\n"
        f"3. Chuyển xong bấm <b>✅ Tôi đã chuyển khoản</b> để Admin duyệt và cộng tiền. Cần hỗ trợ: @{SUPPORT_USERNAME}"
    )
    markup = kb([
        [btn("✅ Tôi đã chuyển khoản", f"dep_paid:{amount}", style="success")],
        [btn("🔄 Kiểm tra số dư ví", "u:profile", style="success")],
        [btn("💵 Chọn số tiền khác", "u:deposit", style="primary")],
        [btn("💬 Hỗ trợ CSKH", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [btn("« Menu chính", "u:home")],
    ])

    if is_edit:
        try:
            await target_msg.delete()
        except Exception:
            pass

    qr_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "momo_qr.jpg")
    await target_msg.answer_photo(
        photo=FSInputFile(qr_path),
        caption=caption,
        reply_markup=markup,
        parse_mode="HTML"
    )

async def _old_send_dynamic_bank_qr(target_msg: Message, user_id: int, amount: int, is_edit: bool = False):
    bank_name = await db.get_config("bank_name", "MBBANK")
    bank_acc = await db.get_config("bank_acc", "0987654321")
    bank_owner = await db.get_config("bank_owner", "NGUYEN VAN A")

    qr_url, caption, markup = ui.render_deposit_qr_card(user_id, amount, bank_name, bank_acc, bank_owner)
    
    if is_edit:
        try:
            await target_msg.delete()
        except Exception:
            pass

    await target_msg.answer_photo(
        photo=qr_url,
        caption=caption,
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==============================================================================
# CÁC MỤC THÔNG TIN HỆ THỐNG
# ==============================================================================
@router.callback_query(F.data == "u:profile")
async def cb_profile(cb: CallbackQuery):
    await show_profile_msg(cb.message, cb.from_user.id, is_edit=True)
    await cb.answer()

async def show_profile_msg(target: Message, uid: int = None, is_edit: bool = False):
    user_id = uid or target.from_user.id
    uname = target.from_user.username or target.from_user.full_name
    user = await db.get_or_create_user(user_id, uname)

    conn = await db.get_connection()
    try:
        async with conn.execute("SELECT COUNT(*) as c FROM orders WHERE user_id = ? AND status = 'SUCCESS'", (user_id,)) as cur:
            succ_orders = (await cur.fetchone())["c"]
    finally:
        await conn.close()

    text = (
        f"{ce('profile', '👤')} <b>HỒ SƠ TÀI KHOẢN NGƯỜI DÙNG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• ID Telegram: <code>{user_id}</code>\n"
        f"• Tên khách hàng: <b>{esc(uname)}</b>\n"
        f"• Số dư ví hiện có: <b>{fmt_vnd(user['balance'])}</b>\n"
        f"• Tổng tiền đã tiêu: <b>{fmt_vnd(user['total_spent'])}</b>\n"
        f"• Đơn thuê OTP thành công: <b>{succ_orders} lần</b>\n"
        f"• Ngày đăng ký: <code>{user['created_at']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    markup = kb([
        [btn("💰 Nạp tiền vào ví (Từ 50k)", "u:deposit", style="success")],
        [btn("📜 Lịch sử mua hàng", "u:history", style="success")],
        [btn("« Quay lại Menu chính", "u:home")],
    ])
    if is_edit:
        try:
            await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    await target.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "u:history")
async def cb_history(cb: CallbackQuery):
    await show_history_msg(cb.message, cb.from_user.id, is_edit=True)
    await cb.answer()

async def show_history_msg(target: Message, uid: int = None, is_edit: bool = False):
    user_id = uid or target.from_user.id
    orders = await db.get_completed_orders_for_user(user_id, limit=6)

    if not orders:
        txt_empty = "📜 <b>LỊCH SỬ THUÊ OTP:</b>\n\nBạn chưa có đơn thuê số nào. Hãy bấm <b>Thuê OTP ngay</b> để trải nghiệm!"
        mk = kb([[btn("⚡️ Thuê số mới ngay", "u:rent_menu", style="success"), btn("« Menu chính", "u:home")]])
        if is_edit:
            return await target.edit_text(txt_empty, reply_markup=mk, parse_mode="HTML")
        return await target.answer(txt_empty, reply_markup=mk, parse_mode="HTML")

    text = f"{ce('history', '🧿')} <b>LỊCH SỬ THUÊ OTP GẦN ĐÂY:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    status_icons = {"SUCCESS": "✅ Thành công", "TIMEOUT": "⏱ Hết hạn (Đã hoàn tiền)", "CANCELED": "❌ Đã hủy (Đã hoàn tiền)", "WAITING": "⏳ Đang chờ"}
    
    rows = []
    for o in orders:
        st_text = status_icons.get(o["status"], o["status"])
        otp_str = f" | OTP: <code>{o['otp_code']}</code>" if o.get("otp_code") else ""
        rerent_tag = " [Thuê lại]" if o.get("is_rerent") else ""
        text += (
            f"• <b>{esc(o['service_name'])}{rerent_tag}</b> (#{o['order_id']})\n"
            f"  Số: <code>{o['phone_number']}</code>{otp_str}\n"
            f"  Cước: {fmt_vnd(o['selling_price'])} | {st_text}\n"
            f"  Thời gian: <code>{o['created_at']}</code>\n\n"
        )
        if o.get("phone_number"):
            rows.append([btn(f"🔄 Thuê lại số: {o['phone_number']}", f"u:rerent:{o['order_id']}", style="success")])

    rows.append([btn("⚡️ Thuê số mới", "u:rent_menu", style="primary"), btn("« Menu chính", "u:home")])
    markup = kb(rows)

    if is_edit:
        try:
            return await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await target.answer(text, reply_markup=markup, parse_mode="HTML")

# ==============================================================================
# QUẢN LÝ MUA BÁN PROXY & PROXY XOAY VIP (TÍCH HỢP HUPSMS)
# ==============================================================================
@router.callback_query(F.data.startswith("u:proxy:"))
async def cb_proxy_catalog(cb: CallbackQuery):
    ptype = cb.data.split(":")[2]
    user = await db.get_or_create_user(cb.from_user.id)
    pkgs = await db.get_proxy_packages(ptype)
    text, markup = ui.render_proxy_catalog(pkgs, ptype, user.get("balance", 0))
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("u:prx_dtl:"))
async def cb_proxy_detail(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    pkg = await db.get_proxy_package_by_id(pid)
    if not pkg:
        return await cb.answer("Gói Proxy không tồn tại hoặc đã ngừng cung cấp.", show_alert=True)
    user = await db.get_or_create_user(cb.from_user.id)
    text, markup = ui.render_proxy_package_detail(pkg, user.get("balance", 0))
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("u:prx_buy:"))
async def cb_buy_proxy(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    uid = cb.from_user.id
    pkg = await db.get_proxy_package_by_id(pid)
    if not pkg:
        return await cb.answer("Gói Proxy không tồn tại.", show_alert=True)

    user = await db.get_or_create_user(uid)
    price = pkg["selling_price"]
    if user.get("balance", 0) < price:
        diff = price - user.get("balance", 0)
        return await cb.answer(f"Số dư ví không đủ (thiếu {fmt_vnd(diff)}). Vui lòng nạp thêm tiền!", show_alert=True)

    await cb.answer("⏳ Đang kết nối cổng HupSMS và khởi tạo Proxy...")
    
    # 1. Gọi API HupSMS mua / cấp proxy
    ok, p_data, r_url, msg = await sms_client.buy_proxy(pkg)
    if not ok or not p_data:
        return await cb.answer(f"❌ Không thể mua Proxy: {msg}", show_alert=True)

    # 2. Khấu trừ tiền ví và lưu đơn hàng qua ACID transaction
    success, order_msg, order_data = await db.create_proxy_order_record(uid, pkg, p_data, r_url)
    if not success or not order_data:
        return await cb.answer(f"❌ Lỗi thanh toán: {order_msg}", show_alert=True)

    # 3. Trả kết quả giao diện bàn giao Proxy
    text, markup = ui.render_proxy_order_success(order_data)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "u:my_proxies")
async def cb_my_proxies(cb: CallbackQuery):
    uid = cb.from_user.id
    orders = await db.get_user_proxy_orders(uid, limit=10)
    text, markup = ui.render_my_proxies(orders)
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(F.text.in_({"🌐 Thuê PROXY", "Thuê PROXY", "Proxy", "proxy"}))
async def handle_text_proxy_static(message: Message):
    user = await db.get_or_create_user(message.from_user.id)
    pkgs = await db.get_proxy_packages("static")
    text, markup = ui.render_proxy_catalog(pkgs, "static", user.get("balance", 0))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.message(F.text.in_({"🔄 PROXY XOAY VIP", "PROXY XOAY VIP", "Proxy xoay", "proxy xoay"}))
async def handle_text_proxy_rotating(message: Message):
    user = await db.get_or_create_user(message.from_user.id)
    pkgs = await db.get_proxy_packages("rotating")
    text, markup = ui.render_proxy_catalog(pkgs, "rotating", user.get("balance", 0))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "u:api_docs")
async def cb_api_docs(cb: CallbackQuery):
    await show_api_msg(cb.message, is_edit=True)
    await cb.answer()

async def show_api_msg(target: Message, is_edit: bool = False):
    text = (
        f"{ce('api', '🔗')} <b>KẾT NỐI API & TỰ ĐỘNG HÓA MMO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• Hệ thống hỗ trợ tích hợp API cho các công cụ auto, phần mềm reg nick, tool nuôi tài khoản.\n"
        "• Cung cấp Webhook / Polling tự động lấy số và nhận mã tức thì.\n"
        "• Tỷ lệ nhận mã cao, hỗ trợ đa luồng tốc độ cao.\n\n"
        f"👉 Để cấp quyền API Key và tài liệu tích hợp riêng, vui lòng liên hệ Admin: @{SUPPORT_USERNAME}"
    )
    markup = kb([[btn("💬 Nhắn tin nhận API Key", url=f"https://t.me/{SUPPORT_USERNAME}"), btn("« Menu", "u:home")]])
    if is_edit:
        try:
            return await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await target.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "u:warranty")
async def cb_warranty(cb: CallbackQuery):
    await show_warranty_msg(cb.message, is_edit=True)
    await cb.answer()

async def show_warranty_msg(target: Message, is_edit: bool = False):
    text = (
        f"{ce('warranty', '📜')} <b>ĐIỀU KHOẢN SỬ DỤNG & CHÍNH SÁCH BẢO HÀNH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📜 <b>ĐIỀU KHOẢN SỬ DỤNG:</b>\n"
        "• Nghiêm cấm các hành vì lừa đảo, sử dụng cho mục đích vi phạm pháp luật, lọc tài khoản cũ, spam lọc số không nhận mã, tạo nhiều tài khoản khác nhau lợi dụng (chúng tôi sẽ khóa tài khoản vĩnh viễn không cần cảnh báo)\n\n"
        "• Khi thuê sim, bạn cũng đang đồng ý với việc chấp nhận rủi ro vì dịch vụ sim gửi/nhận SMS không may có thể bị nhà mạng chặn/dính vào mục spam, suy ra việc gửi hoặc nhận tin nhắn có thể sẽ thất bại!\n\n"
        "• Sử dụng mục tìm kiếm để sử dụng dịch vụ bạn cần, bạn có thể thử nhiều kho để chọn dịch vụ nhận mã tốt nhất. Hệ thống chỉ có nhiệm vụ trả tin nhắn đúng nội dung nhận được, vui lòng lưu ý.\n\n"
        "• Số SIM có thể bị trùng dịch vụ bạn dùng, bạn vui lòng thuê số khác hoặc chọn dịch vụ khác, số bạn không sử dụng sẽ hoàn tiền vào tài khoản của bạn ngay khi hết thời gian thuê số.\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>CHÍNH SÁCH BẢO HÀNH & HOÀN TIỀN:</b>\n"
        "• <b>Hoàn tiền 100% tự động:</b> Trong thời gian giữ số (5 phút), nếu hệ thống không nhận được tin nhắn SMS chứa mã OTP, tiền cước sẽ được hoàn trả 100% về ví số dư ngay lập tức.\n"
        "• <b>Chủ động hủy số:</b> Bạn có thể bấm nút 'Hủy thuê & Hoàn tiền' bất cứ lúc nào nếu số bị trùng hoặc không muốn dùng nữa."
    )
    markup = kb([[btn("« Quay lại Menu chính", "u:home")]])
    if is_edit:
        try:
            return await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await target.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "u:language")
async def cb_language(cb: CallbackQuery):
    await show_language_msg(cb.message, is_edit=True)
    await cb.answer()

async def show_language_msg(target: Message, is_edit: bool = False):
    text = (
        f"{ce('language', '🌐')} <b>CHỌN NGÔN NGỮ / SELECT LANGUAGE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Hiện tại hệ thống đang hỗ trợ mặc định giao diện Tiếng Việt."
    )
    markup = kb([
        [btn("🇻🇳 Tiếng Việt (Mặc định)", "u:home", style="success")],
        [btn("« Menu chính", "u:home")]
    ])
    if is_edit:
        try:
            return await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    await target.answer(text, reply_markup=markup, parse_mode="HTML")
