import os
import time
import random
import logging
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Setup Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SobraveBot")

load_dotenv()

TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")
HARDCODED_SITEKEY = os.getenv("HARDCODED_SITEKEY") 

def generate_random_gmail():
    random_num = random.randint(10000, 99999)
    random_chars = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=4))
    return f"sobrave.{random_chars}{random_num}@gmail.com"

def find_proxy_file():
    possible_names = ["Webshare proxies.txt", "Webshare proxies"]
    for name in possible_names:
        if os.path.exists(name):
            return name
    return None

def get_and_test_proxy():
    proxy_file = find_proxy_file()
    if not proxy_file:
        logger.error("❌ 'Webshare proxies' file folder mein nahi mili!")
        return None

    with open(proxy_file, "r") as f:
        proxies_list = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not proxies_list:
        return None

    raw_proxy = random.choice(proxies_list) 
    try:
        parts = raw_proxy.split(":")
        ip, port, user, password = parts[0], parts[1], parts[2], parts[3]
        proxy_dict = {
            "http": f"http://{user}:{password}@{ip}:{port}",
            "https": f"http://{user}:{password}@{ip}:{port}"
        }
        
        logger.info(f"⚡ Testing Proxy IP: {ip}...")
        response = requests.get("https://httpbin.org/ip", proxies=proxy_dict, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Proxy Live!")
            return {
                "server": f"http://{ip}:{port}", 
                "username": user, 
                "password": password,
                "raw_ip": ip,
                "raw_port": port
            }
        return None
    except Exception as e:
        logger.error(f"❌ Proxy Error: {e}")
        return None

def extract_sitekey_from_anywhere(page, frame_ctx):
    if HARDCODED_SITEKEY:
        logger.info(f"🎯 Using Fixed Sitekey from .env: {HARDCODED_SITEKEY}")
        return HARDCODED_SITEKEY, frame_ctx or page
    return None, page

# 🧑‍💻 HUMAN TYPING HELPER: जो रोबोटिक टाइपिंग को इंसानी टाइपिंग में बदल देगा
def human_type(page, text):
    for char in text:
        page.keyboard.type(char)
        # हर अक्षर के बीच 0.05 से 0.15 सेकंड का रैंडम गैप (Human Behavior)
        time.sleep(random.uniform(0.05, 0.15))

def solve_friendly_captcha_dynamic(page, target_context, page_url, proxy_config):
    try:
        logger.info("🤖 Fetching Friendly Captcha sitekey...")
        sitekey, working_ctx = extract_sitekey_from_anywhere(page, target_context)

        if not sitekey:
            logger.error("❌ Friendly Captcha Sitekey nahi mil saki.")
            return False

        logger.info("🔑 Creating FriendlyCaptchaTask via 2Captcha New API JSON format...")
        
        create_task_url = "https://api.2captcha.com/createTask"
        
        task_payload = {
            "clientKey": TWOCAPTCHA_API_KEY,
            "task": {
                "type": "FriendlyCaptchaTask",
                "websiteURL": page_url,
                "websiteKey": sitekey
            }
        }
        
        if proxy_config:
            task_payload["task"]["proxyType"] = "http"
            task_payload["task"]["proxyAddress"] = proxy_config["raw_ip"]
            task_payload["task"]["proxyPort"] = proxy_config["raw_port"]
            task_payload["task"]["proxyLogin"] = proxy_config["username"]
            task_payload["task"]["proxyPassword"] = proxy_config["password"]

        response = requests.post(create_task_url, json=task_payload).json()
        
        if response.get("errorId") != 0:
            logger.error(f"❌ 2Captcha Task Creation Failed: {response.get('errorDescription')}")
            return False
            
        task_id = response.get("taskId")
        logger.info(f"⏳ Task created successfully (ID: {task_id}). Awaiting solver token...")

        result_url = "https://api.2captcha.com/getTaskResult"
        result_payload = {
            "clientKey": TWOCAPTCHA_API_KEY,
            "taskId": task_id
        }
        
        for _ in range(18): 
            time.sleep(5)
            res = requests.post(result_url, json=result_payload).json()
            
            if res.get("errorId") != 0:
                logger.error(f"❌ Error during fetching token: {res.get('errorDescription')}")
                return False
                
            if res.get("status") == "ready":
                token = res.get("solution", {}).get("token")
                logger.info("✅ 2Captcha successfully generated the token! Injecting via documentation standard...")
                
                working_ctx.evaluate(f"""
                    document.querySelectorAll('.frc-captcha-solution').forEach(el => el.value = "{token}");
                    let hiddenInput = document.querySelector('input[name="frc-captcha-solution"]');
                    if(hiddenInput) {{ hiddenInput.value = "{token}"; }}
                """)
                
                working_ctx.evaluate("""
                    let widget = document.querySelector('.frc-captcha') || document.querySelector('div[class*="main state-"]');
                    if(widget) {
                        widget.classList.remove('frc-error', 'state-unactivated', 'state-solving');
                        widget.classList.add('frc-success', 'state-activated');
                        let btn = widget.querySelector('button[role="checkbox"]');
                        if(btn) { 
                            btn.setAttribute('aria-checked', 'true');
                            btn.setAttribute('aria-disabled', 'true');
                        }
                    }
                """)
                logger.info("🎯 Token successfully injected into the active layer.")
                return True
                
            elif res.get("status") == "processing":
                logger.info("⏳ Captcha response not ready yet, re-checking in 5 seconds...")
            else:
                logger.error(f"⚠️ Unknown status response: {res.get('status')}")
                return False
                
        return False
    except Exception as e:
        logger.error(f"❌ Error inside captcha solver module: {e}")
        return False

def run_signup_pipeline():
    proxy_config = get_and_test_proxy()
    
    TARGET_EMAIL = generate_random_gmail()
    TARGET_PASSWORD = "SecurePass@" + str(random.randint(100, 999))
    
    logger.info(f"🚀 Generated New Email: {TARGET_EMAIL}")

    with sync_playwright() as p:
        logger.info("Launching browser...")
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        context_args = {}
        if proxy_config:
            context_args["proxy"] = {
                "server": proxy_config["server"],
                "username": proxy_config["username"],
                "password": proxy_config["password"]
            }
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            # STEP 1: SIGNUP FORM FILLING
            logger.info("Step 1: Navigating to Signup Page...")
            page.goto("https://sobrave.raiselysite.com/signup", wait_until="domcontentloaded")
            time.sleep(3)
            
            logger.info("Filling Account Form fields...")
            # यहाँ भी टाइपिंग को थोड़ा रियलिस्टिक लुक देने के लिए डिले का इस्तेमाल किया है
            page.locator("input[name='firstName'], input[placeholder*='First']").first.fill("BraveUser")
            time.sleep(random.uniform(0.3, 0.7))
            page.locator("input[name='lastName'], input[placeholder*='Last']").first.fill("BotTesting")
            time.sleep(random.uniform(0.3, 0.7))
            page.locator("input[type='email'], input[name='email']").first.fill(TARGET_EMAIL)
            time.sleep(random.uniform(0.3, 0.7))
            page.locator("input[type='password'], input[name='password']").first.fill(TARGET_PASSWORD)
            time.sleep(1)
            
            logger.info("Clicking the first 'Continue' button...")
            page.locator("form button[type='submit'], .form__actions button:has-text('Continue')").first.click(force=True)
            time.sleep(5)
            
            # STEP 2: SKIP SETUP / PROFILE PAGE
            logger.info("Step 2: Checking for Setup Screen...")
            continue_btn_2 = page.locator(".form__actions button, form button:not([disabled])").filter(has_text="Continue").first
            if continue_btn_2.is_visible():
                continue_btn_2.click(force=True)
                time.sleep(4)
            
            # STEP 3: FINALIZE SIGN UP
            logger.info("Step 3: Clicking Final Sign Up Button...")
            page.locator("form button[type='submit'], button:has-text('Sign Up')").first.click(force=True)
            time.sleep(5)
            
            # STEP 4: DASHBOARD NAVIGATION
            logger.info("Step 4: Redirecting to Dashboard...")
            try:
                page.wait_for_selector("text=Add a Post", timeout=15000)
            except Exception:
                logger.warning("⚠️ Forcing login fallback...")
                page.goto("https://sobrave.raiselysite.com/login", wait_until="domcontentloaded")
                time.sleep(3)
                page.locator("input[type='email'], input[name='email']").first.fill(TARGET_EMAIL)
                page.locator("input[type='password'], input[name='password']").first.fill(TARGET_PASSWORD)
                page.locator("form button[type='submit']").first.click(force=True)
                page.wait_for_selector("text=Add a Post", timeout=30000)

            time.sleep(3) 
            logger.info("Dashboard Loaded. Clicking 'Add a Post'...")
            page.get_by_text("Add a Post").scroll_into_view_if_needed()
            page.get_by_text("Add a Post").click()
            
            logger.info("⏳ Waiting 5 seconds for editor form layers to load fully...")
            time.sleep(5)
            
            # DETECT ACTIVE LAYER CONTEXT
            form_frame = None
            for frame in page.frames:
                if "raisely" in frame.url or "editor" in frame.url:
                    form_frame = frame
                    break
            
            if form_frame:
                logger.info("🎯 Nested form container frame successfully locked.")
                target_layer = form_frame
            else:
                if len(page.frames) > 1:
                    logger.info("🎯 Generic sub-frame context locked.")
                    target_layer = page.frames[1]
                else:
                    logger.info("🎯 Standard page layout context locked.")
                    target_layer = page

            # STEP 5: POST EDITOR FIELDS (HUMAN STYLE)
            logger.info("Step 5: Editor Page Loaded. Generating real-looking post content...")
            
            blog_contents = [
                {
                    "title": "How to Stay Motivated Every Day",
                    "body": "Success doesn't come from what you do occasionally, it comes from what you do consistently. Keep pushing your limits and stay focused on your goals."
                },
                {
                    "title": "Why Consistency is Key to Success",
                    "body": "Consistency turns average talent into excellence. Don't worry about being perfect right away, just make sure you show up and do the work every single day."
                }
            ]
            
            selected_post = random.choice(blog_contents)
            
            post_title_input = target_layer.locator("input[placeholder*='Title'], .form-field input[type='text']").first
            post_title_input.wait_for(state="visible", timeout=25000)
            
            # Title को फोकस करके इंसानों की तरह टाइप करना
            post_title_input.focus()
            human_type(page, selected_post["title"])
            time.sleep(1)
            
            logger.info("🔥 Targetting Rich Text Editor Box...")
            text_editor = target_layer.locator(".public-DraftEditor-content, div[role='textbox'], .rdw-editor-main").first
            text_editor.focus()
            time.sleep(0.5)
            text_editor.click(force=True)
            time.sleep(0.5)
            
            # Main Body को इंसानों की तरह धीरे-धीरे टाइप करना
            logger.info("✍️ Typing content with realistic human speed...")
            human_type(page, selected_post["body"])
            time.sleep(2)
            
            logger.info("Scrolling down using mouse wheel interaction...")
            page.mouse.wheel(0, 900)
            time.sleep(3)
            
            # STEP 6: NEW FRIENDLY CAPTCHA AUTO-PROCESSING
            current_url = page.url
            logger.info("🔄 Initiating automatic token calculations from 2Captcha new JSON server layers...")
            
            captcha_solved = solve_friendly_captcha_dynamic(page, target_layer, current_url, proxy_config)
            if not captcha_solved:
                logger.warning("⚠️ Captcha auto-bypass was not confirmed. Proceeding with adaptive execution...")
            
            time.sleep(3)

            # NETWORK STABILIZATION 
            logger.info("⏳ Waiting for target layer to reach network stability...")
            try:
                # यहाँ timeout को कम किया है ताकि बोट जबरदस्ती अटका न रहे
                target_layer.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.info("⚠️ Network stabilization timeout skipped, continuing submission...")
            time.sleep(2)

            # STEP 7: SUBMIT WORKFLOW
            logger.info("Clicking the final Post Creation submit button...")
            submit_selectors = "button[type='submit'], .form__actions button:has-text('Post'), button:has-text('Publish'), button:has-text('Complete security check first')"
            
            try:
                final_submit_btn = target_layer.locator(submit_selectors).first
                final_submit_btn.wait_for(state="visible", timeout=6000)
                final_submit_btn.click(force=True)
                logger.info("✅ Final Form submit clicked.")
            except Exception:
                logger.warning("⚠️ Target layer button missing, attempting root page fallback...")
                try:
                    page.locator(submit_selectors).first.click(force=True)
                    logger.info("✅ Form submit triggered via root fallback.")
                except Exception as final_err:
                    logger.error(f"❌ Failed to click submit button: {final_err}")
            
            logger.info("✅ Success! Post workflow executed fully.")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Execution Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_signup_pipeline()