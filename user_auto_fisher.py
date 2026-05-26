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

# Generate a random 32-character hex session ID
SESSION_ID = "".join(random.choices("0123456789abcdef", k=32))

HEADERS = {
    'Authorization': f'{USER_TOKEN}',
    'Content-Type': 'application/json'
}

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

def send_slash_command():
    """Send the /fish slash command using the interactions API."""
    url = 'https://discord.com/api/v9/interactions'
    payload = {
        "type": 2,
        "application_id": "574652751745777665",
        "guild_id": "1491654181201903646",
        "channel_id": CHANNEL_ID,
        "session_id": SESSION_ID,
        "nonce": generate_nonce(),
        "data": {
            "version": "1207457860208824332",
            "id": "912432960643416115",
            "name": "fish",
            "type": 1,
            "options": [],
            "application_command": {
                "id": "912432960643416115",
                "type": 1,
                "application_id": "574652751745777665",
                "version": "1207457860208824332",
                "name": "fish"
            },
            "attachments": []
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 204]:
        print("Sent Slash Command: /fish")
        return True
    else:
        print(f"Failed to send slash command: {response.status_code} - {response.text}")
        return False

def send_verify_command(code):
    """Send the /verify slash command using the interactions API."""
    url = 'https://discord.com/api/v9/interactions'
    payload = {
        "type": 2,
        "application_id": "574652751745777665",
        "guild_id": "1491654181201903646",
        "channel_id": CHANNEL_ID,
        "session_id": SESSION_ID,
        "nonce": generate_nonce(),
        "data": {
            "version": "1207457860523663380",
            "id": "912432961222238220",
            "name": "verify",
            "type": 1,
            "options": [
                {"type": 3, "name": "answer", "value": code}
            ],
            "application_command": {
                "id": "912432961222238220",
                "type": 1,
                "application_id": "574652751745777665",
                "version": "1207457860523663380",
                "name": "verify"
            },
            "attachments": []
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 204]:
        print(f"Sent Slash Command: /verify {code}")
        return True
    else:
        print(f"Failed to send verify slash command: {response.status_code} - {response.text}")
        return False

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

def handle_verification(msg_content_raw):
    """Attempt to auto-solve the verification."""
    code = extract_verification_code(msg_content_raw)
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

    while fishing_active:
        try:
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

                    if any(keyword in content for keyword in KEYWORDS):
                        msg_id = msg.get('id')
                        if msg_id in handled_verifications:
                            continue

                        handled_verifications.add(msg_id)

                        print("\n" + "="*50)
                        print(f"🛑 Detected anti-bot keyword in message from bot '{author.get('username')}'!")
                        print(f"Message content: {msg.get('content')}")
                        if msg.get('embeds'):
                            print(f"Embeds: {msg.get('embeds')}")
                        print("="*50 + "\n")

                        success = handle_verification(msg_content_raw)
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

            # 2. Send the /fish command using interactions API
            send_slash_command()

            # 3. Wait exactly WAIT_TIME seconds - change based on your time
            print(f"Waiting {WAIT_TIME:.1f} seconds...")
            time.sleep(WAIT_TIME)

        except KeyboardInterrupt:
            print("\nStopped manually.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()