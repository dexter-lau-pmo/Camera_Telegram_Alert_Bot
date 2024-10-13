import os
import logging
import numpy as np
import cv2
import constants as constants
from collections import Counter


class Shatsu(object):
    def __init__(self, img_path):
        self.img_path = img_path
        self.face_cascade = cv2.CascadeClassifier(constants.haarcascade_file_alt) #Assign haarcascade_file_alt file path as base face classifier

    def compress(self, img):
        Z = img.reshape((-1, 3))
        Z = np.float32(Z)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        K = 5
        ret, label, center = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        center = np.uint8(center)
        res = center[label.flatten()]
        res2 = res.reshape((img.shape))
        return res2


 
    #Median color
    def average_color(self, img):
        #print("IMG: ")
        #print(img)
        return np.median(img, axis=(0, 1))  # Use median instead of average

    #Find the mode - most common color in region
    def most_common_color(self, img):

        # Convert each pixel in the image to a color name
        height, width, _ = img.shape
        color_names = []
        
        for row in range(height):
            for col in range(width):
                bgr = img[row, col]  #OpenCV formats in BGR instead of RGB
                rgb = bgr[::-1]    # Get RGB value of the pixel
                color_name = self.rgb_to_color_name(rgb)
                color_names.append(color_name)

        # Calculate the mode (most common color name)
        color_counter = Counter(color_names)
        most_common_color_detected = color_counter.most_common(1)[0][0]  # Get the most frequent color name

        return most_common_color_detected


    def rgb_to_color_name(self, rgb):
        # Simple color name mapping based on RGB values
        #Full list with all permutations of 0,128,255 must be added, or certain color such as purple are overly favoured
        colors = {
            'black': [0, 0, 0],
            'white': [255, 255, 255],
            'red': [255, 0, 0],
            'green': [0, 255, 0],
            'blue': [0, 0, 255],
            'yellow': [255, 255, 0],
            'cyan': [0, 255, 255],
            'magenta': [255, 0, 255],
            'gray': [128, 128, 128],
            'dark_gray': [128, 128, 0],
            'light_gray': [128, 255, 255],
            'dark_red': [128, 0, 0],
            'light_red': [255, 128, 128],
            'dark_green': [0, 128, 0],
            'light_green': [128, 255, 128],
            'dark_blue': [0, 0, 128],
            'light_blue': [128, 128, 255],
            'dark_yellow': [128, 128, 0],
            'light_yellow': [255, 255, 128],
            'orange': [255, 165, 0],
            'purple': [128, 0, 128],
            'light_cyan': [128, 255, 255],
            'dark_cyan': [0, 128, 128],
            'light_magenta': [255, 128, 255],
            'dark_magenta': [128, 0, 128]
        }

        # Find the closest color
        min_diff = float('inf')
        closest_color = None
        for color_name, color_rgb in colors.items():
            diff = np.linalg.norm(np.array(rgb) - np.array(color_rgb)) #Eucledian distance
            #diff = np.sum(np.abs(np.array(rgb) - np.array(color_rgb)))  #Nominal distance

            if diff < min_diff:
                min_diff = diff
                closest_color = color_name

        #print("RGB: " , rgb , "closest color: " , closest_color)

        return closest_color

    def detect_and_display(self):
        img = cv2.imread(self.img_path)
        if img is None:
            logging.error(f"Failed to load image {self.img_path}")
            return

        blur = cv2.GaussianBlur(img, (7, 7), 0)
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except cv2.error:
            logging.debug(f"Error on gray scale conversion {self.img_path[3:]}")
            return  # Exit if the image conversion fails

        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        height, width = img.shape[:2]
        
        if len(faces) == 0:
            logging.debug(f"No faces detected in image '{self.img_path}'")
            return  # Exit if no faces are detected

        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 4)
            percentage_height = h / height  # Calculate the height percentage of the face
            print("Face is " + str(int(percentage_height * 100)) + " percent of picture")

            # Define shirt region coordinates
            shirt_y = int(y + h + (h * 0.5))  # Neck length adjustment
            shirt_x = int((x + w // 3) + (w * 0.1))  # Shift to avoid collar 
            shirt_w = w // 3
            shirt_h = w // 3
            
            # Ensure the shirt region does not exceed the image boundaries
            shirt_y_end = min(shirt_y + shirt_h, height)
            shirt_x_end = min(shirt_x + shirt_w, width)

            # Check if shirt_region has valid dimensions
            if shirt_y < img.shape[0] and shirt_x < img.shape[1]:
                shirt_region = img[shirt_y:min(shirt_y + shirt_h, img.shape[0]), shirt_x:min(shirt_x + shirt_w, img.shape[1])]
                
                # Optionally visualize the shirt region
                #cv2.imshow('Shirt Region', shirt_region)
                #cv2.waitKey(0)

                avg_color = self.average_color(shirt_region)
                
                # Correct BGR to RGB conversion
                closest_color = self.rgb_to_color_name([int(avg_color[2]), int(avg_color[1]), int(avg_color[0])])
                print(f"Average color of the shirt in image '{self.img_path}': R={int(avg_color[2])}, G={int(avg_color[1])}, B={int(avg_color[0])} - Color: {closest_color}")
                
                #Alternate better way of measuring color
                most_common_color_detected = self.most_common_color(shirt_region)
                print("Most common color detected : " , most_common_color_detected)

                # Draw rectangle around the shirt
                cv2.rectangle(img, (shirt_x, shirt_y), (shirt_x + shirt_w, shirt_y + shirt_h), (255, 0, 0), 4)

        # Resizing logic
        if width > 1000:
            scale_percent = 500 / width * 100  # Resize to a width of 500 pixels
            new_width = int(width * scale_percent / 100)
            new_height = int(height * scale_percent / 100)
            resized_img = cv2.resize(img, (new_width, new_height))
        else:
            resized_img = img  # Use original image if not resizing

        # Display the resized image in a window
        cv2.imshow('Detected Image', resized_img)
        cv2.waitKey(0)  # Wait for a key press
        cv2.destroyAllWindows()  # Close window for the current image


    def detect(self, img, x, y, w, h):

        height, width = img.shape[:2]

        # Define shirt region coordinates
        shirt_y = int(y + h + (h * 0.5))  # Neck length adjustment
        shirt_x = int((x + w // 3) + (w * 0.1))  # Shift to avoid collar 
        shirt_w = w // 3
        shirt_h = w // 3

        # Ensure the shirt region does not exceed the image boundaries
        shirt_y_end = min(shirt_y + shirt_h, height)
        shirt_x_end = min(shirt_x + shirt_w, width)

        # Check if shirt_region has valid dimensions
        if shirt_y < img.shape[0] and shirt_x < img.shape[1]:
            shirt_region = img[shirt_y:min(shirt_y + shirt_h, img.shape[0]), shirt_x:min(shirt_x + shirt_w, img.shape[1])]

            # Median color
            avg_color = self.average_color(shirt_region)
            closest_color = self.rgb_to_color_name([int(avg_color[2]), int(avg_color[1]), int(avg_color[0])])

            # Mode color
            #most_common_color_detected = self.most_common_color(shirt_region)
            #print("Most common color detected : " , most_common_color_detected)
            #closest_color = most_common_color_detected

            return closest_color  # Return the color name

        return "Unknown"  # Return None if no valid shirt region is found




if __name__ == '__main__':
    logging.basicConfig(filename='shirt.log',
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        level=logging.DEBUG)

    # Use os to dynamically list image files
    image_folder = './shirts'
    image_files = [os.path.join(image_folder, file) for file in os.listdir(image_folder) if file.endswith('.jpg')]

    for img_path in image_files:
        shatsu_obj = Shatsu(img_path)
        shatsu_obj.detect_and_display()
