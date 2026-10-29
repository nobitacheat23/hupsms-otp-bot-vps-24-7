import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from config import BOT_TOKEN, ADMIN_IDS
import db
from hupsms_client import sms_client
from handlers import user_router, admin_router, deposit_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("main")

async def setup_bot_commands(bot: Bot):
    # 1. Menu lệnh cho người dùng thông thường (Chỉ thấy /start, ẩn hoàn toàn /admin và /sync)
    user_commands = [
        BotCommand(command="start", description="Khởi động / Menu chính"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # 2. Menu lệnh hiển thị RIÊNG cho Quản trị viên (Admin)
    admin_commands = [
        BotCommand(command="start", description="Khởi động / Menu chính"),
        BotCommand(command="admin", description="Bảng quản trị viên (Admin)"),
        BotCommand(command="sync", description="Đồng bộ tất cả dịch vụ từ các cổng API"),
    ]
    for aid in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=aid))
        except Exception as e:
            log.warning("Không thể set bot commands cho admin %s: %s", aid, e)

async def main():
    log.info("=== ĐANG KHỞI ĐỘNG BOT TELEGRAM THUÊ SIM OTP SMS ĐA API (PRODUCTION READY) ===")
    
    # 1. Khởi tạo Cơ sở dữ liệu SQLite
    await db.init_db()
    log.info("✓ Cơ sở dữ liệu SQLite (WAL mode + ACID) đã sẵn sàng.")

    # 2. Khởi tạo Client Đa API và đồng bộ dịch vụ
    total_services = await sms_client.sync_all_services()
    log.info("✓ Đã đồng bộ %d dịch vụ OTP SMS vào hệ thống.", total_services)

    # 3. Khởi tạo Aiogram Bot & Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Đăng ký các Router xử lý
    dp.include_router(deposit_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Cài đặt command menu
    await setup_bot_commands(bot)

    # Gửi thông báo khởi động cho Admin
    me = await bot.get_me()
    log.info("✓ Bot @%s (%s) đã kết nối thành công với Telegram Bot API!", me.username, me.first_name)
    
    providers = await db.get_api_providers(active_only=True)
    for aid in ADMIN_IDS:
        try:
            markup = await db.get_config("markup_amount", "1500")
            await bot.send_message(
                aid,
                f"🚀 <b>BOT THUÊ SIM OTP SMS ĐA API ĐÃ KHỞI CHẠY THÀNH CÔNG!</b>\n\n"
                f"• Bot: @{me.username} (<code>{me.first_name}</code>)\n"
                f"• Số cổng API hoạt động: <b>{len(providers)} / 3 cổng</b>\n"
                f"• Dịch vụ khả dụng: <b>{total_services} nền tảng</b>\n"
                f"• Biên lợi nhuận: <b>+{int(markup):,}đ/tin nhắn</b>\n"
                f"• Logo thương hiệu: <b>3D Custom Emojis cho toàn bộ ứng dụng</b>\n"
                f"• Thuê lại số cũ: <b>Sẵn sàng hoạt động</b>\n"
                f"• Cam kết: <b>SMS thật 100% từ nhà mạng — Hoàn tiền ví nếu lỗi</b>\n\n"
                f"👉 Bấm /start hoặc /admin để bắt đầu trải nghiệm!",
                parse_mode="HTML"
            )
        except Exception as e:
            log.warning("Không thể gửi tin nhắn khởi động cho Admin %s: %s", aid, e)

    # Xóa webhook tồn đọng nếu có và bắt đầu Polling
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("✓ Đang bắt đầu lắng nghe tin nhắn (Polling)...")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
