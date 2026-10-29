import time
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from config import ORDER_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS
import db
from hupsms_client import sms_client
import ui

log = logging.getLogger(__name__)

# Tập hợp theo dõi các Task Polling đang chạy
_active_polling_tasks = {}

async def rent_otp_service(bot: Bot, user: dict, service_id: int, chat_id: int) -> tuple[bool, str, Optional[dict]]:
    """Quy trình tạo đơn thuê OTP an toàn tuyệt đối chống Race Condition:
    1. Kiểm tra dịch vụ và giá bán.
    2. Tạm giữ tiền ví qua ACID Transaction.
    3. Gọi API nhà mạng lấy số điện thoại thật 100%.
    4. Kích hoạt Polling ngầm độc lập (Non-blocking)."""
    uid = user["telegram_id"]
    
    # 1. Lấy thông tin dịch vụ
    srv = await db.get_service_by_id(service_id)
    if not srv or not srv.get("is_active"):
        return False, "⚠️ Dịch vụ hiện không khả dụng hoặc đã tạm ngưng.", None

    price = srv["selling_price"]
    sname = srv["name"]
    p_id = srv.get("provider_id", 1)
    order_id = f"OTP_{uuid.uuid4().hex[:8].upper()}"

    # 2. Tạm giữ số dư (Chống Race Condition)
    held, hold_msg, new_bal = await db.hold_balance_for_rent(uid, price, order_id, sname)
    if not held:
        return False, hold_msg, None

    # 3. Gọi API nhà mạng tạo phiên
    success, p_oid, phone, msg = await sms_client.create_order(service_id)
    if not success or not phone:
        # Hoàn tiền ngay lập tức nếu lỗi kết nối hoặc hết SIM
        await db.refund_balance(uid, price, order_id, f"Lỗi tạo số: {msg}")
        detail = msg if msg else f"Nhà mạng tạm hết SIM cho dịch vụ {sname}."
        return False, f"⚠️ {detail}\n\n<i>(Số tiền tạm giữ {price:,}đ đã được hoàn lại 100% vào số dư ví của bạn)</i>", None

    timeout_cfg = int(await db.get_config("order_timeout_seconds", str(ORDER_TIMEOUT_SECONDS)))
    expires_at = datetime.now() + timedelta(seconds=timeout_cfg)

    # 4. Lưu đơn hàng vào cơ sở dữ liệu
    conn = await db.get_connection()
    try:
        await conn.execute("""
            INSERT INTO orders (order_id, user_id, service_id, service_name, selling_price, hupsms_order_id, provider_id, phone_number, status, is_rerent, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'WAITING', 0, ?)
        """, (order_id, uid, service_id, sname, price, p_oid, p_id, phone, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
        await conn.commit()
    finally:
        await conn.close()

    order_data = {
        "order_id": order_id,
        "user_id": uid,
        "service_id": service_id,
        "service_name": sname,
        "selling_price": price,
        "hupsms_order_id": p_oid,
        "provider_id": p_id,
        "phone_number": phone,
        "status": "WAITING",
        "timeout_seconds": timeout_cfg
    }

    # 5. Gửi Card giao diện chờ OTP cho khách
    text, markup = ui.render_order_waiting_card(order_data, timeout_cfg)
    sent_msg = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    
    conn = await db.get_connection()
    try:
        await conn.execute("UPDATE orders SET msg_chat_id = ?, msg_id = ? WHERE order_id = ?", (chat_id, sent_msg.message_id, order_id))
        await conn.commit()
    finally:
        await conn.close()

    # 6. Khởi động Polling Task ngầm bằng asyncio.create_task (Tuyệt đối không dùng time.sleep)
    task = asyncio.create_task(
        poll_otp_worker(bot, order_id, uid, p_oid, p_id, timeout_cfg, chat_id, sent_msg.message_id, srv)
    )
    _active_polling_tasks[order_id] = task

    return True, "Khởi tạo thành công", order_data


async def rerent_otp_service(bot: Bot, user: dict, prev_order_id: str, chat_id: int) -> tuple[bool, str, Optional[dict]]:
    """Thuê lại chính xác số điện thoại cũ đã từng thuê của một đơn hàng trước đó."""
    uid = user["telegram_id"]
    prev_order = await db.get_order_by_id(prev_order_id)
    if not prev_order:
        return False, "Không tìm thấy thông tin đơn hàng cũ để thuê lại.", None

    service_id = prev_order["service_id"]
    phone_number = prev_order["phone_number"]
    prev_provider_id = prev_order.get("provider_id", 1)
    
    srv = await db.get_service_by_id(service_id)
    if not srv:
        return False, "Dịch vụ này hiện không còn khả dụng.", None

    price = srv["selling_price"]
    sname = srv["name"]
    new_order_id = f"RE_{uuid.uuid4().hex[:8].upper()}"

    # Tạm giữ số dư
    held, hold_msg, new_bal = await db.hold_balance_for_rent(uid, price, new_order_id, f"Thuê lại {sname}")
    if not held:
        return False, hold_msg, None

    # Gọi API thuê lại số cũ
    success, p_oid, phone, msg = await sms_client.rerent_number(service_id, phone_number, prev_provider_id)
    if not success or not p_oid:
        await db.refund_balance(uid, price, new_order_id, f"Lỗi thuê lại số: {msg}")
        return False, f"⚠️ Số {phone_number} hiện đã hết phiên giữ trên nhà mạng, không thể thuê lại. Vui lòng bấm Thuê số mới!", None

    timeout_cfg = int(await db.get_config("order_timeout_seconds", str(ORDER_TIMEOUT_SECONDS)))
    expires_at = datetime.now() + timedelta(seconds=timeout_cfg)

    conn = await db.get_connection()
    try:
        await conn.execute("""
            INSERT INTO orders (order_id, user_id, service_id, service_name, selling_price, hupsms_order_id, provider_id, phone_number, status, is_rerent, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'WAITING', 1, ?)
        """, (new_order_id, uid, service_id, f"{sname} (Thuê lại)", price, p_oid, prev_provider_id, phone, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
        await conn.commit()
    finally:
        await conn.close()

    order_data = {
        "order_id": new_order_id,
        "user_id": uid,
        "service_id": service_id,
        "service_name": f"{sname} (Thuê lại)",
        "selling_price": price,
        "hupsms_order_id": p_oid,
        "provider_id": prev_provider_id,
        "phone_number": phone,
        "status": "WAITING",
        "timeout_seconds": timeout_cfg
    }

    text, markup = ui.render_order_waiting_card(order_data, timeout_cfg)
    sent_msg = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

    conn = await db.get_connection()
    try:
        await conn.execute("UPDATE orders SET msg_chat_id = ?, msg_id = ? WHERE order_id = ?", (chat_id, sent_msg.message_id, new_order_id))
        await conn.commit()
    finally:
        await conn.close()

    task = asyncio.create_task(
        poll_otp_worker(bot, new_order_id, uid, p_oid, prev_provider_id, timeout_cfg, chat_id, sent_msg.message_id, srv)
    )
    _active_polling_tasks[new_order_id] = task

    return True, "Đã khởi tạo phiên thuê lại số thành công!", order_data


async def poll_otp_worker(bot: Bot, order_id: str, user_id: int, provider_order_id: str, provider_id: int, timeout_sec: int, chat_id: int, message_id: int, srv_info: dict):
    """Tiến trình Polling ngầm độc lập cho từng người dùng (Non-blocking):
    - Kiểm tra trạng thái mã OTP mỗi 3 giây qua asyncio.sleep(3)
    - Tự động cập nhật tin nhắn khi mã về
    - Tự động hủy và hoàn tiền 100% nếu hết giờ."""
    start_time = time.time()
    last_ui_update = time.time()

    try:
        while True:
            elapsed = int(time.time() - start_time)
            remaining = max(0, timeout_sec - elapsed)

            # 1. Kiểm tra đơn trong database xem khách có bấm Hủy thủ công chưa
            order = await db.get_order_by_id(order_id)
            if not order or order["status"] != "WAITING":
                log.info("Order %s no longer WAITING, stopping poll.", order_id)
                break

            # 2. Hết thời gian chờ (Timeout) -> Tự động hủy & hoàn tiền 100%
            if remaining <= 0:
                log.info("Order %s timed out after %ds. Refunding 100%% balance.", order_id, timeout_sec)
                await sms_client.cancel_order(provider_order_id, provider_id)
                await db.refund_balance(user_id, order["selling_price"], order_id, "Hết thời gian chờ (Timeout)")
                
                conn = await db.get_connection()
                try:
                    await conn.execute("UPDATE orders SET status = 'TIMEOUT', completed_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))
                    await conn.commit()
                finally:
                    await conn.close()

                text, markup = ui.render_order_timeout_card(order)
                try:
                    await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
                except TelegramBadRequest:
                    pass
                break

            # 3. Gọi API kiểm tra xem có SMS thật từ nhà mạng chưa
            check_res = await sms_client.check_order(provider_order_id, provider_id)
            status = check_res.get("status")
            otp = check_res.get("otp")
            sms = check_res.get("message")
            clean_otp = str(otp).strip() if otp else ""
            if "invalid" in clean_otp.lower() or "error" in clean_otp.lower():
                clean_otp = ""

            if status == "SUCCESS" and (clean_otp or (sms and len(str(sms)) > 3)):
                otp_to_save = clean_otp or "ĐÃ NHẬN SMS"
                # ĐÃ CÓ OTP THẬT THÀNH CÔNG!
                log.info("🎉 Order %s SUCCESS! Received genuine SMS OTP: %s", order_id, otp_to_save)
                conn = await db.get_connection()
                try:
                    await conn.execute("""
                        UPDATE orders 
                        SET status = 'SUCCESS', otp_code = ?, sms_content = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE order_id = ?
                    """, (str(otp_to_save), str(sms or ""), order_id))
                    await conn.commit()
                finally:
                    await conn.close()

                # Ghi nhận hoàn tất và trừ tiền thực tế
                await db.charge_order_success(order_id)

                order["otp_code"] = otp_to_save
                order["sms_content"] = sms
                text, markup = ui.render_order_success_card(order)
                try:
                    await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
                except TelegramBadRequest:
                    pass
                
                # Gửi thêm tin nhắn chuông báo kèm mã
                try:
                    await bot.send_message(
                        chat_id,
                        f"🔔 <b>MÃ OTP DỊCH VỤ {srv_info['name'].upper()} ĐÃ VỀ:</b>\n"
                        f"👉 <code>{otp}</code> 👈 <i>(Chạm vào mã để sao chép)</i>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                break

            elif status in ("CANCELED", "FAILED"):
                log.info("Order %s was canceled by carrier.", order_id)
                await db.refund_balance(user_id, order["selling_price"], order_id, "Nhà mạng hủy phiên")
                conn = await db.get_connection()
                try:
                    await conn.execute("UPDATE orders SET status = 'CANCELED', completed_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))
                    await conn.commit()
                finally:
                    await conn.close()
                break

            # 4. Định kỳ cập nhật lại đồng hồ đếm ngược mỗi 15 giây
            if time.time() - last_ui_update >= 15 and remaining > 5:
                last_ui_update = time.time()
                text, markup = ui.render_order_waiting_card(order, remaining)
                try:
                    await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
                except TelegramBadRequest:
                    pass

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    except asyncio.CancelledError:
        log.info("Polling task for order %s was cancelled.", order_id)
    except Exception as e:
        log.error("Error in poll_otp_worker for order %s: %s", order_id, e, exc_info=True)
    finally:
        _active_polling_tasks.pop(order_id, None)


async def user_cancel_order(bot: Bot, order_id: str, user_id: int) -> tuple[bool, str]:
    """Người dùng chủ động bấm Hủy đơn:
    - Hủy lệnh trên nhà mạng.
    - Hoàn 100% tiền tạm giữ về ví.
    - Dừng task Polling ngầm."""
    order = await db.get_order_by_id(order_id)
    if not order or order["user_id"] != user_id:
        return False, "Không tìm thấy đơn hàng."

    if order["status"] != "WAITING":
        return False, f"Đơn hàng này không thể hủy (Trạng thái: {order['status']})."

    # Dừng task polling nếu đang chạy
    task = _active_polling_tasks.pop(order_id, None)
    if task and not task.done():
        task.cancel()

    # Hủy trên nhà mạng
    if order.get("hupsms_order_id"):
        await sms_client.cancel_order(order["hupsms_order_id"], order.get("provider_id", 1))

    # Hoàn tiền
    await db.refund_balance(user_id, order["selling_price"], order_id, "Khách hàng chủ động hủy đơn")

    conn = await db.get_connection()
    try:
        await conn.execute("UPDATE orders SET status = 'CANCELED', completed_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))
        await conn.commit()
    finally:
        await conn.close()

    return True, f"Đã hủy đơn #{order_id} thành công! Toàn bộ {order['selling_price']:,}đ đã được hoàn về ví của bạn."
