# ============================================
# ZOOM BOT - 1,000 BOTS PER ACCOUNT
# WITH INDIAN NAMES
# ============================================

import os
import asyncio
import random
import gc
from datetime import datetime
from playwright.async_api import async_playwright
from faker import Faker

# ----- FAKER SETUP (INDIAN NAMES) -----
fake = Faker('en_IN')  # Indian English locale

# ----- SETTINGS (RAILWAY VARIABLES) -----
MEETING_CODE = os.getenv("MEETING_CODE", "123456789")
PASSCODE = os.getenv("PASSCODE", "1234")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "60"))
BOTS_PER_REPLICA = int(os.getenv("BOTS_PER_REPLICA", "24"))
REPLICA_ID = int(os.getenv("REPLICA_ID", "0"))
# ----------------------------------------

TOTAL_BOTS = 1000

# Last replica (42nd) mein bache hue bots
if REPLICA_ID == 41:
    ACTUAL_BOTS = TOTAL_BOTS - (BOTS_PER_REPLICA * 41)  # 1000 - 984 = 16
else:
    ACTUAL_BOTS = BOTS_PER_REPLICA  # 24 bots

print(f"🚀 Replica {REPLICA_ID+1}/42 - {ACTUAL_BOTS} bots starting...")

# ============================================
# INDIAN NAME GENERATOR
# ============================================

def generate_indian_name():
    """Generate a realistic Indian name using faker"""
    
    # Faker se random Indian name
    full_name = fake.name()
    
    # Extra Indian names ka pool (safety fallback)
    indian_names = [
        "Aarav Sharma", "Vivaan Verma", "Aditya Patel", "Vihaan Kumar", 
        "Arjun Singh", "Reyansh Reddy", "Ayaan Gupta", "Krishna Joshi",
        "Ishaan Malhotra", "Shaurya Mehta", "Rahul Chopra", "Rohan Khanna",
        "Priya Agarwal", "Ananya Jain", "Diya Saxena", "Saanvi Bansal",
        "Aadhya Srivastava", "Kavya Mishra", "Riya Pandey", "Anika Rao",
        "Amit Shah", "Rajesh Kumar", "Sneha Reddy", "Pooja Singh",
        "Neha Gupta", "Vikram Sharma", "Karan Verma", "Manish Patel",
        "Suresh Kumar", "Deepak Singh", "Ramesh Gupta", "Sunil Joshi",
        "Anjali Sharma", "Meera Reddy", "Kavita Singh", "Rekha Gupta",
        "Naveen Kumar", "Prakash Singh", "Sanjay Gupta", "Mohan Reddy"
    ]
    
    # 70% chance faker se, 30% chance pool se
    if random.random() < 0.7:
        return full_name
    else:
        return random.choice(indian_names)

# ============================================
# BOT FUNCTION
# ============================================

async def start_bot(bot_id):
    """Start a single Zoom bot with Indian name"""
    
    try:
        async with async_playwright() as p:
            # Browser launch with memory optimization
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--mute-audio',
                    '--window-size=400,300',
                    '--max_old_space_size=128',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=PermissionPrompt',
                    '--disable-notifications',
                    '--disable-popup-blocking',
                    '--disable-camera',
                    '--disable-video-capture',
                    '--use-fake-device-for-media-stream',
                    '--use-file-for-fake-audio-capture=/dev/null',
                    '--disable-site-isolation-trials',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disk-cache-size=0',
                    '--media-cache-size=0',
                    '--single-process'
                ]
            )
            
            context = await browser.new_context(
                viewport={"width": 400, "height": 300},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            page = await context.new_page()
            
            # Zoom join URL
            zoom_url = f"https://zoom.us/wc/join/{MEETING_CODE}"
            await page.goto(zoom_url, timeout=30000)
            await asyncio.sleep(2)
            
            # ==========================================
            # INDIAN NAME INPUT
            # ==========================================
            indian_name = generate_indian_name()
            
            try:
                # Try multiple selectors for name input
                name_selectors = [
                    '//*[@id="input-for-name"]',
                    '//input[@placeholder="Enter your name"]',
                    '//input[@name="name"]',
                    '//input[@type="text"][@placeholder]'
                ]
                
                name_filled = False
                for selector in name_selectors:
                    try:
                        name_input = page.locator(f'xpath={selector}')
                        if await name_input.count() > 0:
                            await name_input.first.wait_for(state="visible", timeout=2000)
                            await name_input.first.fill(indian_name)
                            name_filled = True
                            break
                    except:
                        continue
                
                if not name_filled:
                    await page.keyboard.type(indian_name)
                    
            except Exception as e:
                # Ultimate fallback
                await page.keyboard.type(indian_name)
            
            print(f"  ├─ Bot-{bot_id}: {indian_name} ✅ Name set")
            
            # ==========================================
            # PASSCODE INPUT
            # ==========================================
            if PASSCODE and PASSCODE != "" and PASSCODE != "0":
                try:
                    await asyncio.sleep(0.5)
                    passcode_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/div[2]/div/input'
                    pass_input = page.locator(f'xpath={passcode_xpath}')
                    if await pass_input.count() > 0:
                        await pass_input.fill(PASSCODE)
                except:
                    pass
            
            # ==========================================
            # JOIN BUTTON CLICK
            # ==========================================
            try:
                join_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/button'
                join_btn = page.locator(f'xpath={join_xpath}')
                if await join_btn.count() > 0:
                    await join_btn.click()
                else:
                    await page.keyboard.press('Enter')
            except:
                await page.keyboard.press('Enter')
            
            print(f"  ├─ Bot-{bot_id}: {indian_name} ✅ Joined meeting")
            
            # ==========================================
            # STAY IN MEETING
            # ==========================================
            elapsed = 0
            while elapsed < DURATION_MINUTES * 60:
                await asyncio.sleep(10)
                elapsed += 10
                
                # Keep connection alive
                if elapsed % 60 == 0:
                    try:
                        await page.evaluate("() => 'ping'")
                    except:
                        break
            
            print(f"  └─ Bot-{bot_id}: {indian_name} ✅ Done")
            
            # ==========================================
            # CLEANUP
            # ==========================================
            await page.close()
            await context.close()
            await browser.close()
            gc.collect()
            
    except Exception as e:
        print(f"  └─ Bot-{bot_id} ❌ Failed: {e}")

# ============================================
# MAIN FUNCTION
# ============================================

async def main():
    """Start all bots for this replica"""
    
    print("="*60)
    print(f"🚀 REPLICA {REPLICA_ID+1}/42 - {ACTUAL_BOTS} BOTS")
    print("="*60)
    print(f"📌 Meeting: {MEETING_CODE}")
    print(f"⏱️ Duration: {DURATION_MINUTES} minutes")
    print(f"👥 Bots in this replica: {ACTUAL_BOTS}")
    print("="*60 + "\n")
    
    # Start all bots with staggered timing
    tasks = []
    for i in range(ACTUAL_BOTS):
        bot_id = (REPLICA_ID * BOTS_PER_REPLICA) + i + 1
        task = asyncio.create_task(start_bot(bot_id))
        tasks.append(task)
        await asyncio.sleep(0.2)  # 200ms gap between bots
    
    # Wait for all bots to complete
    await asyncio.gather(*tasks)
    
    print(f"\n✅ Replica {REPLICA_ID+1} completed!")

# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")