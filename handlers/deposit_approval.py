"""Duyệt nạp tiền thủ công: khách báo đã chuyển khoản -> Admin Duyệt / Từ chối."""
import uuid
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

import db
from ui import btn, kb, esc, fmt_vnd
from config import ADMIN_IDS, SUPPORT_USERNAME, is_admin

log = logging.getLogger(__name__)
router = Router(name="deposit_approval")


def _admin_kb(code: str):
    return kb([
        [btn("✅ Duyệt & cộng tiền", f"dep_ok:{code}", style="success"),
         btn("❌ Từ chối", f"dep_no:{code}", style="danger")],
    ])


async def _get_request(code: str):
    conn = await db.get_connection()
    try:
        async with conn.execute("SELECT * FROM deposit_requests WHERE code = ?", (code,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def _set_status(code: str, new_status: str) -> bool:
    """Chỉ đổi trạng thái khi còn PENDING (chống duyệt 2 lần)."""
    conn = await db.get_connection()
    try:
        cur = await conn.execute(
            "UPDATE deposit_requests SET status = ? WHERE code = ? AND status = 'PENDING'",
            (new_status, code),
        )
        await conn.commit()
        return cur.rowcount == 1
    finally:
        await conn.close()


# ---------------- KHÁCH BÁO ĐÃ CHUYỂN KHOẢN ----------------
@router.callback_query(F.data.startswith("dep_paid:"))
async def cb_user_paid(cb: CallbackQuery, bot: Bot):
    amount = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    uname = cb.from_user.username or cb.from_user.full_name

    # Chặn spam: mỗi khách chỉ có 1 yêu cầu chờ duyệt
    conn = await db.get_connection()
    try:
        async with conn.execute(
            "SELECT code FROM deposit_requests WHERE user_id = ? AND status = 'PENDING'", (uid,)
        ) as cur:
            pending = await cur.fetchone()
        if pending:
            return await cb.answer(
                f"Bạn đang có yêu cầu #{pending['code']} chờ duyệt. Vui lòng đợi Admin xử lý!",
                show_alert=True,
            )
        code = f"D{uuid.uuid4().hex[:6].upper()}"
        await conn.execute(
            "INSERT INTO deposit_requests (code, user_id, amount, status) VALUES (?, ?, ?, 'PENDING')",
            (code, uid, amount),
        )
        await conn.commit()
    finally:
        await conn.close()

    await cb.answer("Đã gửi yêu cầu duyệt cho Admin!", show_alert=True)
    try:
        await cb.message.edit_reply_markup(reply_markup=kb([
            [btn("⏳ Đang chờ Admin duyệt...", "u:profile", style="primary")],
            [btn("« Menu chính", "u:home")],
        ]))
    except Exception:
        pass

    text = (
        f"💰 <b>YÊU CẦU NẠP TIỀN MỚI #{code}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Khách: <b>{esc(uname)}</b> (<code>{uid}</code>)\n"
        f"💵 Số tiền: <b>{fmt_vnd(amount)}</b>\n"
        f"📝 Nội dung CK cần kiểm tra: <code>NAP {uid}</code>\n\n"
        f"👉 Kiểm tra app MoMo rồi bấm Duyệt hoặc Từ chối:"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, reply_markup=_admin_kb(code), parse_mode="HTML")
        except Exception as e:
            log.warning("Không gửi được yêu cầu nạp cho admin %s: %s", aid, e)


# ---------------- ADMIN DUYỆT / TỪ CHỐI ----------------
@router.callback_query(F.data.startswith("dep_ok:"))
async def cb_admin_approve(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    code = cb.data.split(":")[1]
    req = await _get_request(code)
    if not req:
        return await cb.answer("Không tìm thấy yêu cầu.", show_alert=True)
    if not await _set_status(code, "APPROVED"):
        return await cb.answer(f"Yêu cầu đã được xử lý trước đó ({req['status']}).", show_alert=True)

    ok, new_bal, msg = await db.adjust_user_balance(
        req["user_id"], req["amount"], admin_name=f"Duyệt nạp #{code}"
    )
    if not ok:
        await _set_status_force(code, "PENDING")
        return await cb.answer(f"Lỗi cộng tiền: {msg}", show_alert=True)

    await cb.answer("Đã duyệt và cộng tiền!", show_alert=True)
    try:
        await cb.message.edit_text(
            cb.message.html_text + f"\n\n✅ <b>ĐÃ DUYỆT</b> bởi Admin — Số dư mới của khách: <b>{fmt_vnd(new_bal)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    try:
        await bot.send_message(
            req["user_id"],
            f"🎉 <b>NẠP TIỀN THÀNH CÔNG #{code}</b>\n"
            f"• Số tiền: <b>+{fmt_vnd(req['amount'])}</b>\n"
            f"• Số dư hiện tại: <b>{fmt_vnd(new_bal)}</b>\n\n"
            f"👉 Bạn có thể thuê số nhận OTP ngay!",
            reply_markup=kb([[btn("⚡️ Thuê OTP ngay", "u:rent_menu", style="success")]]),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def _set_status_force(code: str, status: str):
    conn = await db.get_connection()
    try:
        await conn.execute("UPDATE deposit_requests SET status = ? WHERE code = ?", (status, code))
        await conn.commit()
    finally:
        await conn.close()


@router.callback_query(F.data.startswith("dep_no:"))
async def cb_admin_reject(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id, cb.from_user.username):
        return await cb.answer("⛔ Không có quyền.", show_alert=True)
    code = cb.data.split(":")[1]
    req = await _get_request(code)
    if not req:
        return await cb.answer("Không tìm thấy yêu cầu.", show_alert=True)
    if not await _set_status(code, "REJECTED"):
        return await cb.answer(f"Yêu cầu đã được xử lý trước đó ({req['status']}).", show_alert=True)

    await cb.answer("Đã từ chối yêu cầu.", show_alert=True)
    try:
        await cb.message.edit_text(cb.message.html_text + "\n\n❌ <b>ĐÃ TỪ CHỐI</b>", parse_mode="HTML")
    except Exception:
        pass
    try:
        await bot.send_message(
            req["user_id"],
            f"❌ <b>YÊU CẦU NẠP #{code} BỊ TỪ CHỐI</b>\n"
            f"Admin chưa nhận được khoản chuyển {fmt_vnd(req['amount'])} đúng nội dung <code>NAP {req['user_id']}</code>.\n"
            f"Nếu bạn đã chuyển, vui lòng gửi ảnh biên lai cho @{SUPPORT_USERNAME}.",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ---------------- DANH SÁCH CHỜ DUYỆT ----------------
@router.message(Command("naptien"))
@router.callback_query(F.data == "adm:deposits")
async def list_pending(event):
    if not is_admin(event.from_user.id, event.from_user.username):
        return
    conn = await db.get_connection()
    try:
        async with conn.execute(
            "SELECT * FROM deposit_requests WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 20"
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    target = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()
    if not rows:
        return await target.answer("✅ Không có yêu cầu nạp tiền nào đang chờ duyệt.",
                                   reply_markup=kb([[btn("« Admin", "adm:dashboard")]]))
    await target.answer(f"💰 <b>CÓ {len(rows)} YÊU CẦU NẠP CHỜ DUYỆT:</b>", parse_mode="HTML")
    for r in rows:
        await target.answer(
            f"#{r['code']} • Khách <code>{r['user_id']}</code> • <b>{fmt_vnd(r['amount'])}</b>\n"
            f"Nội dung: <code>NAP {r['user_id']}</code> • {r['created_at']}",
            reply_markup=_admin_kb(r["code"]),
            parse_mode="HTML",
        )
