# 🤖 BOT TELEGRAM THUÊ SIM OTP SMS TỰ ĐỘNG (HUPSMS.COM)

Hệ thống Bot Telegram cho thuê số điện thoại nhận mã xác nhận OTP SMS tự động 24/7, đấu nối trực tiếp API **HupSMS.com**, tích hợp cơ chế cộng biên lợi nhuận (Markup) tự động và phòng chống triệt để các lỗi kỹ thuật trong môi trường Production.

---

## 🚀 ĐẶC ĐIỂM NỔI BẬT

### 1. Phòng chống triệt để các lỗi kỹ thuật (Bug Prevention)
* **Chống Race Condition (Trừ tiền âm số dư):**
  * Áp dụng Transaction ACID (`BEGIN IMMEDIATE`) trong SQLite.
  * Chỉ cho phép thuê số khi số dư khả dụng thực tế `>=` Giá bán.
* **Chống nghẽn luồng (Non-blocking Async):**
  * Tuyệt đối không dùng `time.sleep()`.
  * Tiến trình kiểm tra OTP (Polling) chạy ngầm độc lập cho từng người dùng qua `asyncio.create_task` và `asyncio.sleep(3)`.
* **Cơ chế Timeout cứng & Hoàn tiền tự động 100%:**
  * Giới hạn thời gian chờ (120s - 180s).
  * Nếu quá thời gian mà chưa có OTP, hệ thống tự động hủy đơn trên HupSMS và hoàn tiền 100% ngay lập tức vào ví của người dùng.
* **Xử lý ngắt kết nối API an toàn:**
  * Bọc toàn bộ HTTP Request bằng `aiohttp.ClientError` với timeout kết nối 10 giây.
  * Tự động chuyển đổi giữa các endpoint dự phòng.

### 2. Cơ chế Cộng Lãi Tự Động (Markup Pricing)
* **Công thức giá bán:** `Giá_hiển_thị = Giá_gốc_hupsms + Markup (1.500đ - 2.000đ)`
* Tự động làm tròn lên hàng trăm đồng (VD: 1.250đ -> 1.300đ hoặc 1.500đ).
* Admin có thể thay đổi biên lợi nhuận bất kỳ lúc nào qua lệnh `/setmarkup 1500` hoặc `/setmarkup 2000`.

### 3. Đồng bộ 400+ dịch vụ & Icon 3D trực quan
* Tích hợp bảng ánh xạ Icon 3D tự động:
  * ✈️ **Telegram**
  * 📘 **Facebook**
  * 🎵 **TikTok**
  * 💬 **Zalo**
  * 🌐 **Google / Gmail**
  * 🛍 **Shopee**
  * 🟢 **WhatsApp**
  * 🤖 **OpenAI / ChatGPT**
  * 🍏 **Apple / iCloud**
  * 🎮 **Discord**
  * 📦 **Amazon / Alibaba**
  * 💖 **MoMo / Ngân hàng**

---

## 🛠 HƯỚNG DẪN CẤU HÌNH & QUẢN TRỊ VIÊN

### Lệnh Quản Trị Viên (Admin Commands)
* `/admin`: Mở Bảng điều khiển quản trị (Doanh thu, thành viên, đơn hàng, trạng thái API).
* `/sync`: Đồng bộ lại toàn bộ danh sách dịch vụ và tính lại giá bán từ HupSMS.
* `/setmarkup <số_tiền>`: Đổi mức lợi nhuận cộng thêm (VD: `/setmarkup 2000`).
* `/settimeout <giây>`: Đổi thời gian chờ OTP trước khi tự động hoàn tiền (VD: `/settimeout 180`).
* `/addbal <user_id> <số_tiền>`: Cộng tiền thủ công vào ví người dùng (VD: `/addbal 8754685711 50000`).
* `/subbal <user_id> <số_tiền>`: Trừ tiền người dùng.
* `/setbank <ngân_hàng> <stk> <chủ_tk>`: Cài đặt tài khoản ngân hàng nhận tiền nạp tự động (VietQR).

---

## 📦 THÔNG TIN BÀN GIAO
* **Bot Username:** [@thueotpvip2026_bot](https://t.me/thueotpvip2026_bot) (`SMS GIÁ RẺ`)
* **Bot Token:** Được lưu trữ bảo mật trong file `.env`
* **Admin Telegram ID:** `8754685711` (`@useralex199`)
* **Thư mục dự án:** `C:\Users\adin\.gemini\antigravity\scratch\hupsms_otp_bot`
