# Discord Virtual Fisher Auto-Bot

An automated Python script for sending `/fish` commands in Discord to play Virtual Fisher, with an anti-bot verification handler.

## Features
- Automatically sends the `/fish` slash command every 2.2 seconds (configurable).
- Automatically solves typical logic captchas/anti-bot checks that the bot throws.
- Stops cleanly if an unknown verification appears to protect your account.

## Setup

1. **Install Requirements:**
   Make sure you have Python installed, then run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration:**
   Create a `.env` file in the same directory (you can copy `.env.example` if available) and add your details:
   ```env
   USER_TOKEN=your_discord_user_token_here
   CHANNEL_ID=your_channel_id_here
   ```

3. **Run:**
   ```bash
   python user_auto_fisher.py
   ```

## Disclaimer
Automating user accounts (self-botting) is against Discord's Terms of Service and might lead to your account being banned. Use at your own risk.