import requests
import cv2
import numpy as np
import time
import os
from datetime import datetime
import paho.mqtt.client as mqtt
from recognition_logic import FaceRecognitionLogic

# Define the gateway URL and endpoint
GATEWAY = "http://35.240.151.148"
ENTITY_TYPE = "Robot"
IMAGE_DIR = "./images"  # Directory to store downloaded images
BROKER = "35.240.151.148"  # MQTT Broker address
MQTT_TOPIC = "/1234/Robot001/log"  # MQTT topic to publish to

headers = {
    'NGSILD-Tenant': 'openiot',
    'fiware-servicepath': '/',
    'Link': '<https://raw.githubusercontent.com/dexter-lau-pmo/ngsi-ld/main/datamodels/context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
}

# Create the images directory if it doesn't exist
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Function to download the image from the given URL
def download_image(image_url, filename):
    response = requests.get(image_url)
    if response.status_code == 200:
        # Save the image to the specified filename
        with open(filename, 'wb') as f:
            f.write(response.content)
        # Convert the image data to a NumPy array
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        # Decode the image into an OpenCV format
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        print("Image downloaded")
        return image
    else:
        print(f"Failed to download image from {image_url}. Status code: {response.status_code}")
        return None

# Function to update the NGSI-LD entry with faces
def update_faces(robot_id, faces, observed_at):
    # Prepare the payload to update the temporal entry
    payload = {
        "faces": {
            "type": "Property",
            "value": faces,
            "observedAt": observed_at  # Use the appropriate timestamp here
        }
    }

    response = requests.patch(f"{GATEWAY}/api/broker/ngsi-ld/v1/entities/{robot_id}/attrs", headers=headers, json=payload)
    if response.status_code == 204:
        print("Faces updated successfully.")
    else:
        print(f"Failed to update faces. Status code: {response.status_code}, Response: {response.text}")

# Function to sanitize the robot ID for use in a filename
def sanitize_filename(filename):
    return filename.replace(':', '_').replace('/', '_').replace('\\', '_')

# Function to sanitize the timestamp for use in a filename
def sanitize_timestamp(timestamp):
    return timestamp.replace(':', '-').replace('.', '_').replace('T', '_').replace('Z', '')

# MQTT Client setup
mqtt_client = mqtt.Client()

# Function to connect to the MQTT broker
def connect_mqtt():
    mqtt_client.connect(BROKER)
    mqtt_client.loop_start()

# Function to publish the faces, image URL, and observedAt to MQTT
def publish_message(faces, image_url, observed_at):
    message = {
        "faces": faces,
        "image_url": image_url,
        "observedAt": observed_at
    }
    mqtt_client.publish(MQTT_TOPIC, payload=str(message), qos=1)
    print(f"Published message: {message} to topic: {MQTT_TOPIC}")

# Main function to poll the endpoint and process images
def poll_robots():
    connect_mqtt()  # Connect to the MQTT broker
    recogniser = FaceRecognitionLogic()
    last_observed = {}

    while True:
        try:
            print("Polling...")
            # Poll the entities
            response = requests.get(f"{GATEWAY}/api/broker/ngsi-ld/v1/entities?type={ENTITY_TYPE}", headers=headers)
            if response.status_code == 200:
                robots = response.json()
                print("Response: ", robots)

                for robot in robots:
                    robot_id = robot['id']  # Extract the robot ID
                    sanitized_robot_id = sanitize_filename(robot_id)  # Sanitize the robot ID
                    image_url = robot.get("imagepath", {}).get("value")
                    observed_at = robot.get("timestamp", {}).get("observedAt")  # Extract the observedAt timestamp

                    if image_url and observed_at:
                        if robot_id not in last_observed or last_observed[robot_id] != observed_at:
                            # Sanitize the timestamp for the filename
                            sanitized_observed_at = sanitize_timestamp(observed_at)
                            image_filename = os.path.join(IMAGE_DIR, f"{sanitized_robot_id}_{sanitized_observed_at}.jpg")

                            # Download the image
                            image = download_image(image_url, image_filename)
                            if image is not None:
                                # Convert the image to grayscale
                                gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                                # Call your face_rec function with the grayscale image
                                try:
                                    faces = recogniser.face_rec(gray_image)  # Make sure to import your face_rec function at the top
                                except Exception as e:
                                    print(f"Face recognition failed: {e}")
                                    faces = []

                                # Update the NGSI-LD entry with detected faces
                                update_faces(robot_id, faces, observed_at)  # Pass the timestamp
                                publish_message(faces, image_url, observed_at)  # Publish to MQTT
                                last_observed[robot_id] = observed_at
                        else:
                            print("Image processed before")
            else:
                print(f"Failed to fetch entities. Status code: {response.status_code}")

        except Exception as e:
            print(f"An error occurred: {e}")

        # Sleep for a while before polling again
        time.sleep(4)  # Adjust the polling interval as needed

if __name__ == "__main__":
    poll_robots()
