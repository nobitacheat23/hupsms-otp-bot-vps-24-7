import os
import math
import uuid
import logging
import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from config import (
    DB_PATH,
    DEFAULT_MARKUP,
    ORDER_TIMEOUT_SECONDS,
    DEFAULT_BANK_NAME,
    DEFAULT_BANK_ACC,
    DEFAULT_BANK_OWNER,
    HUPSMS_API_KEY,
    HUPSMS_BASE_URL,
)

log = logging.getLogger(__name__)

async def get_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA synchronous = NORMAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn

async def init_db():
    conn = await get_connection()
    try:
        await conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0 CHECK(balance >= 0),
            total_spent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT NOT NULL,
            api_type TEXT NOT NULL DEFAULT 'hupsms', -- 'hupsms', 'viotp', 'chothuesimcode', 'generic'
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            server TEXT DEFAULT 'Server 1',
            original_price INTEGER NOT NULL,
            selling_price INTEGER NOT NULL,
            custom_price INTEGER DEFAULT NULL,
            icon_3d TEXT DEFAULT '📱',
            custom_emoji_id TEXT DEFAULT NULL,
            category TEXT DEFAULT 'HOT',
            timeout_minutes INTEGER DEFAULT 3,
            is_active INTEGER DEFAULT 1,
            provider_id INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            selling_price INTEGER NOT NULL,
            hupsms_order_id TEXT,
            provider_id INTEGER DEFAULT 1,
            phone_number TEXT,
            otp_code TEXT,
            sms_content TEXT,
            status TEXT NOT NULL, -- WAITING, SUCCESS, TIMEOUT, CANCELED, FAILED
            is_rerent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            completed_at TIMESTAMP,
            msg_chat_id INTEGER,
            msg_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            trans_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            type TEXT NOT NULL, -- HOLD_BALANCE, REFUND_BALANCE, CHARGE_SUCCESS, DEPOSIT, ADMIN_ADJUST
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS deposit_requests (
            code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS proxy_packages (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            proxy_type TEXT NOT NULL, -- 'static' hoặc 'rotating'
            country TEXT DEFAULT 'VN',
            protocol TEXT DEFAULT 'HTTP/SOCKS5',
            original_price INTEGER NOT NULL,
            selling_price INTEGER NOT NULL,
            custom_price INTEGER DEFAULT NULL,
            duration_days INTEGER DEFAULT 1,
            description TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS proxy_orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            package_id INTEGER NOT NULL,
            package_name TEXT NOT NULL,
            proxy_type TEXT NOT NULL,
            selling_price INTEGER NOT NULL,
            proxy_data TEXT NOT NULL, -- IP:PORT:USER:PASS
            rotate_url TEXT,
            protocol TEXT DEFAULT 'HTTP/SOCKS5',
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active);
        CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_proxy_orders_user ON proxy_orders(user_id);
        """)

        # Migration columns if table existed previously without them
        for col_def in [
            ("services", "custom_price", "INTEGER DEFAULT NULL"),
            ("services", "custom_emoji_id", "TEXT DEFAULT NULL"),
            ("services", "provider_id", "INTEGER DEFAULT 1"),
            ("orders", "provider_id", "INTEGER DEFAULT 1"),
            ("orders", "is_rerent", "INTEGER DEFAULT 0"),
        ]:
            tbl, col, dt = col_def
            try:
                await conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {dt}")
            except Exception:
                pass
        
        # Seed default provider 1 (HupSMS) if api_providers is empty
        async with conn.execute("SELECT COUNT(*) as c FROM api_providers") as cur:
            p_count = (await cur.fetchone())["c"]
        if p_count == 0:
            await conn.execute(
                """
                INSERT INTO api_providers (id, name, base_url, api_key, api_type, is_active, priority)
                VALUES (1, 'HupSMS Main', ?, ?, 'hupsms', 1, 1)
            """,
                (HUPSMS_BASE_URL, HUPSMS_API_KEY or ""),
            )

        # Thiết lập cấu hình mặc định nếu chưa có
        defaults = {
            "markup_amount": str(DEFAULT_MARKUP),
            "order_timeout_seconds": str(ORDER_TIMEOUT_SECONDS),
            "min_deposit_amount": "50000",
            "proxy_multiplier": "2.0",
            "bank_name": DEFAULT_BANK_NAME,
            "bank_acc": DEFAULT_BANK_ACC,
            "bank_owner": DEFAULT_BANK_OWNER,
        }
        for k, v in defaults.items():
            await conn.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)", (k, v))

        # Khởi tạo danh mục Proxy chuẩn nếu bảng proxy_packages trống
        async with conn.execute("SELECT COUNT(*) as c FROM proxy_packages") as cur:
            pkg_count = (await cur.fetchone())["c"]
        if pkg_count == 0:
            standard_proxies = [
                # ID, Name, Type, Country, Protocol, Original_Price, Selling_Price, Days, Description
                (1, "Proxy Tĩnh IPv4 Việt Nam (1 Ngày)", "static", "VN", "HTTP/SOCKS5", 5000, 10000, 1, "Việt Nam (Viettel/VNPT/FPT) 100Mbps IPv4 Dedicated"),
                (2, "Proxy Tĩnh IPv4 Việt Nam (30 Ngày)", "static", "VN", "HTTP/SOCKS5", 35000, 70000, 30, "Việt Nam IPv4 riêng tư 30 ngày, nuôi acc sạch 100%"),
                (3, "Proxy Tĩnh Dân Cư Quốc Tế (US/SG - 30 Ngày)", "static", "US/SG", "HTTP/SOCKS5", 45000, 90000, 30, "Dân cư tĩnh sạch US/Singapore, làm MMO, Survey, Ads"),
                (4, "Proxy Tĩnh IPv6 Siêu Rẻ (30 Ngày)", "static", "Global", "HTTP/SOCKS5", 5000, 10000, 30, "IPv6 tốc độ cao nuôi nick Facebook/TikTok số lượng lớn"),
                (5, "Proxy Xoay Dân Cư VN VIP (1 Giờ)", "rotating", "VN", "HTTP/SOCKS5", 3000, 6000, 1, "Tự xoay IP mỗi 1-5 phút hoặc đổi IP tức thì qua link API"),
                (6, "Proxy Xoay Dân Cư VN VIP (1 Ngày)", "rotating", "VN", "HTTP/SOCKS5", 15000, 30000, 1, "Đổi IP không giới hạn, kèm link đổi IP tức thì qua 1 chạm"),
                (7, "Proxy Xoay Dân Cư VN VIP (7 Ngày)", "rotating", "VN", "HTTP/SOCKS5", 80000, 160000, 7, "Nuôi dàn tài khoản, reg nick hàng loạt không lo checkpoint"),
                (8, "Proxy Xoay 4G/5G Di Động Siêu Sạch (1 Ngày)", "rotating", "VN", "HTTP/SOCKS5", 25000, 50000, 1, "Dải IP mạng di động Viettel/VinaPhone, Trust 100%, chống khóa nick"),
                (9, "Proxy Xoay Dân Cư Quốc Tế (US/Global - 1 Ngày)", "rotating", "Global", "HTTP/SOCKS5", 20000, 40000, 1, "Đổi IP toàn cầu hơn 50+ quốc gia, crawl data, reg acc ngoại"),
            ]
            for pid, pname, ptype, pcountry, pproto, porig, psell, pdays, pdesc in standard_proxies:
                await conn.execute("""
                    INSERT OR REPLACE INTO proxy_packages (id, name, proxy_type, country, protocol, original_price, selling_price, duration_days, description, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (pid, pname, ptype, pcountry, pproto, porig, psell, pdays, pdesc))

        await conn.commit()
    finally:
        await conn.close()

# ==============================================================================
# QUẢN LÝ NHÀ CUNG CẤP API NGUỒN (TỐI ĐA 3 API)
# ==============================================================================
async def get_api_providers(active_only: bool = False) -> List[dict]:
    conn = await get_connection()
    try:
        sql = "SELECT * FROM api_providers WHERE is_active = 1 ORDER BY priority ASC, id ASC" if active_only else "SELECT * FROM api_providers ORDER BY priority ASC, id ASC"
        async with conn.execute(sql) as cur:
            return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

async def get_api_provider_by_id(provider_id: int) -> Optional[dict]:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT * FROM api_providers WHERE id = ?", (provider_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()

async def add_api_provider(name: str, base_url: str, api_key: str, api_type: str = "hupsms") -> tuple[bool, str, int]:
    """Thêm một API web mới (Tối đa 3 API)."""
    conn = await get_connection()
    try:
        async with conn.execute("SELECT COUNT(*) as c FROM api_providers") as cur:
            c = (await cur.fetchone())["c"]
        if c >= 3:
            return False, "Hệ thống chỉ hỗ trợ tối đa 3 API nhà cung cấp.", 0
        
        cur = await conn.execute(
            "INSERT INTO api_providers (name, base_url, api_key, api_type, is_active, priority) VALUES (?, ?, ?, ?, 1, ?)",
            (name.strip(), base_url.strip().rstrip("/"), api_key.strip(), api_type.strip().lower(), c + 1)
        )
        new_id = cur.lastrowid
        await conn.commit()
        return True, "Thêm API thành công", new_id
    except Exception as e:
        return False, str(e), 0
    finally:
        await conn.close()

async def toggle_api_provider(provider_id: int) -> bool:
    conn = await get_connection()
    try:
        await conn.execute("UPDATE api_providers SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (provider_id,))
        await conn.commit()
        return True
    finally:
        await conn.close()

async def delete_api_provider(provider_id: int) -> bool:
    conn = await get_connection()
    try:
        await conn.execute("DELETE FROM api_providers WHERE id = ?", (provider_id,))
        await conn.commit()
        return True
    finally:
        await conn.close()

# ==============================================================================
# QUẢN LÝ GIÁ DỊCH VỤ THỦ CÔNG (ADMIN TỰ SET GIÁ)
# ==============================================================================
async def set_service_price(service_id: int, custom_price: int) -> bool:
    """Admin đặt giá bán thủ công cho từng dịch vụ cụ thể."""
    conn = await get_connection()
    try:
        await conn.execute("""
            UPDATE services 
            SET custom_price = ?, selling_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (custom_price, custom_price, service_id))
        await conn.commit()
        return True
    finally:
        await conn.close()

async def reset_service_price(service_id: int) -> bool:
    """Xóa giá tùy chỉnh, quay về công thức Giá_gốc + Markup."""
    conn = await get_connection()
    try:
        markup = int(await get_config("markup_amount", str(DEFAULT_MARKUP)))
        async with conn.execute("SELECT original_price FROM services WHERE id = ?", (service_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            orig = row["original_price"]
        
        # Tính lại markup
        raw = orig + markup
        rem = raw % 100
        if rem > 0:
            raw = raw + (100 - rem)
        new_sell = max(raw, 2000)

        await conn.execute("""
            UPDATE services 
            SET custom_price = NULL, selling_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_sell, service_id))
        await conn.commit()
        return True
    finally:
        await conn.close()

async def get_service_by_id(service_id: int) -> Optional[dict]:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()

# ==============================================================================
# USER MANAGEMENT & ACID TRANSACTIONS (CHỐNG LỖI RACE CONDITION)
# ==============================================================================
async def get_or_create_user(telegram_id: int, username: str = "") -> dict:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            if row:
                if username and row["username"] != username:
                    await conn.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
                    await conn.commit()
                return dict(row)
        
        await conn.execute(
            "INSERT INTO users (telegram_id, username, balance, total_spent) VALUES (?, ?, 0, 0)",
            (telegram_id, username or "")
        )
        await conn.commit()
        async with conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            return dict(await cur.fetchone())
    finally:
        await conn.close()

async def hold_balance_for_rent(user_id: int, price: int, order_id: str, service_name: str) -> tuple[bool, str, int]:
    conn = await get_connection()
    try:
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await conn.rollback()
                return False, "Không tìm thấy người dùng", 0
            
            cur_bal = row["balance"]
            if cur_bal < price:
                await conn.rollback()
                return False, f"Số dư không đủ. Cần {price:,}đ (Hiện có: {cur_bal:,}đ)", cur_bal
            
            new_bal = cur_bal - price
            await conn.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_bal, user_id))
            
            tid = f"TX_HOLD_{uuid.uuid4().hex[:8]}"
            await conn.execute(
                "INSERT INTO transactions (trans_id, user_id, amount, balance_after, type, description) VALUES (?, ?, ?, ?, ?, ?)",
                (tid, user_id, -price, new_bal, "HOLD_BALANCE", f"Tạm giữ thuê OTP {service_name} (#{order_id})")
            )
            await conn.commit()
            return True, "Tạm giữ số dư thành công", new_bal
    except Exception as e:
        await conn.rollback()
        log.error("Transaction error in hold_balance_for_rent: %s", e)
        return False, f"Lỗi hệ thống khi trừ tiền: {e}", 0
    finally:
        await conn.close()

async def refund_balance(user_id: int, price: int, order_id: str, reason: str = "Hết hạn / Hủy đơn") -> tuple[bool, int]:
    conn = await get_connection()
    try:
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await conn.rollback()
                return False, 0
            
            new_bal = row["balance"] + price
            await conn.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_bal, user_id))
            
            tid = f"TX_REFUND_{uuid.uuid4().hex[:8]}"
            await conn.execute(
                "INSERT INTO transactions (trans_id, user_id, amount, balance_after, type, description) VALUES (?, ?, ?, ?, ?, ?)",
                (tid, user_id, price, new_bal, "REFUND_BALANCE", f"Hoàn tiền đơn #{order_id}: {reason}")
            )
            await conn.commit()
            return True, new_bal
    except Exception as e:
        await conn.rollback()
        log.error("Transaction error in refund_balance: %s", e)
        return False, 0
    finally:
        await conn.close()

async def charge_order_success(order_id: str):
    conn = await get_connection()
    try:
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT user_id, selling_price FROM orders WHERE order_id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
            if row:
                uid, price = row["user_id"], row["selling_price"]
                await conn.execute("UPDATE users SET total_spent = total_spent + ? WHERE telegram_id = ?", (price, uid))
                await conn.execute("UPDATE orders SET status = 'SUCCESS', completed_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))
                
                tid = f"TX_SUCCESS_{uuid.uuid4().hex[:8]}"
                async with conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (uid,)) as cur2:
                    bal_row = await cur2.fetchone()
                    cur_bal = bal_row["balance"] if bal_row else 0
                await conn.execute(
                    "INSERT INTO transactions (trans_id, user_id, amount, balance_after, type, description) VALUES (?, ?, 0, ?, ?, ?)",
                    (tid, uid, cur_bal, "CHARGE_SUCCESS", f"Hoàn tất đơn OTP thành công #{order_id}")
                )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        log.error("Transaction error in charge_order_success: %s", e)
    finally:
        await conn.close()

async def adjust_user_balance(user_id: int, amount: int, admin_name: str = "Admin") -> tuple[bool, int, str]:
    conn = await get_connection()
    try:
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await conn.rollback()
                return False, 0, "Người dùng không tồn tại"
            
            cur_bal = row["balance"]
            new_bal = cur_bal + amount
            if new_bal < 0:
                await conn.rollback()
                return False, cur_bal, f"Số dư không thể âm (Hiện có: {cur_bal:,}đ)"
            
            await conn.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_bal, user_id))
            tid = f"TX_ADM_{uuid.uuid4().hex[:8]}"
            ttype = "ADMIN_ADD" if amount >= 0 else "ADMIN_SUB"
            await conn.execute(
                "INSERT INTO transactions (trans_id, user_id, amount, balance_after, type, description) VALUES (?, ?, ?, ?, ?, ?)",
                (tid, user_id, amount, new_bal, ttype, f"{admin_name} điều chỉnh số dư: {amount:+,}đ")
            )
            await conn.commit()
            return True, new_bal, "Thành công"
    except Exception as e:
        await conn.rollback()
        log.error("Adjust balance error: %s", e)
        return False, 0, str(e)
    finally:
        await conn.close()

# ==============================================================================
# LỊCH SỬ ĐƠN HÀNG & THUÊ LẠI SỐ CŨ
# ==============================================================================
async def get_order_by_id(order_id: str) -> Optional[dict]:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()

async def get_completed_orders_for_user(user_id: int, limit: int = 10) -> List[dict]:
    conn = await get_connection()
    try:
        async with conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND phone_number IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

# ==============================================================================
# CONFIG & STATS
# ==============================================================================
async def get_config(key: str, default: str = "") -> str:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row["value"] if row else default
    finally:
        await conn.close()

async def set_config(key: str, value: str):
    conn = await get_connection()
    try:
        await conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, str(value)))
        await conn.commit()
    finally:
        await conn.close()

async def get_system_stats() -> dict:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT COUNT(*) as c, SUM(balance) as b, SUM(total_spent) as s FROM users") as cur:
            u_row = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'SUCCESS'") as cur:
            ord_succ = (await cur.fetchone())["c"]
        async with conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'WAITING'") as cur:
            ord_wait = (await cur.fetchone())["c"]
        async with conn.execute("SELECT COUNT(*) as c FROM services WHERE is_active = 1") as cur:
            srv_count = (await cur.fetchone())["c"]
        async with conn.execute("SELECT COUNT(*) as c FROM api_providers WHERE is_active = 1") as cur:
            p_count = (await cur.fetchone())["c"]
        
        return {
            "total_users": u_row["c"] or 0,
            "total_user_balance": u_row["b"] or 0,
            "total_revenue": u_row["s"] or 0,
            "success_orders": ord_succ,
            "waiting_orders": ord_wait,
            "active_services": srv_count,
            "active_providers": p_count
        }
    finally:
        await conn.close()

# ==============================================================================
# QUẢN LÝ MỨC NẠP TỐI THIỂU (MIN DEPOSIT) DO ADMIN CHỌN
# ==============================================================================
async def get_min_deposit() -> int:
    val = await get_config("min_deposit_amount", "50000")
    try:
        return max(1000, int(val))
    except Exception:
        return 50000

async def set_min_deposit(amount: int):
    await set_config("min_deposit_amount", str(max(1000, amount)))

# ==============================================================================
# QUẢN LÝ GÓI PROXY & GIÁ BÁN (MẶC ĐỊNH X2 HOẶC ADMIN TỰ CHỈNH)
# ==============================================================================
async def get_proxy_multiplier() -> float:
    val = await get_config("proxy_multiplier", "2.0")
    try:
        return max(1.0, float(val))
    except Exception:
        return 2.0

async def set_proxy_multiplier(multiplier: float):
    mult = max(1.0, float(multiplier))
    await set_config("proxy_multiplier", str(mult))
    conn = await get_connection()
    try:
        async with conn.execute("SELECT id, original_price, custom_price FROM proxy_packages") as cur:
            rows = await cur.fetchall()
            for r in rows:
                if not r["custom_price"] or r["custom_price"] <= 0:
                    new_sell = int(round(r["original_price"] * mult, -2))
                    await conn.execute("UPDATE proxy_packages SET selling_price = ? WHERE id = ?", (new_sell, r["id"]))
        await conn.commit()
    finally:
        await conn.close()

async def get_proxy_packages(proxy_type: Optional[str] = None, active_only: bool = True) -> List[dict]:
    conn = await get_connection()
    try:
        conditions = []
        params = []
        if active_only:
            conditions.append("is_active = 1")
        if proxy_type:
            conditions.append("proxy_type = ?")
            params.append(proxy_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM proxy_packages {where} ORDER BY id ASC"
        async with conn.execute(sql, tuple(params)) as cur:
            return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

async def get_proxy_package_by_id(pkg_id: int) -> Optional[dict]:
    conn = await get_connection()
    try:
        async with conn.execute("SELECT * FROM proxy_packages WHERE id = ?", (pkg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()

async def set_proxy_custom_price(pkg_id: int, custom_price: int) -> bool:
    """Admin đặt giá bán riêng cho từng gói Proxy."""
    conn = await get_connection()
    try:
        pkg = await get_proxy_package_by_id(pkg_id)
        if not pkg:
            return False
        if custom_price and custom_price > 0:
            await conn.execute("UPDATE proxy_packages SET custom_price = ?, selling_price = ? WHERE id = ?", (custom_price, custom_price, pkg_id))
        else:
            mult = await get_proxy_multiplier()
            orig = pkg["original_price"]
            sell = int(round(orig * mult, -2))
            await conn.execute("UPDATE proxy_packages SET custom_price = NULL, selling_price = ? WHERE id = ?", (sell, pkg_id))
        await conn.commit()
        return True
    finally:
        await conn.close()

async def create_proxy_order_record(user_id: int, pkg: dict, proxy_data: str, rotate_url: Optional[str] = None) -> tuple[bool, str, Optional[dict]]:
    """Tạo đơn mua Proxy qua ACID transaction."""
    import uuid
    from datetime import datetime, timedelta
    oid = f"PRX_{uuid.uuid4().hex[:8].upper()}"
    price = pkg["selling_price"]
    pname = pkg["name"]
    ptype = pkg["proxy_type"]
    proto = pkg.get("protocol", "HTTP/SOCKS5")
    duration = pkg.get("duration_days", 1)
    expires_at = datetime.now() + timedelta(days=duration)

    conn = await get_connection()
    try:
        # 1. Kiểm tra và trừ tiền ví người dùng
        async with conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row or row["balance"] < price:
                return False, f"Số dư ví không đủ ({fmt_vnd(row['balance'] if row else 0)}). Cần {price:,}đ để thanh toán.", None
            new_bal = row["balance"] - price

        # 2. Cập nhật số dư và lịch sử giao dịch
        await conn.execute("UPDATE users SET balance = ?, total_spent = total_spent + ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?", (new_bal, price, user_id))
        t_id = f"TRX_{uuid.uuid4().hex[:8].upper()}"
        await conn.execute("""
            INSERT INTO transactions (trans_id, user_id, amount, balance_after, type, description)
            VALUES (?, ?, ?, ?, 'CHARGE_SUCCESS', ?)
        """, (t_id, user_id, -price, new_bal, f"Mua {pname}"))

        # 3. Lưu đơn hàng proxy
        await conn.execute("""
            INSERT INTO proxy_orders (order_id, user_id, package_id, package_name, proxy_type, selling_price, proxy_data, rotate_url, protocol, status, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """, (oid, user_id, pkg["id"], pname, ptype, price, proxy_data, rotate_url, proto, expires_at.strftime("%Y-%m-%d %H:%M:%S")))

        await conn.commit()
        order_dict = {
            "order_id": oid,
            "user_id": user_id,
            "package_id": pkg["id"],
            "package_name": pname,
            "proxy_type": ptype,
            "selling_price": price,
            "proxy_data": proxy_data,
            "rotate_url": rotate_url,
            "protocol": proto,
            "duration_days": duration,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        return True, "Thành công", order_dict
    except Exception as e:
        log.error("create_proxy_order_record error: %s", e)
        return False, f"Lỗi hệ thống: {e}", None
    finally:
        await conn.close()

async def get_user_proxy_orders(user_id: int, limit: int = 10) -> List[dict]:
    conn = await get_connection()
    try:
        async with conn.execute("""
            SELECT * FROM proxy_orders 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()
