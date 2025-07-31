import paho.mqtt.client as mqtt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import time
import requests
import asyncio
import os
import datetime
import logging
import json

#  Broker and topics
BROKER = "35.240.151.148"
TOPICS = ["/1234/Camera001/attrs", "/1234/Camera002/attrs" , "/1234/Robot001/log" , "/1234/Robot001/attrs"] #/1234/Robot001/attrs
TELEGRAM_BOT_TOKEN = "7775950726:AAGNbYtQ92sjyPRiYK78c7uo1B0_RityZEc"

# Track last alert times to enforce the 7-second rule
last_alert_times = {}

# Dictionary to store user-specific data
user_data = {}

# Global variable to store names for sending:
global_last_names = []
global_imagepath = None  # Store the image path globally
global_last_topic = ""

shirt_color = "Unknown"
robot_imagepath = None
robot_observedat = None
robot_faces = []


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
    print(f"Connected to broker with result code {rc}")
    for topic in TOPICS:
        client.subscribe(topic)


def on_message(client, userdata, msg):
    global global_last_names, global_imagepath, shirt_color  # Declare as global
    global robot_imagepath, robot_faces, robot_observedat, global_last_topic

    try:
        # Use json instead of eval for safe JSON parsing
        message = json.loads(msg.payload.decode())
    except json.JSONDecodeError as e:
        print(f"Failed to decode message: {e}")
        return  # Exit if the message is not valid JSON

    if msg.topic == TOPICS[0] or msg.topic == TOPICS[1]:
        names = message.get("names", "")
        global_imagepath = message.get("imagepath")  # Store the imagepath globally
        
        if "alerts" in global_imagepath:
            shirt_color = message.get("color")
            current_time = time.time()

            # If names is a string, convert to list
            if isinstance(names, str):
                names = [names]
            # Set global variable to trigger send_detection_alert from main function
            global_last_names = names
            print("Alert footage ")
            global_last_topic =  msg.topic # Store topic to ret camera name
            
            print("Imagepath: ", global_imagepath)
        else:
            print("Survelliance footage ")
            print("Imagepath: ", global_imagepath)
        
    elif msg.topic == TOPICS[2]:
        print("Logs topic")
        
    elif msg.topic == TOPICS[3]:
        if robot_imagepath is None:
            robot_imagepath = message.get("imagepath") 
            robot_observedat = message.get("timestamp")
            print("Robot image path received")
        else:
            print("Wait for next detection to update")
    else:
        print("Unregistered topic received")



async def trigger_send_robot_image():
    global robot_observedat, robot_imagepath, robot_faces
    
    for user_id in user_data.keys():  # Loop through user data
        detected_name = user_data[user_id].get('detected_name')
        await send_robot_image(user_data[user_id], robot_faces , robot_imagepath)  # Pass user context
        
    await asyncio.sleep(0.1)  # Sleep to avoid blocking the loop


async def send_robot_image(user_context,   name , imagepath):
    global robot_observedat
    # Download the image
    image_url = imagepath
    image_response = requests.get(image_url)

    # Generate a unique filename using the current timestamp
    current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"./snapshots/robot_{current_timestamp}.jpg"  # Using the robot and timestamp
    name = "Unknown" #Reset name
    
    if len(name)<2:
        name = "Unknown"
    
    # Save image locally
    if image_response.status_code == 200:
        with open(image_filename, "wb") as f:
            f.write(image_response.content)

        print(f"Image from Robot with {name} ! Image downloaded and saved as {image_filename}.")

        # Prepare the message to send
        detection_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Get current time
        #caption = f"Image from robot {name} detected at {robot_observedat}"
        caption = f"Image from robot detected at {robot_observedat}"

        # Send the image to the user
        chat_id = user_context['chat_id']  # Get the chat ID from user data
        bot = user_context['bot']  # Retrieve the bot instance from user data
        with open(image_filename, "rb") as photo:
            print("Opened image file for sending")
            try:
                await bot.send_photo(chat_id, photo, caption=caption)
            except Exception as e:
                # Log the error and continue
                logging.error(f"Failed to send alert to {chat_id}: {e}")
            await asyncio.sleep(0.1)
            #send_message_to_user(chat_id, f"Image from robot with: {name} ")
            send_message_to_user(chat_id, f"Image from robot triggered ")

    else:
        print(f"Failed to download image from {image_url}. Status code: {image_response.status_code}")




async def trigger_send_detection_alert_function(imagepath):
    global global_last_names , shirt_color  # Declare as global
    current_time = time.time()  # Move this inside the function
    for user_id in user_data.keys():  # Loop through user data
        detected_name = user_data[user_id].get('detected_name') 
        if detected_name and any(detected_name.lower() == name.lower() for name in global_last_names): #Looking for specific person
            if detected_name in last_alert_times and current_time - last_alert_times[detected_name] < 7:
                continue
            last_alert_times[detected_name] = current_time
            print("Await: ", imagepath)
            await send_detection_alert(user_data[user_id], detected_name, shirt_color, imagepath)  # Pass user context
        elif not detected_name: #Not looking for anyone in particular
            for name in global_last_names:
                if name in last_alert_times and current_time - last_alert_times[name] < 7:
                    continue
                last_alert_times[name] = current_time
                await send_detection_alert(user_data[user_id], name, shirt_color, imagepath)  # Pass user context
        await asyncio.sleep(0.1)  # Sleep to avoid blocking the loop


async def send_detection_alert(user_context, name, shirt_color, imagepath):
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
            try:
                await bot.send_photo(chat_id, photo, caption=caption)
            except Exception as e:
                # Log the error and continue
                logging.error(f"Failed to send alert to {chat_id}: {e}")

            camera_name = "Camera001"
            if "002" in global_last_topic:
                camera_name= "Camera002"
                
            send_message_to_user(chat_id, f"{name} was detected with shirt color {shirt_color} by {camera_name} located in Room001")
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
    global global_last_names, robot_observedat, robot_imagepath #robot_faces
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name))

    # Start the bot
    await application.initialize()  # Ensure the application is initialized
    await application.start()

    # Start the client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, 1883, 60)
    client.loop_start()

    # Start polling for updates
    await application.updater.start_polling()

    robot_image_counter = 0
    # Keep the bot running
    try:
        while True:
            await asyncio.sleep(1)  # Keep the loop running
            
            if len(global_last_names) > 0 and global_imagepath:  # Check if both names and imagepath are available
                print("Names received: ", global_last_names)
                print("Imagepath: ", global_imagepath)
                await trigger_send_detection_alert_function(global_imagepath)  # Pass the imagepath
                global_last_names = []
                robot_image_counter = 2
                robot_imagepath = None
            
            #Comment out robot image block
            '''
            if robot_imagepath is not None:
                if robot_image_counter > 0:
                    await trigger_send_robot_image() 
                    robot_image_counter = robot_image_counter - 1
                    robot_imagepath = None
            '''
                
 
    except KeyboardInterrupt:
        print("Stopping the bot...")
    finally:
        await application.stop()
        client.loop_stop()  # Stop the MQTT loop
        client.disconnect()  # Disconnect from the broker


if __name__ == '__main__':
    asyncio.run(run_bot())
