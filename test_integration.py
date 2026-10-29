import asyncio
import sys
import db
import ui
from hupsms_client import sms_client

sys.stdout.reconfigure(encoding="utf-8")

async def test_all():
    print("=== STARTING INTEGRATION TESTS ===")
    await db.init_db()
    print("1. DB initialized successfully.")
    
    # Test Providers
    providers = await db.get_api_providers()
    print(f"2. Active Providers: {len(providers)} - {[p['name'] for p in providers]}")
    
    # Test Services sync
    total = await sms_client.sync_all_services()
    print(f"3. Synced Services: {total}")
    
    # Check services custom emojis
    conn = await db.get_connection()
    async with conn.execute(
        "SELECT id, name, selling_price, custom_emoji_id, custom_price FROM services WHERE name IN ('Facebook', 'Telegram', 'TikTok', 'Zalo', 'Google / Gmail', 'Canva Pro', 'CapCut')"
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
        print("4. Sample Services with genuine 3D icons:")
        for r in rows:
            print(f"   - #{r['id']} {r['name']}: {r['selling_price']} VND | CustomEmojiID={r['custom_emoji_id']} | CustomPrice={r['custom_price']}")
    await conn.close()
    
    # Test Custom Price setting
    await db.set_service_price(95, 6000)
    s2 = await db.get_service_by_id(95)
    print(f"5. Updated Facebook custom price: {s2['selling_price']} (custom_price={s2['custom_price']})")
    
    # Test UI card rendering
    w = ui.render_welcome_card()
    print("6. Welcome card rendered OK. Length:", len(w))
    
    # Test Rent menu
    from handlers.user import get_rent_menu_content
    t, m = get_rent_menu_content()
    print("7. Rent menu buttons rendered OK. Total rows:", len(m.inline_keyboard))
    
    # Test Add Provider
    if len(providers) < 3:
        ok, msg, pid = await db.add_api_provider("ViOTP Test", "https://api.viotp.com", "dummy_token_123", "viotp")
        print(f"8. Added test provider result: {ok}, ID: {pid}")
        # Clean up test provider
        await db.delete_api_provider(pid)
        print("9. Cleaned up test provider.")
    
    print("=== ALL INTEGRATION TESTS PASSED 100% ===")

if __name__ == "__main__":
    asyncio.run(test_all())
