import paho.mqtt.client as mqtt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import time
import requests
import asyncio
import os
import datetime

# MQTT Broker and topics
BROKER = "35.240.151.148"
TOPICS = ["/1234/Camera001/attrs", "/1234/Camera002/attrs"]
TELEGRAM_BOT_TOKEN = "7775950726:AAGNbYtQ92sjyPRiYK78c7uo1B0_RityZEc"

# Track last alert times to enforce the 7-second rule
last_alert_times = {}

# Dictionary to store user-specific data
user_data = {}

# Global variable to store names for sending:
global_last_names = []
global_imagepath = None  # Store the image path globally

# Telegram bot handlers
async def start(update: Update, context):
    user_id = update.message.chat.id
    user_data[user_id] = {
        'chat_id': user_id,
        'expecting_name': False,  # Is a name assigned?
        'detected_name': None,  # What name are we expecting?
        'bot': context.bot  # Store the bot instance in user data
    }  # Initialize user data

    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="yes"),
         InlineKeyboardButton("No", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Is there someone specific we are looking for?", reply_markup=reply_markup)


async def button(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "yes":
        await query.edit_message_text(text="Please send me the name you are interested in.")
        user_data[user_id]['expecting_name'] = True
    else:
        user_data[user_id]['detected_name'] = None
        await query.edit_message_text(text="Detection started; alerts will be sent if anyone is detected")


async def receive_name(update: Update, context):
    user_id = update.message.chat.id
    if user_data[user_id]['expecting_name']:
        user_data[user_id]['detected_name'] = update.message.text.lower()
        await update.message.reply_text(f"Detection started; Waiting for {user_data[user_id]['detected_name']}")
        user_data[user_id]['expecting_name'] = False


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    for topic in TOPICS:
        client.subscribe(topic)


def on_message(client, userdata, msg):
    global global_last_names, global_imagepath  # Declare as global
    message = eval(msg.payload.decode())
    names = message.get("names", "")
    global_imagepath = message.get("imagepath")  # Store the imagepath globally

    current_time = time.time()

    # If names is a string, convert to list
    if isinstance(names, str):
        names = [names]

    # Set global variable to trigger send_detection_alert from main fn
    global_last_names = names
    print("Message received: ", message)  # Moved this line down after processing the message


async def trigger_send_detection_alert_function(imagepath):
    global global_last_names  # Declare as global
    current_time = time.time()  # Move this inside the function
    for user_id in user_data.keys():  # Loop through user data
        detected_name = user_data[user_id].get('detected_name')
        if detected_name and any(detected_name.lower() == name.lower() for name in global_last_names):
            if detected_name in last_alert_times and current_time - last_alert_times[detected_name] < 7:
                continue
            last_alert_times[detected_name] = current_time
            await send_detection_alert(user_data[user_id], detected_name, imagepath)  # Pass user context
        elif not detected_name:
            for name in global_last_names:
                if name in last_alert_times and current_time - last_alert_times[name] < 7:
                    continue
                last_alert_times[name] = current_time
                await send_detection_alert(user_data[user_id], name, imagepath)  # Pass user context
        await asyncio.sleep(0.1)  # Sleep to avoid blocking the loop


async def send_detection_alert(user_context, name, imagepath):
    # Download the image
    image_url = imagepath
    image_response = requests.get(image_url)

    # Generate a unique filename using the current timestamp
    current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"./snapshots/{name}_{current_timestamp}.jpg"  # Using the detected name and timestamp

    # Save image locally
    if image_response.status_code == 200:
        with open(image_filename, "wb") as f:
            f.write(image_response.content)

        print(f"{name} detected! Image downloaded and saved as {image_filename}.")

        # Prepare the message to send
        detection_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Get current time
        caption = f"{name} detected at {detection_time}"

        # Send the image to the user
        chat_id = user_context['chat_id']  # Get the chat ID from user data
        bot = user_context['bot']  # Retrieve the bot instance from user data
        with open(image_filename, "rb") as photo:
            print("Opened image file for sending")
            await bot.send_photo(chat_id, photo, caption=caption)
            send_message_to_user(chat_id, f"{name} was detected")
    else:
        print(f"Failed to download image from {image_url}. Status code: {image_response.status_code}")


def send_message_to_user(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    requests.post(url, json=payload)


async def run_bot():
    global global_last_names
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
            
            if len(global_last_names) > 0 and global_imagepath:  # Check if both names and imagepath are available
                print("Names received: ", global_last_names)
                await trigger_send_detection_alert_function(global_imagepath)  # Pass the imagepath
                global_last_names = []
 
    except KeyboardInterrupt:
        print("Stopping the bot...")
    finally:
        await application.stop()
        client.loop_stop()  # Stop the MQTT loop
        client.disconnect()  # Disconnect from the broker


if __name__ == '__main__':
    asyncio.run(run_bot())
