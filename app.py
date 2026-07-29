from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import threading
import asyncio
import os
import random
import base64
import gc
import signal
import psutil
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import nest_asyncio
import uvicorn
from typing import List, Optional
from pathlib import Path

nest_asyncio.apply()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# SCREENSHOT DIRECTORY
# ============================================
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# INDIAN NAMES
# ============================================
INDIAN_FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Reyansh', 'Ayaan', 
    'Krishna', 'Ishaan', 'Shaurya', 'Rahul', 'Rohan', 'Priya', 'Ananya',
    'Diya', 'Saanvi', 'Aadhya', 'Kavya', 'Riya', 'Anika', 'Amit', 'Rajesh',
    'Sneha', 'Pooja', 'Neha', 'Vikram', 'Karan', 'Manish', 'Suresh', 'Deepak'
]

INDIAN_LAST_NAMES = [
    'Sharma', 'Verma', 'Patel', 'Kumar', 'Singh', 'Reddy', 'Gupta', 'Joshi',
    'Malhotra', 'Mehta', 'Chopra', 'Khanna', 'Agarwal', 'Jain', 'Saxena',
    'Bansal', 'Srivastava', 'Mishra', 'Pandey', 'Rao', 'Desai', 'Nair'
]

ENGLISH_FIRST_NAMES = [
    'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph',
    'Thomas', 'Charles', 'Christopher', 'Daniel', 'Matthew', 'Anthony', 'Donald',
    'Mark', 'Paul', 'Steven', 'Andrew', 'Kenneth', 'Joshua', 'Kevin', 'Brian',
    'George', 'Timothy', 'Ronald', 'Edward', 'Jason', 'Jeffrey', 'Ryan', 'Jacob'
]

ENGLISH_LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Wilson', 'Anderson', 'Thomas',
    'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White',
    'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young'
]

def get_indian_name():
    return f"{random.choice(INDIAN_FIRST_NAMES)} {random.choice(INDIAN_LAST_NAMES)}"

def get_english_name():
    return f"{random.choice(ENGLISH_FIRST_NAMES)} {random.choice(ENGLISH_LAST_NAMES)}"

def get_name(name_type):
    if name_type == "english":
        return get_english_name()
    return get_indian_name()

# ============================================
# ZOOM URL
# ============================================
ZOOM_PARTS = {
    'domain': base64.b64decode('em9vbS51cw==').decode(),
    'join_path': base64.b64decode('d2Mvam9pbg==').decode()
}

def get_zoom_url(meeting_code):
    return f"https://{ZOOM_PARTS['domain']}/{ZOOM_PARTS['join_path']}/{meeting_code}"

# ============================================
# REQUEST MODEL
# ============================================
class StartBotRequest(BaseModel):
    meeting_code: str
    passcode: str = ""
    bot_count: int
    duration_minutes: int = 5
    name_type: str = "indian"

class StopBotRequest(BaseModel):
    meeting_code: str

# ============================================
# STATE
# ============================================
active_browsers = {}  # tag -> browser object
active_meetings = {}  # meeting_code -> {start_time, bots, timeout, status}
meeting_timers = {}   # meeting_code -> timer thread
billing_enabled = True

# ============================================
# SYNC BARRIER
# ============================================
READY_TO_JOIN = asyncio.Event()
BOTS_READY = 0
BOTS_TOTAL = 0
BOTS_FAILED = 0
BOTS_LOCK = asyncio.Lock()

async def wait_for_all_bots():
    global BOTS_READY, BOTS_TOTAL, BOTS_FAILED
    async with BOTS_LOCK:
        BOTS_READY += 1
        ready = BOTS_READY
        total = BOTS_TOTAL
        failed = BOTS_FAILED

    print(f"[SYNC] {ready}/{total} bots ready (failed: {failed})")

    if ready + failed >= total:
        READY_TO_JOIN.set()
        print("⚡ All bots ready! Joining together...")

    await READY_TO_JOIN.wait()

# ============================================
# KILL ALL BROWSERS
# ============================================
def kill_all_browsers():
    """Kill all browser processes immediately"""
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'chromium' in cmdline.lower() or 'chrome' in cmdline.lower():
                if 'playwright' in cmdline.lower():
                    proc.kill()
                    killed += 1
        except:
            pass
    return killed

async def kill_meeting_browsers(meeting_code):
    """Kill all browsers associated with a meeting"""
    killed = 0
    tags_to_remove = []
    
    for tag, browser in list(active_browsers.items()):
        if tag.startswith(meeting_code):
            try:
                await browser.close()
                killed += 1
                tags_to_remove.append(tag)
            except:
                pass
    
    for tag in tags_to_remove:
        del active_browsers[tag]
    
    # Kill any leftover processes
    killed += kill_all_browsers()
    return killed

# ============================================
# BOT FUNCTION
# ============================================
async def start_bot(tag, wait_time, meetingcode, passcode, name_type="indian"):
    global BOTS_FAILED
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Started")
    gc.collect()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=PermissionPrompt',
                    '--disable-notifications',
                    '--disable-popup-blocking',
                    '--disable-camera',
                    '--disable-video-capture',
                    '--mute-audio',
                    '--use-fake-device-for-media-stream',
                    '--use-file-for-fake-audio-capture=/dev/null',
                    '--window-size=800,600',
                    '--max_old_space_size=64',
                    '--js-flags=--max-old-space-size=64',
                    '--disable-site-isolation-trials',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disk-cache-size=0',
                    '--media-cache-size=0',
                    '--single-process'
                ]
            )

            # Store browser reference
            active_browsers[tag] = browser

            context = await browser.new_context(
                viewport={"width": 800, "height": 600},
                permissions=[],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            page = await context.new_page()
            zoom_url = get_zoom_url(meetingcode)
            
            await page.goto(zoom_url, timeout=60000)
            await asyncio.sleep(2)

            # NAME INPUT
            try:
                user_name = get_name(name_type)
                name_selectors = [
                    '//*[@id="input-for-name"]',
                    '//input[@placeholder="Enter your name"]',
                    '//input[@name="name"]'
                ]
                
                name_filled = False
                for selector in name_selectors:
                    try:
                        name_input = page.locator(f'xpath={selector}')
                        if await name_input.count() > 0:
                            await name_input.first.wait_for(state="visible", timeout=3000)
                            await name_input.first.fill(user_name)
                            name_filled = True
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Name: {user_name}")
                            break
                    except:
                        continue
                
                if not name_filled:
                    await page.keyboard.type(user_name)
                    
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Name error: {e}")

            # PASSCODE INPUT
            if passcode and passcode != "" and passcode != "0":
                try:
                    await asyncio.sleep(0.5)
                    passcode_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/div[2]/div/input'
                    pass_input = page.locator(f'xpath={passcode_xpath}')
                    if await pass_input.count() > 0:
                        await pass_input.fill(passcode)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Passcode entered")
                except Exception:
                    pass

            # WAIT FOR ALL BOTS
            await wait_for_all_bots()

            # JOIN BUTTON
            try:
                join_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/button'
                join_btn = page.locator(f'xpath={join_xpath}')
                if await join_btn.count() > 0:
                    await join_btn.click()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Join clicked")
                else:
                    await page.keyboard.press('Enter')
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Enter pressed")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Join error: {e}")
                await page.keyboard.press('Enter')

            await asyncio.sleep(3)
            
            # Audio join
            try:
                audio_btn = page.locator('xpath=//button[contains(text(), "Join Audio")]')
                if await audio_btn.count() > 0:
                    await audio_btn.click()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Audio joined")
            except Exception:
                pass

            await asyncio.sleep(2)
            try:
                leave_btn = page.locator('xpath=//button[contains(text(), "Leave")]')
                if await leave_btn.count() > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - CONFIRMED: In meeting!")
            except:
                pass

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Joined! Staying for {wait_time//60} minutes")
            
            # STAY IN MEETING
            elapsed = 0
            while elapsed < wait_time:
                # Check if billing is disabled
                if not billing_enabled:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Billing disabled, stopping...")
                    break
                    
                await asyncio.sleep(10)
                elapsed += 10
                
                if elapsed % 60 == 0:
                    gc.collect()
                    try:
                        await page.evaluate("() => 'ping'")
                    except:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Ping failed")
                        break

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Done")
            
            await page.close()
            await context.close()
            await browser.close()
            gc.collect()
            
            # Remove from active browsers
            if tag in active_browsers:
                del active_browsers[tag]
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} - Failed: {str(e)[:100]}")
        BOTS_FAILED += 1
        if tag in active_browsers:
            del active_browsers[tag]

# ============================================
# API ENDPOINTS
# ============================================
@app.get("/")
async def root():
    return {"message": "Zoom Bot Worker is running!", "status": "healthy"}

@app.post("/api/start-bots")
async def start_bots(request: StartBotRequest):
    global BOTS_TOTAL, BOTS_READY, BOTS_FAILED, billing_enabled
    
    if not billing_enabled:
        raise HTTPException(status_code=403, detail="Billing is disabled")
    
    try:
        if request.bot_count < 1 or request.bot_count > 5:
            raise HTTPException(status_code=400, detail="Bot count must be between 1 and 5")
        
        BOTS_TOTAL = request.bot_count
        BOTS_READY = 0
        BOTS_FAILED = 0
        READY_TO_JOIN.clear()
        
        # Track meeting
        if request.meeting_code not in active_meetings:
            active_meetings[request.meeting_code] = {
                "start_time": datetime.now(),
                "bots": request.bot_count,
                "duration": request.duration_minutes,
                "status": "running",
                "name_type": request.name_type
            }
        else:
            active_meetings[request.meeting_code]["status"] = "running"
        
        def run_bots():
            asyncio.run(run_bot_tasks(
                request.meeting_code, 
                request.passcode, 
                request.bot_count, 
                request.duration_minutes,
                request.name_type
            ))
        
        thread = threading.Thread(target=run_bots)
        thread.daemon = True
        thread.start()
        
        return {
            "success": True,
            "message": f"Started {request.bot_count} bots for meeting {request.meeting_code}",
            "duration": request.duration_minutes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_bot_tasks(meeting_code, passcode, bot_count, duration_minutes, name_type):
    duration_seconds = duration_minutes * 60
    tasks = []
    for i in range(bot_count):
        tag = f"{meeting_code}-Bot-{i+1}"
        task = asyncio.create_task(
            start_bot(tag, duration_seconds, meeting_code, passcode, name_type)
        )
        tasks.append(task)
        await asyncio.sleep(0.5)
    
    await asyncio.gather(*tasks)
    
    # Update meeting status
    if meeting_code in active_meetings:
        active_meetings[meeting_code]["status"] = "completed"
        active_meetings[meeting_code]["completed_at"] = datetime.now().isoformat()

@app.post("/api/stop-bots")
async def stop_bots(request: StopBotRequest):
    """Kill all bots for a meeting immediately"""
    meeting_code = request.meeting_code
    
    # Kill all browsers
    killed = await kill_meeting_browsers(meeting_code)
    
    # Update meeting status
    if meeting_code in active_meetings:
        active_meetings[meeting_code]["status"] = "killed"
        active_meetings[meeting_code]["killed_at"] = datetime.now().isoformat()
    
    return {
        "success": True,
        "message": f"Stopped {killed} bots for meeting {meeting_code}",
        "bots_killed": killed
    }

@app.post("/api/toggle-billing")
async def toggle_billing(request: dict):
    global billing_enabled
    
    enabled = request.get("enabled", True)
    billing_enabled = enabled
    
    if not enabled:
        # Kill all active meetings
        killed_total = 0
        for meeting_code in list(active_meetings.keys()):
            if active_meetings[meeting_code]["status"] == "running":
                killed = await kill_meeting_browsers(meeting_code)
                killed_total += killed
                active_meetings[meeting_code]["status"] = "paused"
                active_meetings[meeting_code]["paused_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "billing_enabled": False,
            "message": f"Billing disabled. Killed {killed_total} bots.",
            "bots_killed": killed_total
        }
    
    return {
        "success": True,
        "billing_enabled": True,
        "message": "Billing enabled. System ready."
    }

@app.get("/api/status")
async def get_status():
    running_bots = len(active_browsers)
    
    # Clean up completed meetings older than 1 hour
    for code, meeting in list(active_meetings.items()):
        if meeting["status"] in ["completed", "killed"]:
            if "completed_at" in meeting:
                completed_time = datetime.fromisoformat(meeting["completed_at"])
                if (datetime.now() - completed_time).seconds > 3600:
                    del active_meetings[code]
    
    return {
        "billing_enabled": billing_enabled,
        "active_meetings": active_meetings,
        "running_bots": running_bots,
        "total_bots": sum(m["bots"] for m in active_meetings.values()),
        "meetings": list(active_meetings.keys())
    }

@app.get("/health")
async def health():
    return {
        "online": True,
        "capacity": 5,
        "worker_id": "worker"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
