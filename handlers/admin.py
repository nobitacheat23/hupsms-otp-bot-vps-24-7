from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import db
import ui
from ui import btn, kb, esc, fmt_vnd
from config import ADMIN_IDS, is_admin as cfg_is_admin
from hupsms_client import sms_client, calculate_markup_price

router = Router(name="admin")

def is_admin(user_id: int, username: str = None) -> bool:
    return cfg_is_admin(user_id, username)

class AdminPriceState(StatesGroup):
    waiting_for_price = State()

class AdminMarkupState(StatesGroup):
    waiting_for_markup = State()

class AdminMinDepositState(StatesGroup):
    waiting_for_amount = State()

class AdminProxyPriceState(StatesGroup):
    package_id = State()
    waiting_for_price = State()

class AdminProviderState(StatesGroup):
    waiting_for_type = State()
    waiting_for_name = State()
    waiting_for_url = State()
    waiting_for_key = State()

# ==============================================================================
# DASHBOARD ADMIN
# ==============================================================================
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Bạn không có quyền truy cập bảng quản trị.")
    
    text, markup = await get_admin_dashboard_content()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "adm:dashboard")
async def cb_adm_dashboard(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    
    text, markup = await get_admin_dashboard_content()
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

async def get_admin_dashboard_content():
    stats = await db.get_system_stats()
    markup = await db.get_config("markup_amount", "1500")
    timeout_cfg = await db.get_config("order_timeout_seconds", "300")
    min_dep = await db.get_min_deposit()
    proxy_mult = await db.get_proxy_multiplier()
    b_name = await db.get_config("bank_name", "MBBANK")
    b_acc = await db.get_config("bank_acc", "0987654321")
    b_owner = await db.get_config("bank_owner", "NGUYEN VAN A")
    providers = await db.get_api_providers()

    p_list_str = ", ".join([f"{p['name']} ({'BẬT' if p['is_active'] else 'TẮT'})" for p in providers]) or "Chưa cấu hình"

    # Kiểm tra số dư tài khoản web HupSMS
    bal_ok, hup_bal, _ = await sms_client.get_provider_balance(1)
    if bal_ok:
        if hup_bal > 0:
            hup_bal_str = f"<b>{fmt_vnd(hup_bal)}</b> ✅"
        else:
            hup_bal_str = "<b>0đ</b> ⚠️ <i>(Cần nạp tiền trên web hupsms.com)</i>"
    else:
        hup_bal_str = "<i>Đang kết nối API...</i>"

    text = (
        "⚙️ <b>BẢNG QUẢN TRỊ VIÊN HỆ THỐNG OTP & PROXY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Số dư API HupSMS: {hup_bal_str}\n"
        f"👥 Tổng thành viên: <b>{stats['total_users']:,} người</b>\n"
        f"👛 Tổng số dư ví khách: <b>{fmt_vnd(stats['total_user_balance'])}</b>\n"
        f"💰 Tổng doanh thu tích lũy: <b>{fmt_vnd(stats['total_revenue'])}</b>\n"
        f"✅ Đơn thành công: <b>{stats['success_orders']:,}</b> | ⏳ Đang chờ: <b>{stats['waiting_orders']}</b>\n"
        f"📱 Dịch vụ OTP mở: <b>{stats['active_services']:,} nền tảng</b>\n"
        f"🔌 API kết nối ({len(providers)}/3): <b>{esc(p_list_str)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Tiền lãi OTP SMS: <b>+{int(markup):,}đ/tin</b>\n"
        f"💵 Mức nạp tối thiểu (Min Nạp): <b>{fmt_vnd(min_dep)}</b>\n"
        f"🌐 Hệ số giá Proxy: <b>x{proxy_mult}</b> (Mặc định đắt gấp đôi)\n"
        f"⏱ Thời gian chờ OTP: <b>{timeout_cfg} giây (5 phút)</b>\n"
        f"🏦 Ngân hàng nạp: <b>{b_name} - {b_acc} ({b_owner})</b>\n\n"
        "💡 <b>LỆNH QUẢN TRỊ NHANH:</b>\n"
        "• <code>/setmindeposit [số_tiền]</code>: Đổi mức nạp tối thiểu (VD: /setmindeposit 20000)\n"
        "• <code>/setproxyprice [id_gói] [giá]</code>: Tự chỉnh giá gói Proxy\n"
        "• <code>/setproxymultiplier [hệ_số]</code>: Đổi hệ số giá Proxy (VD: 2.0 hoặc 2.5)\n"
        "• <code>/setprice [id_dịch_vụ] [giá]</code>: Tự set giá OTP riêng\n"
        "• <code>/setmarkup [số_tiền]</code>: Đổi tiền lãi OTP chung\n"
        "• <code>/addbal [user_id] [tiền]</code>: Cộng tiền ví cho khách\n"
        "• <code>/subbal [user_id] [tiền]</code>: Trừ tiền khách\n"
        "• <code>/sync</code>: Đồng bộ tất cả dịch vụ từ các cổng API"
    )
    markup_kb = kb([
        [btn("💰 Duyệt nạp tiền chờ xử lý", "adm:deposits", style="success")],
        [btn("💵 Chỉnh Mức Nạp Tối Thiểu (Min Nạp)", "adm:set_mindeposit", style="primary"), btn("🌐 Quản Lý PROXY & Giá Bán", "adm:manage_proxies", style="primary")],
        [btn("📈 Tự điều chỉnh lãi OTP (Nhập số bất kỳ)", "adm:markup_custom", style="success")],
        [btn("🔄 Đồng bộ tất cả dịch vụ (All API)", "adm:sync_srv", style="primary")],
        [btn("🔌 Quản lý API Nguồn (Tối đa 3)", "adm:providers", style="primary"), btn("⚙️ Tự Set Giá Dịch Vụ OTP", "adm:prices:1", style="primary")],
        [btn("📈 Lãi OTP (+1.500đ)", "adm:markup:1500"), btn("📈 Lãi OTP (+2.000đ)", "adm:markup:2000")],
        [btn("« Về Menu người dùng", "u:home")],
    ])
    return text, markup_kb

# ==============================================================================
# QUẢN LÝ CỔNG API NGUỒN (TỐI ĐA 3 API)
# ==============================================================================
@router.callback_query(F.data == "adm:providers")
async def cb_adm_providers(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    
    providers = await db.get_api_providers()
    text = (
        "🔌 <b>QUẢN LÝ CỔNG API NGUỒN CHO THUÊ SIM (TỐI ĐA 3 WEB)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Hệ thống cho phép đấu nối tối đa 3 API từ các web khác nhau (HupSMS, ViOTP, ChoThueSimCode...).\n"
        "Khi người dùng thuê số, hệ thống sẽ tự động gọi API tương ứng với kết quả SMS thật 100%.\n\n"
    )
    
    rows = []
    for i, p in enumerate(providers, 1):
        status_txt = "🟢 Đang BẬT" if p["is_active"] else "🔴 Đang TẮT"
        key_masked = p["api_key"][:6] + "..." + p["api_key"][-4:] if len(p["api_key"]) > 10 else "***"
        text += (
            f"<b>{i}. {esc(p['name'])}</b> ({esc(p['api_type'].upper())})\n"
            f"• Base URL: <code>{esc(p['base_url'])}</code>\n"
            f"• API Key: <code>{esc(key_masked)}</code>\n"
            f"• Trạng thái: <b>{status_txt}</b>\n\n"
        )
        togg_lbl = f"Tắt #{p['id']}" if p["is_active"] else f"Bật #{p['id']}"
        row = [btn(f"🔄 {togg_lbl}", f"adm:prov_togg:{p['id']}", style="primary")]
        if len(providers) > 1:
            row.append(btn(f"🗑️ Xóa #{p['id']}", f"adm:prov_del:{p['id']}", style="danger"))
        rows.append(row)

    if len(providers) < 3:
        rows.append([btn("➕ Thêm API Web mới", "adm:prov_add", style="success")])
    
    rows.append([btn("🔄 Đồng bộ dịch vụ ngay", "adm:sync_srv", style="success")])
    rows.append([btn("« Quay lại Admin Dashboard", "adm:dashboard")])

    await cb.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("adm:prov_togg:"))
async def cb_prov_toggle(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    await db.toggle_api_provider(pid)
    await cb.answer("Đã thay đổi trạng thái hoạt động của cổng API!", show_alert=True)
    await cb_adm_providers(cb, None)

@router.callback_query(F.data.startswith("adm:prov_del:"))
async def cb_prov_del(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    await db.delete_api_provider(pid)
    await cb.answer("Đã xóa cổng API thành công!", show_alert=True)
    await cb_adm_providers(cb, None)

@router.callback_query(F.data == "adm:prov_add")
async def cb_prov_add(cb: CallbackQuery, state: FSMContext):
    providers = await db.get_api_providers()
    if len(providers) >= 3:
        return await cb.answer("Đã đạt giới hạn tối đa 3 API!", show_alert=True)
    
    text = (
        "➕ <b>THÊM CỔNG API CHO THUÊ SIM MỚI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Bước 1: Vui lòng chọn <b>Loại cấu trúc API</b> của website bạn muốn tích hợp:"
    )
    markup = kb([
        [btn("1. Chuẩn HupSMS (Bearer / api_key)", "adm:add_type:hupsms", style="success")],
        [btn("2. Chuẩn ViOTP (token)", "adm:add_type:viotp", style="success")],
        [btn("3. Chuẩn ChoThueSimCode (api_key)", "adm:add_type:chothuesimcode", style="success")],
        [btn("4. Chuẩn Generic REST", "adm:add_type:generic", style="primary")],
        [btn("« Hủy", "adm:providers")],
    ])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("adm:add_type:"))
async def cb_prov_add_type(cb: CallbackQuery, state: FSMContext):
    atype = cb.data.split(":")[2]
    await state.update_data(api_type=atype)
    await state.set_state(AdminProviderState.waiting_for_name)
    
    await cb.message.edit_text(
        f"📝 <b>Đã chọn loại API: {atype.upper()}</b>\n\n"
        "👉 <b>Bước 2:</b> Vui lòng gửi <b>Tên đại diện</b> của web (Ví dụ: <code>ViOTP Server 1</code> hoặc <code>ChoThueSimCode VIP</code>):",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminProviderState.waiting_for_name)
async def msg_prov_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(AdminProviderState.waiting_for_url)
    await message.answer(
        f"🌐 <b>Tên: {esc(name)}</b>\n\n"
        "👉 <b>Bước 3:</b> Vui lòng gửi <b>Base URL</b> của API web đó:\n"
        "(Ví dụ: <code>https://api.viotp.com</code> hoặc <code>https://chothuesimcode.com/api</code>):",
        parse_mode="HTML"
    )

@router.message(AdminProviderState.waiting_for_url)
async def msg_prov_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.answer("⚠️ URL phải bắt đầu bằng http:// hoặc https://. Vui lòng nhập lại:")
    
    await state.update_data(base_url=url)
    await state.set_state(AdminProviderState.waiting_for_key)
    await message.answer(
        f"🔑 <b>URL: {esc(url)}</b>\n\n"
        "👉 <b>Bước 4:</b> Vui lòng gửi <b>API Key / Token</b> kết nối của tài khoản bạn trên web đó:",
        parse_mode="HTML"
    )

@router.message(AdminProviderState.waiting_for_key)
async def msg_prov_key(message: Message, state: FSMContext):
    key = message.text.strip()
    data = await state.get_data()
    await state.clear()

    ok, msg, pid = await db.add_api_provider(
        name=data["name"],
        base_url=data["base_url"],
        api_key=key,
        api_type=data["api_type"]
    )
    if ok:
        await message.answer(
            f"🎉 <b>THÊM API WEB THÀNH CÔNG!</b>\n\n"
            f"• Tên: <b>{esc(data['name'])}</b>\n"
            f"• Loại: <b>{data['api_type'].upper()}</b>\n"
            f"• URL: <code>{esc(data['base_url'])}</code>\n\n"
            f"👉 Bây giờ bạn có thể bấm <b>Đồng bộ dịch vụ</b> để nạp toàn bộ danh mục từ web mới này vào Bot!",
            reply_markup=kb([
                [btn("🔄 Đồng bộ dịch vụ ngay", "adm:sync_srv", style="success")],
                [btn("« Danh sách API", "adm:providers")],
            ]),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"❌ Lỗi: {msg}", reply_markup=kb([[btn("« Quay lại", "adm:providers")]]))

# ==============================================================================
# QUẢN LÝ GIÁ DỊCH VỤ THỦ CÔNG (ADMIN TỰ SET GIÁ)
# ==============================================================================
@router.message(Command("setprice"))
async def cmd_set_price(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer(
            "⚠️ Cú pháp: <code>/setprice [ID_Dịch_Vụ] [Giá_Bán_VNĐ]</code>\n"
            "Ví dụ: <code>/setprice 2 5000</code> (Đặt giá dịch vụ Facebook thành 5.000đ)",
            parse_mode="HTML"
        )
    sid = int(parts[1])
    price = int(parts[2])
    srv = await db.get_service_by_id(sid)
    if not srv:
        return await message.answer(f"❌ Không tìm thấy dịch vụ có ID #{sid}")

    await db.set_service_price(sid, price)
    await message.answer(
        f"✅ <b>ĐÃ CẬP NHẬT GIÁ DỊCH VỤ #{sid}:</b>\n\n"
        f"• Dịch vụ: <b>{srv['name']}</b>\n"
        f"• Giá gốc nhà mạng: {fmt_vnd(srv['original_price'])}\n"
        f"• Giá bán mới niêm yết: <b>{fmt_vnd(price)}</b>",
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("adm:prices:"))
async def cb_admin_prices(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    
    page = int(cb.data.split(":")[2])
    page_size = 8
    offset = (page - 1) * page_size

    conn = await db.get_connection()
    try:
        async with conn.execute("SELECT COUNT(*) as c FROM services WHERE is_active = 1") as cur:
            total_items = (await cur.fetchone())["c"]
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        page = min(page, total_pages)

        async with conn.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY id ASC LIMIT ? OFFSET ?", (page_size, offset)) as cur:
            services_list = [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    text = (
        f"⚙️ <b>CÀI ĐẶT GIÁ DỊCH VỤ THỦ CÔNG (Trang {page}/{total_pages})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Bấm vào dịch vụ bất kỳ để tự đặt giá bán cố định hoặc khôi phục giá tự động:</i>\n\n"
    )

    rows = []
    for s in services_list:
        cust_tag = f"⭐ {fmt_vnd(s['selling_price'])}" if s.get("custom_price") else f"{fmt_vnd(s['selling_price'])}"
        lbl = f"#{s['id']} {s['name']} — {cust_tag}"
        rows.append([btn(lbl, f"adm:edit_price:{s['id']}", icon=s.get("custom_emoji_id"), style="primary")])

    nav_row = []
    if page > 1:
        nav_row.append(btn("◀️ Trước", f"adm:prices:{page-1}"))
    nav_row.append(btn(f"Trang {page}/{total_pages}", "adm:dashboard"))
    if page < total_pages:
        nav_row.append(btn("Sau ▶️", f"adm:prices:{page+1}"))
    rows.append(nav_row)

    rows.append([btn("« Bảng quản trị", "adm:dashboard")])
    await cb.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("adm:edit_price:"))
async def cb_admin_edit_price(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[2])
    srv = await db.get_service_by_id(sid)
    if not srv:
        return await cb.answer("Dịch vụ không tồn tại", show_alert=True)
    
    await state.update_data(edit_service_id=sid)
    await state.set_state(AdminPriceState.waiting_for_price)

    cust_status = f"Đang đặt cố định: <b>{fmt_vnd(srv['custom_price'])}</b>" if srv.get("custom_price") else "Đang dùng công thức tự động (Gốc + Markup)"

    text = (
        f"✏️ <b>CÀI ĐẶT GIÁ BÁN CHO: {srv['name']} (#{srv['id']})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Giá gốc nhà mạng: <b>{fmt_vnd(srv['original_price'])}</b>\n"
        f"• Giá bán hiện tại: <b>{fmt_vnd(srv['selling_price'])}</b>\n"
        f"• Trạng thái giá: {cust_status}\n\n"
        f"👉 <b>Hãy gửi số tiền bán mới (VNĐ) vào đây:</b>\n"
        f"(Ví dụ gửi tin nhắn: <code>4000</code> hoặc <code>5000</code>)"
    )
    markup = kb([
        [btn("🔄 Khôi phục Giá gốc + Markup", f"adm:reset_price:{sid}", style="primary")],
        [btn("« Hủy / Quay lại", "adm:prices:1")],
    ])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(AdminPriceState.waiting_for_price)
async def msg_save_custom_price(message: Message, state: FSMContext):
    data = await state.get_data()
    sid = data.get("edit_service_id")
    await state.clear()

    txt = message.text.strip().replace(".", "").replace(",", "")
    if not txt.isdigit():
        return await message.answer("⚠️ Giá tiền phải là số nguyên dương. Thao tác đã hủy.", reply_markup=kb([[btn("« Danh sách giá", "adm:prices:1")]]))

    price = int(txt)
    await db.set_service_price(sid, price)
    srv = await db.get_service_by_id(sid)
    await message.answer(
        f"✅ <b>ĐÃ CẬP NHẬT GIÁ MỚI CHO {srv['name']}!</b>\n\n"
        f"• Giá bán niêm yết: <b>{fmt_vnd(price)}</b>",
        reply_markup=kb([[btn("« Quay lại danh sách giá", "adm:prices:1")]]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("adm:reset_price:"))
async def cb_admin_reset_price(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[2])
    await state.clear()
    await db.reset_service_price(sid)
    srv = await db.get_service_by_id(sid)
    await cb.answer("Đã khôi phục giá bán tự động theo Markup!", show_alert=True)
    await cb.message.edit_text(
        f"✅ <b>ĐÃ KHÔI PHỤC GIÁ TỰ ĐỘNG CHO: {srv['name']}</b>\n\n"
        f"• Giá bán hiện tại: <b>{fmt_vnd(srv['selling_price'])}</b> (Giá gốc + Markup)",
        reply_markup=kb([[btn("« Quay lại danh sách giá", "adm:prices:1")]]),
        parse_mode="HTML"
    )

# ==============================================================================
# ĐỒNG BỘ TẤT CẢ DỊCH VỤ TỪ CÁC CỔNG API
# ==============================================================================
@router.message(Command("sync"))
@router.callback_query(F.data == "adm:sync_srv")
async def handle_sync_services(event):
    uid = event.from_user.id
    if not is_admin(uid):
        if isinstance(event, CallbackQuery):
            return await event.answer("⛔ Không có quyền.", show_alert=True)
        return await event.answer("⛔ Không có quyền.")

    if isinstance(event, CallbackQuery):
        await event.answer("⏳ Đang đồng bộ tất cả cổng API...")
        msg = await event.message.answer("⏳ <b>Đang đồng bộ dữ liệu dịch vụ từ tất cả API kết nối...</b>", parse_mode="HTML")
    else:
        msg = await event.answer("⏳ <b>Đang đồng bộ dữ liệu dịch vụ từ tất cả API kết nối...</b>", parse_mode="HTML")

    count = await sms_client.sync_all_services()
    markup = await db.get_config("markup_amount", "1500")
    providers = await db.get_api_providers(active_only=True)

    await msg.edit_text(
        f"✅ <b>ĐÃ ĐỒNG BỘ DỊCH VỤ THÀNH CÔNG!</b>\n\n"
        f"• Tổng dịch vụ sẵn sàng: <b>{count} nền tảng</b>\n"
        f"• Số cổng API đang hoạt động: <b>{len(providers)} API</b>\n"
        f"• Biên lợi nhuận mặc định: <b>+{int(markup):,}đ / tin nhắn</b>\n"
        f"• Toàn bộ Icon 3D thương hiệu và giá riêng của Admin đã được đồng bộ chính xác 100%.",
        reply_markup=kb([[btn("« Quay lại Admin", "adm:dashboard")]]),
        parse_mode="HTML"
    )

# ==============================================================================
# CÀI ĐẶT & TỰ ĐỘNG ĐIỀU CHỈNH BIÊN LỢI NHUẬN (LÃI TỰ ĐỘNG)
# ==============================================================================
@router.callback_query(F.data == "adm:markup_custom")
async def cb_markup_custom(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    
    current_markup = await db.get_config("markup_amount", "1500")
    await state.set_state(AdminMarkupState.waiting_for_markup)
    
    text = (
        "📈 <b>TỰ ĐỘNG ĐIỀU CHỈNH BIÊN LỢI NHUẬN (LÃI TỰ ĐỘNG)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• Mức lãi hiện tại: <b>+{int(current_markup):,}đ/tin nhắn</b>\n"
        "• Công thức tính: <code>Giá bán = Giá gốc API + Lãi</code> (làm tròn lên hàng trăm).\n\n"
        "👉 <b>Vui lòng gửi số tiền lãi bạn muốn áp dụng:</b>\n"
        "<i>(Ví dụ: 500, 1000, 1500, 1800, 2000, 2500, 3000, 5000...)</i>\n\n"
        "⚡️ <i>Ngay sau khi bạn gửi tin nhắn, hệ thống sẽ tự động cập nhật lại giá bán cho toàn bộ dịch vụ!</i>"
    )
    markup = kb([
        [btn("💵 +1.000đ", "adm:markup:1000"), btn("💵 +1.500đ", "adm:markup:1500")],
        [btn("💵 +2.000đ", "adm:markup:2000"), btn("💵 +2.500đ", "adm:markup:2500")],
        [btn("💵 +3.000đ", "adm:markup:3000"), btn("💵 +5.000đ", "adm:markup:5000")],
        [btn("« Hủy / Quay lại Admin Dashboard", "adm:dashboard")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(AdminMarkupState.waiting_for_markup)
async def handle_admin_markup_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip().replace(".", "").replace(",", "")
    if not text.isdigit() or int(text) < 0:
        return await message.answer(
            "⚠️ <b>Số tiền lãi không hợp lệ!</b>\n"
            "Vui lòng chỉ gửi số tiền (VNĐ) lớn hơn hoặc bằng 0.\n"
            "Ví dụ: <code>1500</code> hoặc <code>2000</code>",
            parse_mode="HTML"
        )
    val = int(text)
    updated_count = await _apply_new_markup(val)
    await state.clear()
    
    markup_kb = kb([
        [btn("⚙️ Về Bảng Quản Trị Admin", "adm:dashboard", style="primary")],
        [btn("📱 Xem Giá Bán Trên Menu Thuê", "u:rent_menu", style="success")],
    ])
    await message.answer(
        f"🎉 <b>ĐÃ CẬP NHẬT BIÊN LỢI NHUẬN THÀNH CÔNG!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Mức lãi mới: <b>+{val:,}đ/tin nhắn</b>\n"
        f"• Đã tự động cập nhật giá cho: <b>{updated_count:,} dịch vụ</b>\n"
        f"• Tất cả khách hàng sẽ nhìn thấy mức giá mới ngay lập tức!\n\n"
        f"💡 <i>Những dịch vụ admin đã đặt giá riêng thủ công (/setprice) sẽ được bảo lưu.</i>",
        reply_markup=markup_kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("adm:markup:"))
async def cb_set_markup_btn(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    val = int(cb.data.split(":")[2])
    updated_count = await _apply_new_markup(val)
    await cb.answer(f"✅ Đã đổi lợi nhuận sang +{val:,}đ/tin ({updated_count} dịch vụ)!", show_alert=True)
    await cb_adm_dashboard(cb, state)

@router.message(Command("setmarkup"))
async def cmd_set_markup(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].replace(".", "").replace(",", "").isdigit():
        return await message.answer("⚠️ Cú pháp: <code>/setmarkup [số_tiền]</code>\nVí dụ: <code>/setmarkup 1500</code> hoặc <code>/setmarkup 2000</code>", parse_mode="HTML")
    val = int(parts[1].replace(".", "").replace(",", ""))
    updated_count = await _apply_new_markup(val)
    await message.answer(
        f"✅ Đã đổi biên lợi nhuận sang <b>+{val:,}đ/tin nhắn</b>!\n"
        f"Đã tự động tính toán lại và cập nhật giá bán cho <b>{updated_count:,} dịch vụ</b> trên toàn hệ thống!",
        parse_mode="HTML"
    )

async def _apply_new_markup(markup: int) -> int:
    await db.set_config("markup_amount", str(markup))
    conn = await db.get_connection()
    count = 0
    try:
        async with conn.execute("SELECT id, original_price, custom_price FROM services") as cur:
            rows = await cur.fetchall()
            for r in rows:
                if not r["custom_price"] or r["custom_price"] <= 0:
                    new_sell = calculate_markup_price(r["original_price"], markup)
                    await conn.execute("UPDATE services SET selling_price = ? WHERE id = ?", (new_sell, r["id"]))
                    count += 1
        await conn.commit()
        return count
    finally:
        await conn.close()

# ==============================================================================
# CÀI ĐẶT TIMEOUT
# ==============================================================================
@router.message(Command("settimeout"))
async def cmd_set_timeout(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("⚠️ Cú pháp: <code>/settimeout [số_giây]</code>\nVí dụ: <code>/settimeout 180</code>", parse_mode="HTML")
    sec = int(parts[1])
    if sec < 60 or sec > 600:
        return await message.answer("⚠️ Thời gian timeout phải từ 60 đến 600 giây.")
    await db.set_config("order_timeout_seconds", str(sec))
    await message.answer(f"✅ Đã cập nhật thời gian chờ OTP thành <b>{sec} giây</b>!", parse_mode="HTML")

# ==============================================================================
# QUẢN LÝ SỐ DƯ NGƯỜI DÙNG
# ==============================================================================
@router.message(Command("addbal"))
async def cmd_add_balance(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].lstrip("-").isdigit():
        return await message.answer("⚠️ Cú pháp: <code>/addbal [user_id] [số_tiền]</code>\nVí dụ: <code>/addbal 8754685711 50000</code>", parse_mode="HTML")
    uid = int(parts[1])
    amount = int(parts[2])

    success, new_bal, msg = await db.adjust_user_balance(uid, amount, admin_name=f"Admin {message.from_user.id}")
    if success:
        await message.answer(f"✅ Đã cộng <b>+{amount:,}đ</b> cho người dùng <code>{uid}</code>.\n• Số dư mới: <b>{fmt_vnd(new_bal)}</b>", parse_mode="HTML")
        try:
            await bot.send_message(uid, f"🎉 <b>TÀI KHOẢN CỦA BẠN ĐƯỢC CỘNG TIỀN:</b>\n• Số tiền: <b>+{amount:,}đ</b>\n• Số dư hiện tại: <b>{fmt_vnd(new_bal)}</b>\n\n👉 Bạn có thể thuê số nhận OTP ngay bây giờ!", parse_mode="HTML")
        except Exception:
            pass
    else:
        await message.answer(f"❌ Thất bại: {msg}")

@router.message(Command("subbal"))
async def cmd_sub_balance(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer("⚠️ Cú pháp: <code>/subbal [user_id] [số_tiền]</code>\nVí dụ: <code>/subbal 8754685711 20000</code>", parse_mode="HTML")
    uid = int(parts[1])
    amount = int(parts[2])

    success, new_bal, msg = await db.adjust_user_balance(uid, -amount, admin_name=f"Admin {message.from_user.id}")
    if success:
        await message.answer(f"✅ Đã trừ <b>-{amount:,}đ</b> của người dùng <code>{uid}</code>.\n• Số dư mới: <b>{fmt_vnd(new_bal)}</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Thất bại: {msg}")

# ==============================================================================
# CÀI ĐẶT THÔNG TIN NGÂN HÀNG NẠP TIỀN
# ==============================================================================
@router.message(Command("setbank"))
async def cmd_set_bank(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.answer(
            "⚠️ Cú pháp: <code>/setbank [tên_ngân_hàng] [stk] [chủ_tài_khoản]</code>\n"
            "Ví dụ: <code>/setbank MBBANK 0987654321 NGUYEN VAN A</code>",
            parse_mode="HTML"
        )
    b_name = parts[1].upper()
    b_acc = parts[2]
    b_owner = parts[3].upper()

    await db.set_config("bank_name", b_name)
    await db.set_config("bank_acc", b_acc)
    await db.set_config("bank_owner", b_owner)

    await message.answer(
        f"✅ <b>ĐÃ CẬP NHẬT THÔNG TIN NGÂN HÀNG NẠP TIỀN:</b>\n\n"
        f"• Ngân hàng: <b>{b_name}</b>\n"
        f"• Số tài khoản: <code>{b_acc}</code>\n"
        f"• Chủ tài khoản: <b>{b_owner}</b>",
        parse_mode="HTML"
    )

# ==============================================================================
# ĐIỀU CHỈNH MỨC NẠP TỐI THIỂU (MIN NẠP) DO ADMIN CHỌN
# ==============================================================================
@router.callback_query(F.data == "adm:set_mindeposit")
async def cb_adm_set_mindeposit(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)

    cur_min = await db.get_min_deposit()
    text = (
        "💵 <b>ĐIỀU CHỈNH MỨC NẠP TỐI THIỂU (MIN NẠP)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• Mức nạp tối thiểu hiện tại: <b>{fmt_vnd(cur_min)}</b>\n\n"
        "👉 Bạn có thể chọn nhanh một mốc bên dưới hoặc nhập số tiền tùy ý:"
    )
    markup = kb([
        [btn("💵 10.000đ", "adm:set_mindep_val:10000"), btn("💵 20.000đ", "adm:set_mindep_val:20000")],
        [btn("💵 50.000đ", "adm:set_mindep_val:50000"), btn("💵 100.000đ", "adm:set_mindep_val:100000")],
        [btn("💵 200.000đ", "adm:set_mindep_val:200000"), btn("✍️ Nhập số tiền tùy ý", "adm:set_mindep_custom", style="primary")],
        [btn("« Bảng điều khiển Admin", "adm:dashboard")],
    ])
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("adm:set_mindep_val:"))
async def cb_adm_set_mindep_val(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    val = int(cb.data.split(":")[2])
    await db.set_min_deposit(val)
    await cb.answer(f"✅ Đã đổi mức nạp tối thiểu thành {fmt_vnd(val)}!", show_alert=True)
    await cb_adm_dashboard(cb, state)

@router.callback_query(F.data == "adm:set_mindep_custom")
async def cb_adm_set_mindep_custom(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    await state.set_state(AdminMinDepositState.waiting_for_amount)
    text = (
        "✍️ <b>NHẬP MỨC NẠP TỐI THIỂU (MIN NẠP) MONG MUỐN:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Vui lòng gửi tin nhắn số tiền bạn muốn đặt làm mức nạp tối thiểu (Ví dụ: <code>10000</code> hoặc <code>25000</code>, <code>50k</code>):"
    )
    markup = kb([[btn("« Hủy & Quay lại", "adm:set_mindeposit")]])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(AdminMinDepositState.waiting_for_amount)
async def handle_admin_mindeposit_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = message.text.strip().lower().replace(",", "").replace(".", "").replace("đ", "").replace("vnd", "")
    if raw.endswith("k"):
        num = raw[:-1]
        amount = int(float(num) * 1_000) if num.replace(".", "").isdigit() else 0
    elif raw.endswith("m"):
        num = raw[:-1]
        amount = int(float(num) * 1_000_000) if num.replace(".", "").isdigit() else 0
    elif raw.isdigit():
        amount = int(raw)
    else:
        amount = 0

    if amount < 1000:
        return await message.answer("⚠️ Số tiền không hợp lệ. Vui lòng nhập tối thiểu từ 1.000đ trở lên!")

    await state.clear()
    await db.set_min_deposit(amount)
    await message.answer(
        f"✅ <b>ĐÃ CẬP NHẬT MỨC NẠP TỐI THIỂU:</b> <b>{fmt_vnd(amount)}</b>\n"
        f"Giao diện nạp tiền của người dùng và các nút chọn mốc nạp đã được đồng bộ tự động!",
        reply_markup=kb([[btn("« Bảng điều khiển Admin", "adm:dashboard")]]),
        parse_mode="HTML"
    )

@router.message(Command("setmindeposit"))
async def cmd_set_min_deposit(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("⚠️ Cú pháp: <code>/setmindeposit [số_tiền]</code>\nVí dụ: <code>/setmindeposit 20000</code>", parse_mode="HTML")
    raw = parts[1].strip().lower().replace(",", "").replace(".", "").replace("đ", "").replace("vnd", "")
    if raw.endswith("k"):
        amount = int(float(raw[:-1]) * 1000)
    elif raw.isdigit():
        amount = int(raw)
    else:
        amount = 0

    if amount < 1000:
        return await message.answer("⚠️ Số tiền phải từ 1.000đ trở lên!")

    await db.set_min_deposit(amount)
    await message.answer(f"✅ Đã đặt mức nạp tối thiểu thành <b>{fmt_vnd(amount)}</b>!", parse_mode="HTML")

# ==============================================================================
# QUẢN LÝ PROXY & TỰ ĐIỀU CHỈNH GIÁ PROXY
# ==============================================================================
@router.callback_query(F.data == "adm:manage_proxies")
async def cb_adm_manage_proxies(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)

    pkgs = await db.get_proxy_packages(active_only=False)
    mult = await db.get_proxy_multiplier()

    text = (
        "🌐 <b>QUẢN LÝ GÓI PROXY & ĐIỀU CHỈNH GIÁ BÁN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• Hệ số nhân giá mặc định: <b>x{mult}</b> (Đắt gấp đôi giá gốc)\n"
        "• Cơ chế: Nếu gói có giá tùy chỉnh (Custom Price) do Admin đặt -> Áp dụng giá đó. Ngược lại -> Tự động tính = Giá gốc x Hệ số.\n\n"
        "👉 <b>Danh sách các gói Proxy hiện có:</b>\n"
    )
    rows = []
    for p in pkgs:
        cust_str = f" [Tự đặt: {fmt_vnd(p['custom_price'])}]" if p.get("custom_price") else " [Giá x2]"
        text += (
            f"<b>#{p['id']} - {esc(p['name'])}</b>\n"
            f"• Gốc: {fmt_vnd(p['original_price'])} | Bán: <b>{fmt_vnd(p['selling_price'])}</b>{cust_str}\n"
            f"• Loại: {esc(p['proxy_type'].upper())} | Thời hạn: {p['duration_days']} ngày\n\n"
        )
        rows.append([btn(f"✏️ Đổi giá #{p['id']} ({fmt_vnd(p['selling_price'])})", f"adm:edit_prx:{p['id']}", style="primary")])

    rows.append([
        btn("📈 Đổi hệ số x1.5", "adm:set_prx_mult:1.5"),
        btn("📈 Đổi hệ số x2.0", "adm:set_prx_mult:2.0"),
        btn("📈 Đổi hệ số x2.5", "adm:set_prx_mult:2.5"),
    ])
    rows.append([btn("« Bảng điều khiển Admin", "adm:dashboard")])

    try:
        await cb.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=kb(rows), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("adm:set_prx_mult:"))
async def cb_adm_set_prx_mult(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    val = float(cb.data.split(":")[2])
    await db.set_proxy_multiplier(val)
    await cb.answer(f"✅ Đã đổi hệ số giá Proxy sang x{val}!", show_alert=True)
    await cb_adm_manage_proxies(cb, state)

@router.callback_query(F.data.startswith("adm:edit_prx:"))
async def cb_adm_edit_prx_price(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    pid = int(cb.data.split(":")[2])
    pkg = await db.get_proxy_package_by_id(pid)
    if not pkg:
        return await cb.answer("Gói không tồn tại.", show_alert=True)

    await state.set_state(AdminProxyPriceState.waiting_for_price)
    await state.update_data(package_id=pid)

    text = (
        f"✏️ <b>ĐIỀU CHỈNH GIÁ GÓI PROXY #{pid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Tên gói: <b>{esc(pkg['name'])}</b>\n"
        f"• Giá gốc nhà cung cấp: <b>{fmt_vnd(pkg['original_price'])}</b>\n"
        f"• Giá bán hiện tại: <b>{fmt_vnd(pkg['selling_price'])}</b>\n"
        f"• Giá tùy chỉnh hiện tại: <b>{fmt_vnd(pkg['custom_price']) if pkg.get('custom_price') else 'Chưa đặt (dùng hệ số x2)'}</b>\n\n"
        "👉 <b>Hãy nhập giá bán mong muốn mới (VNĐ) vào đây:</b>\n"
        "<i>(Hoặc gửi <code>0</code> để xóa giá tùy chỉnh và quay về công thức gấp đôi x2 mặc định)</i>"
    )
    markup = kb([[btn("« Quay lại Quản lý Proxy", "adm:manage_proxies")]])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.message(AdminProxyPriceState.waiting_for_price)
async def handle_admin_proxy_price_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    pid = data.get("package_id")
    if not pid:
        await state.clear()
        return

    raw = message.text.strip().lower().replace(",", "").replace(".", "").replace("đ", "").replace("vnd", "")
    if raw.endswith("k"):
        val = int(float(raw[:-1]) * 1000)
    elif raw.isdigit():
        val = int(raw)
    else:
        return await message.answer("⚠️ Giá tiền không hợp lệ. Vui lòng nhập số tiền!")

    await state.clear()
    await db.set_proxy_custom_price(pid, val)
    pkg = await db.get_proxy_package_by_id(pid)

    price_str = f"<b>{fmt_vnd(val)}</b> (Giá tùy chỉnh)" if val > 0 else f"<b>{fmt_vnd(pkg['selling_price'])}</b> (Khôi phục x2 mặc định)"
    await message.answer(
        f"✅ <b>ĐÃ CẬP NHẬT GIÁ BÁN PROXY THÀNH CÔNG!</b>\n\n"
        f"• Gói: <b>{esc(pkg['name'])}</b>\n"
        f"• Giá bán mới áp dụng cho khách: {price_str}",
        reply_markup=kb([[btn("« Quản lý Proxy", "adm:manage_proxies")]]),
        parse_mode="HTML"
    )

@router.message(Command("setproxyprice"))
async def cmd_set_proxy_price(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit():
        return await message.answer(
            "⚠️ Cú pháp: <code>/setproxyprice [id_gói] [giá_tiền]</code>\n"
            "Ví dụ: <code>/setproxyprice 1 12000</code> hoặc gửi giá <code>0</code> để đặt lại mặc định x2.",
            parse_mode="HTML"
        )
    pid = int(parts[1])
    raw = parts[2].lower().replace(",", "").replace(".", "")
    val = int(float(raw[:-1]) * 1000) if raw.endswith("k") else (int(raw) if raw.isdigit() else 0)

    ok = await db.set_proxy_custom_price(pid, val)
    if ok:
        pkg = await db.get_proxy_package_by_id(pid)
        await message.answer(f"✅ Đã cập nhật giá bán gói #{pid} (<b>{pkg['name']}</b>) thành <b>{fmt_vnd(pkg['selling_price'])}</b>!", parse_mode="HTML")
    else:
        await message.answer("❌ Không tìm thấy gói Proxy tương ứng.")
