import time
import random
import re
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
USER_TOKEN = os.getenv('USER_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
WAIT_TIME = float(os.getenv('WAIT_TIME', '2.2'))
KEYWORDS = ["verification", "code", "captcha", "anti-bot", "verify"]

# Known Virtual Fisher App ID
APP_ID = "574652751745777665"

# --- COMMAND IDS (fallback defaults) ---
CMD_FISH_ID = os.getenv('CMD_FISH_ID', '912432960643416115')
CMD_FISH_VER = os.getenv('CMD_FISH_VER', '1207457860208824332')

CMD_BUY_ID = os.getenv('CMD_BUY_ID', '912432961134166090')
CMD_BUY_VER = os.getenv('CMD_BUY_VER', '1207457860460744728')

CMD_SELL_ID = os.getenv('CMD_SELL_ID', '912432960643416116')
CMD_SELL_VER = os.getenv('CMD_SELL_VER', '1207457860208824333')

CMD_VERIFY_ID = os.getenv('CMD_VERIFY_ID', '912432961222238220')
CMD_VERIFY_VER = os.getenv('CMD_VERIFY_VER', '1207457860523663380')

# For features requiring extra setup:
CMD_PROFILE_ID = os.getenv('CMD_PROFILE_ID', '912432960815372338')
CMD_PROFILE_VER = os.getenv('CMD_PROFILE_VER', '1207457860460744723')

CMD_SHOP_ID = os.getenv('CMD_SHOP_ID', '912432960815372339')
CMD_SHOP_VER = os.getenv('CMD_SHOP_VER', '1207457860460744724')

# Generate a random 32-character hex session ID
SESSION_ID = "".join(random.choices("0123456789abcdef", k=32))
GUILD_ID = os.getenv('GUILD_ID', '1491654181201903646')

HEADERS = {
    'Authorization': f'{USER_TOKEN}',
    'Content-Type': 'application/json'
}

class GameState:
    def __init__(self):
        self.balance = 0
        self.level = 0
        self.bait_amount = 0
        self.bait_name = ""
        self.unowned_items = []
        self.available_baits = []

    def reset_shop_state(self):
        self.unowned_items = []
        self.available_baits = []

    def parse_profile(self, text):
        bal_match = re.search(r'Balance:\s*\$([\d,]+)', text)
        if bal_match:
            self.balance = int(bal_match.group(1).replace(',', ''))

        lvl_match = re.search(r'Level\s+(\d+)', text)
        if lvl_match:
            self.level = int(lvl_match.group(1))

        bait_match = re.search(r'Bait:(.*?)(?:\n|$)', text)
        if bait_match:
            bait_line = bait_match.group(1)
            b = re.search(r':([a-z_]+):\s*(.*?)\s*\((\d+)\)', bait_line)
            if b:
                self.bait_name = b.group(2).strip()
                self.bait_amount = int(b.group(3))

    def parse_shop(self, text, category=""):
        if "Your balance:" in text:
            bal_match = re.search(r'Your balance:\s*\$([\d,]+)', text)
            if bal_match:
                self.balance = int(bal_match.group(1).replace(',', ''))

        if category == "bait":
            baits = re.findall(r':[a-z_]+:\s*(.+?)\s*-\s*\$([\d,]+)\.', text)
            for name, price in baits:
                self.available_baits.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', ''))
                })
        else:
            items = re.findall(r':[a-z_]+:\s*(.+?)\s*-\s*\$([\d,]+)', text)
            for name, price in items:
                self.unowned_items.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', '')),
                    'type': category
                })

            upgrades = re.findall(r'\d+/\d+\s+(.+?)\s*-\s*\$([\d,]+)', text)
            for name, price in upgrades:
                self.unowned_items.append({
                    'name': name.strip(),
                    'price': int(price.replace(',', '')),
                    'type': category
                })

    def get_best_purchase(self):
        if self.unowned_items:
            self.unowned_items.sort(key=lambda x: x['price'])
            cheapest = self.unowned_items[0]
            if self.balance >= cheapest['price']:
                return cheapest
        return None

# Global game state reference
game_state = GameState()


def generate_nonce():
    """Generate a pseudo-random snowflake-like nonce string."""
    return str(random.randint(10**18, 10**19 - 1))

def get_latest_messages(limit=5):
    """Fetch the latest messages from the channel."""
    url = f'https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit={limit}'
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch messages. Status code: {response.status_code}")
        if response.status_code == 401:
            print("Unauthorized: Your user token is likely invalid or missing.")
            exit(1)
        return []

def get_my_user_info():
    """Fetch the current user's profile info to identify our own messages."""
    url = 'https://discord.com/api/v9/users/@me'
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    print("Warning: Could not fetch user profile.")
    return {}

def send_message(content):
    """Send a normal text message to the channel (e.g. for verification)."""
    url = f'https://discord.com/api/v9/channels/{CHANNEL_ID}/messages'
    payload = {
        'content': content,
        'nonce': generate_nonce(),
        'tts': False
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        print(f"Sent Message: {content}")
        return True
    else:
        print(f"Failed to send message: {response.status_code} - {response.text}")
        return False

def dispatch_slash_command(command_name, cmd_id, version, options=None):
    """Generic function to send a slash command."""
    if options is None:
        options = []

    url = 'https://discord.com/api/v9/interactions'
    payload = {
        "type": 2,
        "application_id": APP_ID,
        "channel_id": CHANNEL_ID,
        "guild_id": GUILD_ID,
        "session_id": SESSION_ID,
        "nonce": generate_nonce(),
        "data": {
            "version": version,
            "id": cmd_id,
            "name": command_name,
            "type": 1,
            "options": options,
            "application_command": {
                "id": cmd_id,
                "type": 1,
                "application_id": APP_ID,
                "version": version,
                "name": command_name
            },
            "attachments": []
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 204]:
        opts_str = " ".join([f"{o.get('name')}={o.get('value')}" for o in options])
        print(f"Sent Slash Command: /{command_name} {opts_str}".strip())
        return True
    else:
        print(f"Failed to send /{command_name}: {response.status_code} - {response.text}")
        return False

def send_slash_command():
    return dispatch_slash_command("fish", CMD_FISH_ID, CMD_FISH_VER)

def send_verify_command(code):
    return dispatch_slash_command("verify", CMD_VERIFY_ID, CMD_VERIFY_VER, [{"type": 3, "name": "answer", "value": code}])

def send_buy_command(item):
    return dispatch_slash_command("buy", CMD_BUY_ID, CMD_BUY_VER, [{"type": 3, "name": "item", "value": item}])

def send_sell_command(amount):
    return dispatch_slash_command("sell", CMD_SELL_ID, CMD_SELL_VER, [{"type": 3, "name": "amount", "value": amount}])

def send_profile_command():
    return dispatch_slash_command("profile", CMD_PROFILE_ID, CMD_PROFILE_VER)

def send_shop_command(category):
    return dispatch_slash_command("shop", CMD_SHOP_ID, CMD_SHOP_VER, [{"type": 3, "name": "category", "value": category}])

def extract_verification_code(message_text):
    """Extract a verification code from a bot message after cleaning markdown formatting."""
    # Remove markdown symbols (asterisks, underscores, backticks) to clean up formatting
    cleaned_text = re.sub(r'[\*_`]', '', message_text)

    # Specific targeted pattern for Virtual Fisher
    match = re.search(r'Code:\s*([A-Za-z0-9]+)', cleaned_text, re.IGNORECASE)
    if match:
        return match.group(1)

    code_patterns = [
        r'code[:\s]*([A-Za-z0-9]{4,8})',
        r'verification code[:\s]*([A-Za-z0-9]{4,8})',
        r'type[:\s]*([A-Za-z0-9]{4,8})',
        r'enter[:\s]*([A-Za-z0-9]{4,8})',
        r'send[:\s]*([A-Za-z0-9]{4,8})',
    ]
    for pattern in code_patterns:
        match = re.search(pattern, cleaned_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def get_image_url_from_message(msg):
    if not msg:
        return None
    for attachment in msg.get('attachments', []):
        if 'image' in attachment.get('content_type', '') or attachment.get('url', '').endswith(('.png', '.jpg', '.jpeg')):
            return attachment.get('url')
    for embed in msg.get('embeds', []):
        if embed.get('image') and embed['image'].get('url'):
            return embed['image']['url']
    return None

def handle_verification(msg_content_raw, msg=None):
    """Attempt to auto-solve the verification."""
    code = extract_verification_code(msg_content_raw)
    
    if not code:
        image_url = get_image_url_from_message(msg)
        if image_url:
            print(f"🖼️ Found image verification at: {image_url}")
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                try:
                    import google.generativeai as genai
                    from PIL import Image
                    import io
                    print("🤖 Using Google AI Studio to solve image captcha...")
                    genai.configure(api_key=api_key)
                    # User specifically requested gemma-4-26b-a4b-it
                    model = genai.GenerativeModel('gemma-4-26b-a4b-it')
                    
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        img = Image.open(io.BytesIO(response.content))
                        prompt = "Extract the verification code or text from this captcha image. Respond with ONLY the exact code/text, nothing else. No explanation, no markdown."
                        ocr_result = model.generate_content([prompt, img])
                        code = ocr_result.text.strip()
                        # Clean up any potential markdown added by the model
                        code = re.sub(r'[\*_`]', '', code)
                        print(f"🤖 AI Studio OCR Result: {code}")
                    else:
                        print("❌ Failed to download image for OCR.")
                except ImportError:
                    print("❌ google-generativeai or Pillow library is not installed.")
                except Exception as e:
                    print(f"❌ Error during AI Studio OCR: {e}")
            else:
                print("⚠️ GEMINI_API_KEY not found in .env. Setup Google AI Studio API for optional Auto-OCR. (It's 100% free!)")

    if code:
        print(f"🔧 Extracted captcha code: {code}")
        print("Sending /verify command...")
        success = send_verify_command(code)
        if success:
            print("Verify command sent successfully!")
            return True

    print("\n" + "="*50)
    print("🚨 ANTI-BOT VERIFICATION DETECTED BUT COULD NOT AUTO-SOLVE! 🚨")
    print("Stopping the auto-fisher immediately to keep your account safe.")
    print("Solve the captcha manually in Discord before running the script again.")
    print("="*50 + "\n")
    return False

def main():
    print("Starting user account auto-fisher with anti-verification handler...")
    print("Press Ctrl+C to stop.\n")

    my_info = get_my_user_info()
    my_id = my_info.get('id', '')
    my_username = my_info.get('username', '').lower()
    my_global_name = (my_info.get('global_name') or '').lower()
    if my_username:
        print(f"Logged in as: {my_username} ({my_id})")

    fishing_active = True
    handled_verifications = set()

    last_5m_time = 0
    COOLDOWN_5M = 305  # 5 minutes and 5 seconds

    last_10m_time = 0
    COOLDOWN_10M = 605  # 10 minutes and 5 seconds

    last_shop_time = 0
    COOLDOWN_SHOP = 1800  # 30 minutes

    while fishing_active:
        try:
            current_time = time.time()

            # Send the 10m commands
            if current_time - last_10m_time >= COOLDOWN_10M:
                print("\n[+] Sending 10-minute scheduled commands...")
                send_sell_command("all")
                time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                send_buy_command("Auto10m")
                time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                last_10m_time = time.time()

            # Send the 5m commands
            if current_time - last_5m_time >= COOLDOWN_5M:
                print("\n[+] Sending 5-minute scheduled commands...")
                send_buy_command("Fish5m")
                time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                send_buy_command("Treasure5m")
                time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                last_5m_time = time.time()

            # 1. Read recent messages to check for bot stop keywords
            messages = get_latest_messages(limit=15)

            for msg in messages:
                author = msg.get('author', {})
                if author.get('bot', False) or author.get('username') == 'Virtual Fisher':
                    content = msg.get('content', '').lower()

                    # Ensure the bot message is directed at us
                    is_for_me = False
                    if my_id and msg.get('interaction', {}).get('user', {}).get('id') == my_id:
                        is_for_me = True
                    elif my_id and any(u.get('id') == my_id for u in msg.get('mentions', [])):
                        is_for_me = True
                    elif my_username and my_username in content:
                        is_for_me = True
                    elif my_global_name and my_global_name in content:
                        is_for_me = True

                    if not is_for_me:
                        continue # Skip messages for other users

                    # Reconstruct raw content for case-sensitive captcha solving
                    msg_content_raw = msg.get('content', '')

                    # Parse message embeds and their internal fields
                    for embed in msg.get('embeds', []):
                        if embed.get('title'):
                            content += ' ' + embed['title'].lower()
                            msg_content_raw += '\n' + embed['title']
                        if embed.get('description'):
                            content += ' ' + embed['description'].lower()
                            msg_content_raw += '\n' + embed['description']
                        for field in embed.get('fields', []):
                            if field.get('name'):
                                content += ' ' + field['name'].lower()
                                msg_content_raw += '\n' + field['name']
                            if field.get('value'):
                                content += ' ' + field['value'].lower()
                                msg_content_raw += '\n' + field['value']

                    msg_id = msg.get('id')
                    if msg_id in handled_verifications:
                        continue
                    handled_verifications.add(msg_id)

                    # --- Profile/Shop State Parsing ---
                    lower_content = msg_content_raw.lower()
                    if "inventory of" in lower_content or "balance:" in lower_content:
                        game_state.parse_profile(msg_content_raw)
                    if "shop" in lower_content:
                        if "rod" in lower_content:
                            game_state.parse_shop(msg_content_raw, "rods")
                        elif "boat" in lower_content or "sailboat" in lower_content:
                            game_state.parse_shop(msg_content_raw, "boats")
                        elif "upgrade" in lower_content:
                            game_state.parse_shop(msg_content_raw, "upgrades")
                        elif "bait shop" in lower_content or "bait:" in lower_content:
                            game_state.parse_shop(msg_content_raw, "bait")

                    # --- Anti-bot / Verification check ---
                    if any(keyword in content for keyword in KEYWORDS):
                        print("\n" + "="*50)
                        print(f"🛑 Detected anti-bot keyword in message from bot '{author.get('username')}'!")
                        print(f"Message content: {msg.get('content')}")
                        if msg.get('embeds'):
                            print(f"Embeds: {msg.get('embeds')}")
                        print("="*50 + "\n")

                        success = handle_verification(msg_content_raw, msg)
                        if success:
                            print("[*] Verification auto-solved. Resuming fishing in 5 seconds...")
                            time.sleep(5)
                            break
                        else:
                            print("[!] Verification handling failed. Stopping to avoid ban.")
                            fishing_active = False
                            break

            if not fishing_active:
                break

            # --- Auto-Shop and Purchases ---
            best_purchase = game_state.get_best_purchase()
            while best_purchase:
                print(f"[!] Can afford {best_purchase['name']} for ${best_purchase['price']:,}! Buying...")
                send_buy_command(best_purchase['name'])
                time.sleep(WAIT_TIME)
                game_state.unowned_items.remove(best_purchase)
                game_state.balance -= best_purchase['price']
                best_purchase = game_state.get_best_purchase()

            # Bait maintenance logic (Make sure we parsed the bait shop first, thus available_baits has items)
            if game_state.available_baits and game_state.bait_name:
                # We try to stock up the current best bait we are using, or just the best available:
                best_bait = game_state.available_baits[-1]
                if game_state.bait_amount < 10 and game_state.balance >= best_bait['price'] * 50:
                    print(f"[!] Low on bait ({game_state.bait_amount}). Buying 50x {best_bait['name']}...")
                    send_buy_command(f"{best_bait['name']} 50")
                    time.sleep(WAIT_TIME)
                    game_state.bait_amount += 50
                    game_state.balance -= (best_bait['price'] * 50)

            # Sync shop state periodically
            if current_time - last_shop_time >= COOLDOWN_SHOP:
                print("\n[+] Syncing Profile and Shop information...")
                game_state.reset_shop_state()
                send_profile_command()
                time.sleep(WAIT_TIME)
                send_shop_command("rods")
                time.sleep(WAIT_TIME)
                send_shop_command("boats")
                time.sleep(WAIT_TIME)
                send_shop_command("upgrades")
                time.sleep(WAIT_TIME)
                send_shop_command("bait")
                time.sleep(WAIT_TIME)
                last_shop_time = time.time()
                # DO NOT skip /fish this cycle so we do not pause fishing

            # 2. Send the /fish command using interactions API
            send_slash_command()

            # 3. Wait exactly WAIT_TIME seconds + random 0 to 0.3s
            actual_wait = WAIT_TIME + random.uniform(0, 0.3)
            print(f"Waiting {actual_wait:.2f} seconds...")
            time.sleep(actual_wait)

        except KeyboardInterrupt:
            print("\nStopped manually.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()