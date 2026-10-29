import asyncio
import io
import logging
import sys
import aiohttp
import aiogram
from PIL import Image, ImageDraw
from aiogram.types import BufferedInputFile, InputSticker
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

from config import BOT_TOKEN, ADMIN_IDS
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 8754685711

# Brand mappings: (keyword_list, brand_name, domain, fallback_emoji)
BRANDS = [
    (["facebook", "fb", "meta"], "Facebook", "facebook.com", "📘"),
    (["telegram", "tele"], "Telegram", "telegram.org", "✈️"),
    (["tiktok", "tik tok"], "TikTok", "tiktok.com", "🎵"),
    (["zalo"], "Zalo", "zalo.me", "💬"),
    (["google", "youtube"], "Google", "google.com", "🌐"),
    (["gmail"], "Gmail", "mail.google.com", "📧"),
    (["shopee", "shopeepay"], "Shopee", "shopee.vn", "🛍"),
    (["whatsapp", "wa"], "WhatsApp", "whatsapp.com", "🟢"),
    (["openai", "chatgpt", "gpt"], "OpenAI", "chatgpt.com", "🤖"),
    (["discord"], "Discord", "discord.com", "🎮"),
    (["apple", "icloud"], "Apple", "apple.com", "🍏"),
    (["amazon", "aws"], "Amazon", "amazon.com", "📦"),
    (["alibaba", "aliexpress", "taobao"], "Alibaba", "alibaba.com", "🏮"),
    (["lazada"], "Lazada", "lazada.vn", "🛒"),
    (["momo"], "MoMo", "momo.vn", "💖"),
    (["mbbank", "vietcombank", "bank"], "MBBank", "mbbank.com.vn", "🏦"),
    (["twitter", "x.com"], "Twitter", "x.com", "✖️"),
    (["instagram", "insta"], "Instagram", "instagram.com", "📸"),
    (["microsoft", "outlook", "hotmail"], "Microsoft", "microsoft.com", "💼"),
    (["netflix"], "Netflix", "netflix.com", "🎬"),
    (["spotify"], "Spotify", "spotify.com", "🎧"),
    (["tinder"], "Tinder", "tinder.com", "🔥"),
    (["steam"], "Steam", "steampowered.com", "🕹"),
    (["canva"], "Canva", "canva.com", "🎨"),
    (["capcut"], "CapCut", "capcut.com", "✂️"),
    (["be"], "Be", "be.com.vn", "🚕"),
    (["grab"], "Grab", "grab.com", "🚗"),
    (["garena"], "Garena", "garena.vn", "🐚"),
]

def make_rounded_icon(raw_bytes: bytes | None, brand_name: str) -> bytes:
    canvas = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    bg = Image.new("RGBA", (92, 92), (255, 255, 255, 255))
    mask = Image.new("L", (92, 92), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle((0, 0, 91, 91), radius=22, fill=255)
    canvas.paste(bg, (4, 4), mask)

    if raw_bytes:
        try:
            im = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            im = im.resize((76, 76), Image.Resampling.LANCZOS)
            canvas.paste(im, (12, 12), im)
            out = io.BytesIO()
            canvas.save(out, format="PNG")
            return out.getvalue()
        except Exception as e:
            log.warning("Image resize error for %s: %s", brand_name, e)

    # Fallback letter
    d = ImageDraw.Draw(canvas)
    d.text((30, 26), brand_name[:2].upper(), fill=(20, 20, 20, 255))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()

async def fetch_favicon(session: aiohttp.ClientSession, domain: str) -> bytes | None:
    urls = [
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        f"https://icon.horse/icon/{domain}",
    ]
    for url in urls:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.read()
                    if len(data) > 100:
                        return data
        except Exception:
            pass
    return None

async def main():
    bot = aiogram.Bot(BOT_TOKEN)
    me = await bot.get_me()
    pack_name = f"sms_icons_by_{me.username}"
    log.info("Target sticker pack: %s for bot @%s", pack_name, me.username)

    # 1. Check existing stickers in pack
    try:
        sset = await bot.get_sticker_set(pack_name)
        existing_stickers = sset.stickers
        log.info("Pack currently has %d stickers", len(existing_stickers))
    except Exception as e:
        log.error("Could not get sticker set: %s", e)
        await bot.session.close()
        return

    # 2. Add brand icons one by one if not already added
    # We will upload the icons with unique filenames
    added_count = 0
    # To keep track of added brands, let's see how many we have:
    current_count = len(existing_stickers)
    # The first 2 were Facebook and Telegram
    brands_to_add = BRANDS[current_count:] if current_count < len(BRANDS) else []

    async with aiohttp.ClientSession() as session:
        for keywords, name, domain, emo in brands_to_add:
            log.info("Fetching and uploading icon for %s (%s)...", name, domain)
            raw = await fetch_favicon(session, domain)
            png = make_rounded_icon(raw, name)
            try:
                ok = await bot.add_sticker_to_set(
                    user_id=ADMIN_ID,
                    name=pack_name,
                    sticker=InputSticker(
                        sticker=BufferedInputFile(png, filename=f"brand_{name.lower()}.png"),
                        format="static",
                        emoji_list=[emo]
                    )
                )
                log.info("Added %s: %s", name, ok)
                added_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                log.warning("Failed to add %s: %s", name, e)

    # 3. Retrieve the full updated sticker set to map every brand to its custom_emoji_id
    sset = await bot.get_sticker_set(pack_name)
    log.info("Final sticker count in pack: %d", len(sset.stickers))

    emoji_map = {}
    for i, sticker in enumerate(sset.stickers):
        if i < len(BRANDS):
            b_name = BRANDS[i][1]
            emoji_map[b_name.lower()] = sticker.custom_emoji_id
            log.info("Mapped %s -> custom_emoji_id: %s", b_name, sticker.custom_emoji_id)

    # 4. Save to Database and update services
    db_path = r"C:\Users\adin\.gemini\antigravity\scratch\hupsms_otp_bot\hupsms_otp.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Add column custom_emoji_id to services if not exists
    try:
        cur.execute("ALTER TABLE services ADD COLUMN custom_emoji_id TEXT")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE services ADD COLUMN custom_price INTEGER DEFAULT NULL")
    except Exception:
        pass

    # Update services with the real brand custom_emoji_id
    for keywords, b_name, domain, emo in BRANDS:
        cid = emoji_map.get(b_name.lower())
        if not cid:
            continue
        for kw in keywords:
            cur.execute("""
                UPDATE services 
                SET custom_emoji_id = ?
                WHERE LOWER(name) LIKE ?
            """, (cid, f"%{kw}%"))

    # Also update system_config with key app custom_emoji_ids
    for b_name, cid in emoji_map.items():
        cur.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (f"emoji_{b_name}", cid))

    conn.commit()
    conn.close()
    log.info("Updated database services with genuine 3D custom emojis!")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
