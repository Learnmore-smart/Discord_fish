# Discord Virtual Fisher Auto-Bot

An automated Python script for sending `/fish` commands in Discord to play Virtual Fisher, with an anti-bot verification handler.

## Features
- Automatically sends the `/fish` slash command based on your configured cooldown.
- Automatically solves typical logic captchas/anti-bot checks that the bot throws.
- Skips already-handled verifications seamlessly.
- Stops cleanly if an unknown verification appears to protect your account.

## Setup Guide

### 1. Install Requirements
Make sure you have Python (3.7+) installed. Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### 2. Configuration
1. Copy the `.env.example` file and rename the copy to `.env`.
2. Open `.env` in a text editor and fill in your details:
   - `USER_TOKEN`: Your personal Discord account token (**DO NOT share this**).
   - `CHANNEL_ID`: The ID of the Discord channel where you want to fish.
   - `WAIT_TIME`: Time to wait between `/fish` commands in seconds. (Recommended `2.2` or higher).

**How to find your User Token:**
*(Note: Self-botting is against Discord TOS. Do this at your own risk.)*
1. Open Discord in your web browser and press `F12` to open Developer Tools.
2. Go to the **Network** tab.
3. Send a random message in any channel.
4. Click on the `messages` network request that appears.
5. Scroll down to **Request Headers** and find `Authorization`. Copy that value.

**How to find a Channel ID:**
1. Enable **Developer Mode** in Discord (User Settings > Advanced).
2. Right-click the channel name where you want to fish and click **Copy Channel ID**.

### 3. Run the Bot
Start the script from your terminal:
```bash
python user_auto_fisher.py
```

## Disclaimer
Automating user accounts (self-botting) is strictly against [Discord's Terms of Service](https://discord.com/terms) and might lead to your account being banned. Use at your own risk. The creator is not responsible for any banned accounts.