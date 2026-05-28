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
CMD_PROFILE_ID = os.getenv('CMD_PROFILE_ID', '912432960643416118')
CMD_PROFILE_VER = os.getenv('CMD_PROFILE_VER', '1207457860523663382')

CMD_SHOP_ID = os.getenv('CMD_SHOP_ID', '912432960643416117')
CMD_SHOP_VER = os.getenv('CMD_SHOP_VER', '1290504714135277620')

# Generate a random 32-character hex session ID
SESSION_ID = "".join(random.choices("0123456789abcdef", k=32))
GUILD_ID = os.getenv('GUILD_ID', '1491654181201903646')

HEADERS = {
    'Authorization': f'{USER_TOKEN}',
    'Content-Type': 'application/json'
}

# ─── Emoji pattern shared across parsers ───
EMOJI_PATTERN = r'(?:<a?:[a-zA-Z0-9_]+:\d+>|:[a-zA-Z0-9_]+:)'

# ─── Upgrade priority (lower = higher priority, used as tiebreaker) ───
UPGRADE_PRIORITY = {
    "Better Fish": 1,
    "Salesman": 2,
    "More Chests": 3,
    "Bait Efficiency": 4,
    "Better Dailies": 5,
    "Artifact Specialist": 6,
    "Better Chests": 7,
    "Experienced": 8,
    "Worker Motivation": 9,
}

class GameState:
    def __init__(self):
        self.balance = 0
        self.level = 0
        self.fish_value = 0
        self.bait_amount = 0
        self.bait_name = ""
        self.unowned_items = []       # [{name, price, type, priority?, current_level?, max_level?}]
        self.bait_inventory = {}      # {name: {name, price, owned}}
        self.shop_pages = {}          # {category: total_pages}
        self.next_bait_unlock_level = 0
        self.exotic_inventory = {}    # {name: owned_count}

    def reset_shop_state(self):
        self.unowned_items = []
        self.bait_inventory = {}
        self.shop_pages = {}
        self.next_bait_unlock_level = 0
        self.exotic_inventory = {}

    def parse_profile(self, text):
        # Clean markdown formatting (asterisks and backslashes) to match robustly
        text = text.replace('*', '').replace('\\', '')
        
        bal_match = re.search(r'Balance:\s*\$([\d,]+)', text)
        if bal_match:
            self.balance = int(bal_match.group(1).replace(',', ''))

        lvl_match = re.search(r'Level\s+(\d+)', text)
        if lvl_match:
            self.level = int(lvl_match.group(1))

        fish_val_match = re.search(r'Fish Value:\s*\$([\d,]+)', text)
        if fish_val_match:
            self.fish_value = int(fish_val_match.group(1).replace(',', ''))

        bait_match = re.search(r'Bait:(.*?)(?:\n|$)', text)
        if bait_match:
            bait_line = bait_match.group(1)
            b = re.search(EMOJI_PATTERN + r'\s*(.*?)\s*\((\d+)\)', bait_line)
            if b:
                clean_name = re.sub(r'[\*`]', '', b.group(1)).strip()
                self.bait_name = clean_name
                self.bait_amount = int(b.group(2))

        # Exotic Fish section
        exotic_sec = re.search(r'Exotic Fish(.*?)(?:Special|$)', text, re.DOTALL | re.IGNORECASE)
        if exotic_sec:
            # Lines look like: 1,284 :gold_fish: Gold Fish
            matches = re.findall(r'([\d,]+)\s+' + EMOJI_PATTERN + r'\s*(.*?)(?:\n|$)', exotic_sec.group(1))
            for count, name in matches:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                self.exotic_inventory[clean_name] = int(count.replace(',', ''))

    def parse_shop(self, text, category=""):
        # Clean markdown formatting (asterisks and backslashes) to match robustly
        text = text.replace('*', '').replace('\\', '')
        
        # Extract balance from shop header
        if "Your balance:" in text:
            bal_match = re.search(r'Your balance:\s*\$([\d,]+)', text)
            if bal_match:
                self.balance = int(bal_match.group(1).replace(',', ''))

        # Detect page numbers: "Page X/Y"
        page_match = re.search(r'Page\s+(\d+)/(\d+)', text)
        if page_match:
            total_pages = int(page_match.group(2))
            if category not in self.shop_pages or total_pages > self.shop_pages[category]:
                self.shop_pages[category] = total_pages

        if category == "bait":
            # Format: :bait_type: Name - $PRICE. You own: COUNT
            bait_pattern = EMOJI_PATTERN + r'\s*(.+?)\s*-\s*\$([\d,]+)\.\s*You own:\s*(\d+)'
            baits = re.findall(bait_pattern, text)
            for name, price, owned in baits:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                self.bait_inventory[clean_name] = {
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'owned': int(owned)
                }

            # Detect next bait unlock: "UNLOCKED AT LEVEL XXX!"
            unlock_match = re.search(r'UNLOCKED AT LEVEL\s+(\d+)', text)
            if unlock_match:
                self.next_bait_unlock_level = int(unlock_match.group(1))

        elif category == "upgrades":
            # Format: CURRENT/MAX Name - $PRICE   or   CURRENT/MAX Name - MAX
            # Only capture non-MAX upgrades with a $ price
            upgrade_pattern = r'(\d+)/(\d+)\s+(.+?)\s*-\s*\$([\d,]+)'
            upgrades = re.findall(upgrade_pattern, text)
            for current, maximum, name, price in upgrades:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                priority = UPGRADE_PRIORITY.get(clean_name, 50)
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'type': 'upgrades',
                    'priority': priority,
                    'current_level': int(current),
                    'max_level': int(maximum),
                })

        elif category == "special":
            # Format: PRICE :emoji: - CURRENT/MAX Name
            # e.g. 120 :lava_fish: - 6/20 Fish Ovens
            # Regex: ([\d,]+) (emoji) - (\d+)/(\d+) (Name)
            special_pattern = r'([\d,]+)\s+(' + EMOJI_PATTERN + r')\s*-\s*(\d+)/(\d+)\s+(.+?)(?:\n|$)'
            upgrades = re.findall(special_pattern, text)
            for price, emoji_part, current, maximum, name in upgrades:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                # Parse currency type from emoji
                emoji_match = re.search(r':([a-zA-Z0-9_]+):', emoji_part)
                currency = "Gold Fish" # fallback
                if emoji_match:
                    currency = emoji_match.group(1).replace('_', ' ').title()
                
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'currency': currency, # e.g. "Lava Fish", "Diamond Fish"
                    'type': 'special',
                    'priority': 40,
                    'current_level': int(current),
                    'max_level': int(maximum),
                })

            # Parse inventory from header line specifically
            inv_line_match = re.search(r'Inventory:\s*(.*?)(?:\n|$)', text, re.IGNORECASE)
            if inv_line_match:
                inv_matches = re.findall(r'([\d,]+)\s+(' + EMOJI_PATTERN + r')', inv_line_match.group(1))
                for count, emoji_part in inv_matches:
                    emoji_match = re.search(r':([a-zA-Z0-9_]+):', emoji_part)
                    if emoji_match:
                        currency = emoji_match.group(1).replace('_', ' ').title()
                        self.exotic_inventory[currency] = int(count.replace(',', ''))

        else:
            # Rods and Boats — only match items with a $ price (skips OWNED automatically)
            item_pattern = EMOJI_PATTERN + r'\s*(.+?)\s*-\s*\$([\d,]+)'
            items = re.findall(item_pattern, text)
            for name, price in items:
                clean_name = re.sub(r'[\*`]', '', name).strip()
                # Skip balance lines that match the pattern
                if clean_name.lower().startswith('your balance'):
                    continue
                self.unowned_items.append({
                    'name': clean_name,
                    'price': int(price.replace(',', '')),
                    'type': category,
                    'priority': 0,
                })

    def get_best_bait(self):
        """Returns the most expensive (best) available bait from the bait inventory."""
        if not self.bait_inventory:
            return None
        return max(self.bait_inventory.values(), key=lambda b: b['price'])

    def get_purchase_plan(self):
        """Returns an ordered list of purchases: bait maintenance first, then cheapest items."""
        plan = []

        # Priority 1: Bait maintenance
        best_bait = self.get_best_bait()
        if best_bait:
            # Use the bait currently equipped if it exists in inventory, otherwise use best
            current_bait = self.bait_inventory.get(self.bait_name)
            target_bait = current_bait if current_bait else best_bait

            # Always prefer the BEST bait (most expensive) even if currently using a cheaper one
            if best_bait['price'] > target_bait['price']:
                target_bait = best_bait

            # Determine current stock of the target bait
            # Profile bait_amount is the authoritative source for equipped bait
            if target_bait['name'] == self.bait_name and self.bait_amount > 0:
                bait_stock = self.bait_amount
            elif target_bait['name'] in self.bait_inventory:
                bait_stock = self.bait_inventory[target_bait['name']]['owned']
            else:
                bait_stock = 0

            if bait_stock < 100:
                buy_amount = 100
                total_cost = target_bait['price'] * buy_amount
                if self.balance >= total_cost:
                    plan.append({
                        'name': f"{target_bait['name']} {buy_amount}",
                        'display_name': f"100x {target_bait['name']}",
                        'price': total_cost,
                        'type': 'bait',
                        'priority': -1,  # highest priority
                    })

        # Priority 2: Special Shop upgrades (bought with exotic fish)
        special_items = [item for item in self.unowned_items if item['type'] == 'special']
        special_items.sort(key=lambda x: x['price'])
        
        remaining_exotics = self.exotic_inventory.copy()
        for item in special_items:
            currency = item.get('currency', 'Diamond Fish')
            cost = item['price']
            if remaining_exotics.get(currency, 0) >= cost:
                plan.append(item)
                remaining_exotics[currency] -= cost

        # Priority 3: Cheapest available items across all categories (cash upgrades, boats, rods)
        cash_items = [item for item in self.unowned_items if item['type'] != 'special']
        affordable = [item for item in cash_items if self.balance >= item['price']]
        affordable.sort(key=lambda x: (x['price'], x.get('priority', 50)))

        remaining_balance = self.balance
        # Subtract bait cost if bait is in the plan
        for p in plan:
            if p['type'] == 'bait':
                remaining_balance -= p['price']

        for item in affordable:
            if remaining_balance >= item['price']:
                plan.append(item)
                remaining_balance -= item['price']

        return plan

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

def send_shop_command(category, page=None):
    options = [{"type": 3, "name": "category", "value": category}]
    if page is not None and page > 1:
        options.append({"type": 4, "name": "page", "value": str(page)})
    return dispatch_slash_command("shop", CMD_SHOP_ID, CMD_SHOP_VER, options)

def extract_bot_response(my_id, wait_time=None):
    """Wait for bot response, then fetch and return the raw text of the most recent bot message directed at us."""
    if wait_time is None:
        wait_time = WAIT_TIME + 1.5
    time.sleep(wait_time)
    messages = get_latest_messages(limit=5)
    for msg in messages:
        author = msg.get('author', {})
        if not (author.get('bot', False) or author.get('username') == 'Virtual Fisher'):
            continue
        # Check if message is for us
        if my_id and msg.get('interaction', {}).get('user', {}).get('id') == my_id:
            pass  # It's for us
        elif my_id and any(u.get('id') == my_id for u in msg.get('mentions', [])):
            pass  # It's for us
        else:
            continue
        # Build raw text from content + embeds
        raw = msg.get('content', '')
        for embed in msg.get('embeds', []):
            if embed.get('title'):
                raw += '\n' + embed['title']
            if embed.get('description'):
                raw += '\n' + embed['description']
            for field in embed.get('fields', []):
                if field.get('name'):
                    raw += '\n' + field['name']
                if field.get('value'):
                    raw += '\n' + field['value']
        return raw
    return ""

def fetch_and_parse_shop(category, my_id):
    """Fetch all pages of a shop category and parse them into game_state."""
    # Page 1
    send_shop_command(category)
    response_text = extract_bot_response(my_id)
    if response_text:
        game_state.parse_shop(response_text, category)

    # Check for additional pages
    total_pages = game_state.shop_pages.get(category, 1)
    for page_num in range(2, total_pages + 1):
        send_shop_command(category, page=page_num)
        response_text = extract_bot_response(my_id)
        if response_text:
            game_state.parse_shop(response_text, category)


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

    last_buy_time = 0
    COOLDOWN_BUY = 305  # 5 minutes and 5 seconds

    last_shop_time = 0
    COOLDOWN_SHOP = 305  # 5 minutes and 5 seconds

    while fishing_active:
        try:
            current_time = time.time()

            # Send scheduled buy commands every 5 minutes
            if current_time - last_buy_time >= COOLDOWN_BUY:
                print("\n[+] Sending 5-minute scheduled buy commands...")
                # Sell all fish first to get money
                send_sell_command("all")
                time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                # Buy actual Virtual Fisher boosters by their real names (Exotic Fish boosts)
                boosters = ["Auto10m", "Fish5m", "Treasure5m"]
                for booster in boosters:
                    send_buy_command(booster)
                    time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                # Quick bait check: if we know bait is low, buy 100 more
                best_bait = game_state.get_best_bait()
                if best_bait and game_state.bait_amount < 100:
                    total_cost = best_bait['price'] * 100
                    if game_state.balance >= total_cost:
                        print(f"[!] Low bait ({game_state.bait_amount}). Buying 100x {best_bait['name']}...")
                        send_buy_command(f"{best_bait['name']} 100")
                        time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                        game_state.bait_amount += 100
                        game_state.balance -= total_cost
                last_buy_time = time.time()

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

                    # --- Anti-bot / Verification check ---
                    has_verification = any(keyword in content for keyword in KEYWORDS)
                    if has_verification:
                        if msg_id in handled_verifications:
                            continue
                        handled_verifications.add(msg_id)

                    # --- Profile/Shop State Parsing (always parse, not gated by handled set) ---
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
                        elif "special" in lower_content:
                            game_state.parse_shop(msg_content_raw, "special")
                        elif "bait shop" in lower_content or "bait:" in lower_content:
                            game_state.parse_shop(msg_content_raw, "bait")

                    # --- Handle verification if detected ---
                    if has_verification:
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

            # --- Smart Auto-Purchasing (runs after shop sync populates data) ---
            purchase_plan = game_state.get_purchase_plan()
            if purchase_plan:
                print(f"\n[!] Purchase Plan ({len(purchase_plan)} items):")
                for i, item in enumerate(purchase_plan, 1):
                    display = item.get('display_name', item['name'])
                    level_info = ""
                    if 'current_level' in item:
                        level_info = f" ({item['current_level']}->{item['current_level']+1}/{item['max_level']})"
                    
                    if item['type'] == 'special':
                        currency = item.get('currency', 'Lava Fish')
                        print(f"    {i}. {display}{level_info} - {item['price']} {currency} ({item['type']})")
                    else:
                        print(f"    {i}. {display}{level_info} - ${item['price']:,} ({item['type']})")

                for item in purchase_plan:
                    display = item.get('display_name', item['name'])
                    cost_str = ""
                    if item['type'] == 'special':
                        currency = item.get('currency', 'Lava Fish')
                        cost_str = f"{item['price']} {currency}"
                    else:
                        cost_str = f"${item['price']:,}"
                        
                    print(f"[+] Buying {display} for {cost_str}...")
                    send_buy_command(item['name'])
                    time.sleep(WAIT_TIME + random.uniform(0, 0.3))
                    
                    # Update local state
                    if item['type'] == 'special':
                        currency = item.get('currency', 'Lava Fish')
                        if currency in game_state.exotic_inventory:
                            game_state.exotic_inventory[currency] -= item['price']
                        if item in game_state.unowned_items:
                            game_state.unowned_items.remove(item)
                    elif item['type'] == 'bait':
                        game_state.bait_amount += 100
                    else:
                        game_state.balance -= item['price']
                        if item in game_state.unowned_items:
                            game_state.unowned_items.remove(item)
                print(f"    Remaining balance: ${game_state.balance:,}")

            # Sync shop state periodically (every 5 minutes)
            if current_time - last_shop_time >= COOLDOWN_SHOP:
                print("\n[+] Syncing Profile and Shop information...")
                game_state.reset_shop_state()

                # Fetch profile first
                send_profile_command()
                profile_text = extract_bot_response(my_id)
                if profile_text:
                    game_state.parse_profile(profile_text)

                # Fetch all shop categories (with multi-page support)
                for shop_cat in ["rods", "boats", "upgrades", "bait", "special"]:
                    fetch_and_parse_shop(shop_cat, my_id)

                # Print detailed status
                print(f"\n    === Shop Sync Complete ===")
                print(f"    Balance: ${game_state.balance:,} | Level: {game_state.level}")
                print(f"    Bait: {game_state.bait_name} ({game_state.bait_amount}) | Best: {game_state.get_best_bait()['name'] if game_state.get_best_bait() else 'N/A'}")
                if game_state.next_bait_unlock_level:
                    print(f"    Next bait unlocks at Level {game_state.next_bait_unlock_level}")
                
                rod_count = len([i for i in game_state.unowned_items if i['type'] == 'rods'])
                boat_count = len([i for i in game_state.unowned_items if i['type'] == 'boats'])
                upgrade_count = len([i for i in game_state.unowned_items if i['type'] == 'upgrades'])
                special_count = len([i for i in game_state.unowned_items if i['type'] == 'special'])
                print(f"    Available: {rod_count} rods, {boat_count} boats, {upgrade_count} upgrades, {special_count} special upgrades")
                
                # Print exotic fish count
                exotic_str = " | ".join([f"{name}: {count:,}" for name, count in game_state.exotic_inventory.items()])
                if exotic_str:
                    print(f"    Exotic Fish: {exotic_str}")
                    
                for item in sorted(game_state.unowned_items, key=lambda x: x['price']):
                    level_info = ""
                    if 'current_level' in item:
                        level_info = f" ({item['current_level']}/{item['max_level']})"
                    
                    if item['type'] == 'special':
                        currency = item.get('currency', 'Lava Fish')
                        owned_count = game_state.exotic_inventory.get(currency, 0)
                        affordable = "BUY" if owned_count >= item['price'] else "---"
                        print(f"      [{affordable}] {item['name']}{level_info} - {item['price']} {currency} ({item['type']})")
                    else:
                        affordable = "BUY" if game_state.balance >= item['price'] else "---"
                        print(f"      [{affordable}] {item['name']}{level_info} - ${item['price']:,} ({item['type']})")

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