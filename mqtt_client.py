import paho.mqtt.client as mqtt
import json
import os


class MQTTClient:
    def __init__(self , custom_param):
        self.connect()
        self.client.loop_start()
        print("Custom mqtt param : " , custom_param)

    def on_publish(self, client, userdata, mid):
        print("Message published: ", mid)

    def on_message(self, client, userdata, message):
        print(f"Message received on topic {message.topic}: {message.payload.decode('utf-8')}")
        
    def custom_topic_publish (self, json_object , custom_topic):
        ret = self.client.publish(custom_topic, json.dumps(json_object))
        print(json.dumps(json_object))
        print("Paho ret ", ret)

    def reconnect(self):
        self.client.disconnect()
        self.connect()

    def is_connection_active(self):
        return self.client.is_connected()

    def connect(self):

        BROKER = "35.240.151.148"
        TOPICS = ["/1234/Camera001/attrs", "/1234/Camera002/attrs"]


        broker = BROKER
        port = 1883
        
        self.client = mqtt.Client()

        # Register event handlers
        self.client.on_publish = self.on_publish
        self.client.on_message = self.on_message  # Add on_message callback

        # Connect to the broker
        self.client.connect(broker, port, 60)

        # Subscribe to the /download/trainer topic
        for topic in TOPICS:
            self.client.subscribe(topic)

