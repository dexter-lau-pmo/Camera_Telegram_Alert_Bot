# 📷 Telegram Alert Bot for Sensehub

This is a simple Telegram bot that interfaces with my [Sensehub Raspberry Pi project](https://github.com/systemssndgg/Sensehub).  
The bot sends an alert when a recognized person is detected via the NGSI-LD broker.

---

## ⚙️ Setup

### 1. Set Environment Variables and Run

In the file `ljp_camera_bot.py`, modify the following lines:

```python
# Set your NGSI-LD broker IP address
BROKER = "Your_broker_IP_address"

# Set your Telegram bot token
TELEGRAM_BOT_TOKEN = "Your_telegram_bot_token"

# Then, run the bot
python ljp_camera_bot.py
