import requests
import cv2
import numpy as np
import time
import os
from datetime import datetime
from recognition_logic import FaceRecognitionLogic

# Define the gateway URL and endpoint
GATEWAY = "http://35.240.151.148"
ENTITY_TYPE = "Robot"
IMAGE_DIR = "./images"  # Directory to store downloaded images
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
    
    response = requests.patch(f"{GATEWAY}/api/broker/ngsi-ld/v1/entities/{robot_id}/attrs", headers=headers ,json=payload)
    if response.status_code == 204:
        print("Faces updated successfully.")
    else:
        print(f"Failed to update faces. Status code: {response.status_code}, Response: {response.text}")

# Function to sanitize the robot ID for use in a filename
def sanitize_filename(filename):
    return filename.replace(':', '_').replace('/', '_').replace('\\', '_')

# Main function to poll the endpoint and process images
def poll_robots():
    recogniser = FaceRecognitionLogic()
    last_observed = ""
    while True:
        try:
            print("Polling...")
            # Poll the entities
            response = requests.get(f"{GATEWAY}/api/broker/ngsi-ld/v1/entities?type={ENTITY_TYPE}", headers=headers)
            print(response)
            if response.status_code == 200:
                robots = response.json()
                print("Response: ", robots)
                
                for robot in robots:
                    robot_id = robot['id']  # Extract the robot ID
                    sanitized_robot_id = sanitize_filename(robot_id)  # Sanitize the robot ID
                    image_url = robot.get("imagepath", {}).get("value")
                    observed_at = robot.get("timestamp", {}).get("observedAt")  # Extract the observedAt timestamp
                    if image_url and observed_at:
                        # Generate a unique filename based on robot ID and timestamp
                        current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                       
                        if(last_observed != observed_at): #Update new image if not done so before
                            image_filename = os.path.join(IMAGE_DIR, f"{sanitized_robot_id}_{current_timestamp}.jpg")

                            # Download the image
                            image = download_image(image_url, image_filename)
                            if image is not None:
                                # Convert the image to grayscale
                                gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                                
                                # Call your face_rec function with the grayscale image
                                faces = recogniser.face_rec(gray_image)  # Make sure to import your face_rec function at the top
                                
                                # Update the NGSI-LD entry with detected faces
                                update_faces(robot_id, faces, observed_at)  # Pass the timestamp
                                last_observed = observed_at
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
