import paho.mqtt.client as mqtt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import time
import requests
import asyncio  # Import asyncio here
import os
import datetime  # Import datetime to generate a timestamp for the filename


# MQTT Broker and topics
BROKER = "35.240.151.148"
TOPICS = ["/1234/Camera001/attrs", "/1234/Camera002/attrs"]
TELEGRAM_BOT_TOKEN = "7775950726:AAGNbYtQ92sjyPRiYK78c7uo1B0_RityZEc"

# Track last alert times to enforce the 7-second rule
last_alert_times = {}

# Track the name to detect
detected_name = None

# Telegram bot handlers
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="yes"),
         InlineKeyboardButton("No", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Is there someone specific we are looking for?", reply_markup=reply_markup)

async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "yes":
        await query.edit_message_text(text="Please send me the name you are interested in.")
        context.user_data['expecting_name'] = True
    else:
        global detected_name
        detected_name = None
        await query.edit_message_text(text="Detection started; alerts will be sent if anyone is detected")

async def receive_name(update: Update, context):
    if 'expecting_name' in context.user_data and context.user_data['expecting_name']:
        global detected_name
        detected_name = update.message.text.lower()
        await update.message.reply_text(f"Detection started; Waiting for {detected_name}")
        context.user_data['expecting_name'] = False

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    for topic in TOPICS:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    message = eval(msg.payload.decode())
    names = message.get("names", "")
    timestamp = message.get("timestamp")
    imagepath = message.get("imagepath")
    confidence = message.get("confidence")
    color = message.get("color")
    #filename = message.get("filename")

    # Handle detection logic
    current_time = time.time()

    # If names is a string, convert to list
    if isinstance(names, str):
        names = [names]

    # Ensure detected_name is set and within the time limit
    if detected_name and any(detected_name.lower() == name.lower() for name in names):
        # Prevent multiple alerts within 7 seconds
        if detected_name in last_alert_times and current_time - last_alert_times[detected_name] < 7:
            return
        last_alert_times[detected_name] = current_time
        send_detection_alert(detected_name, imagepath)
    elif not detected_name:
        for name in names:
            if name in last_alert_times and current_time - last_alert_times[name] < 7:
                continue
            last_alert_times[name] = current_time
            send_detection_alert(name, imagepath)


def send_detection_alert(name, imagepath):
    # Download the image
    image_url = imagepath
    image_response = requests.get(image_url)
    
    # Generate a unique filename using the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"./snapshots/{name}_{timestamp}.jpg"  # Using the detected name and timestamp

    # Save image locally
    if image_response.status_code == 200:
        with open(image_filename, "wb") as f:
            f.write(image_response.content)
        print(f"{name} detected! Image downloaded and saved as {image_filename}.")


async def run_bot():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name))

    # Start the bot
    await application.initialize()  # Ensure the application is initialized
    await application.start()

    # Start the MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, 1883, 60)
    client.loop_start()

    # Start polling for updates
    await application.updater.start_polling()

    # Keep the bot running
    try:
        while True:
            await asyncio.sleep(1)  # Keep the loop running
    except KeyboardInterrupt:
        print("Stopping the bot...")
    finally:
        await application.stop()
        client.loop_stop()  # Stop the MQTT loop
        client.disconnect()  # Disconnect from the broker

if __name__ == '__main__':
    asyncio.run(run_bot())
