from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD, SSID_TEST, PASSWORD_TEST
from BROKER import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PW, MQTT_TOPIC, MQTT_OTA_UPDATE, MQTT_SSL
from umqtt.simple import MQTTClient
import network
import usocket
import ussl
import time
import ntptime  # Import NTP module

# SSL/TLS Parameters
CA_CRT_PATH = "/ssl/ca.crt"  # Path to the root CA certificate

# MQTT Connection Details
CLIENT_ID = 'ESP32WoMoClient'
mqtt_topic = MQTT_TOPIC
ota_topic = MQTT_OTA_UPDATE

# Wi-Fi Connection Details
wifi_ssid = SSID
wifi_password = PASSWORD
wifi_ssid_test = SSID_TEST
wifi_password_test = PASSWORD_TEST

# MQTT Client Instance
mqtt_client = None

# OTA-Update durchführen
def perform_ota_update():
    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    if ota_updater.download_and_install_update_if_available():
        return True
    else: return False
    
# Callback Function for Incoming MQTT Messages
def mqtt_callback(topic, msg):
    print("Received message on topic:", topic.decode(), "with message:", msg.decode())
    if msg.decode() == 'now' and topic.decode() == ota_topic:
    # Nachricht zum Starten des OTA-Updates empfangen
        print('OTA update message received.', msg.decode)
        # Hier können Sie das OTA-Update durchführen
        if perform_ota_update():
            # Sende Wert über MQTT
            publish_to_mqtt(ota_topic, 'success')
        else: publish_to_mqtt(ota_topic, 'failure')

# Connect to MQTT Broker with SSL
def connect_mqtt():
    global mqtt_client
    try:
        addr_info = usocket.getaddrinfo(MQTT_BROKER, MQTT_PORT)[0][-1]
        sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
        sock.connect(addr_info)

        # Wrap the socket with SSL
        with open(CA_CRT_PATH, 'rb') as f:
            ca_cert = f.read()
        sock = ussl.wrap_socket(sock, server_hostname=MQTT_BROKER, cert_reqs=ussl.CERT_REQUIRED, cadata=ca_cert)

        mqtt_client = MQTTClient(CLIENT_ID, server=MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PW, ssl=True)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        print('Connected to MQTT-Broker')
        return True
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return False

# Publish Message to MQTT
def publish_to_mqtt(topic, value):
    global mqtt_client
    mqtt_client.publish(topic, str(value))

# Check for MQTT Messages
def check_mqtt_messages():
    global mqtt_client
    mqtt_client.subscribe(MQTT_OTA_UPDATE)
    while True:
        try:
            mqtt_client.wait_msg()
        except Exception as e:
            print(f"Error checking messages: {e}")
            reconnect_mqtt()

def reconnect_mqtt():
    connected = False
    while not connected:
        connected = connect_mqtt()
        if not connected:
            print("Retrying MQTT connection in 5 seconds...")
            time.sleep(5)  # Wait a short time

# Connect to WiFi
def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    
    attempts = 3
    for attempt in range(attempts):
        try:
            wlan.connect(ssid, password)
            timeout = 5  # Seconds to wait for connection
            while not wlan.isconnected() and timeout > 0:
                print(f'Attempting to connect to {ssid}... (Attempt {attempt + 1}/{attempts})')
                time.sleep(1)
                timeout -= 1
            
            if wlan.isconnected():
                print(f'Connected to {ssid}')
                print('Network config:', wlan.ifconfig())
                return True
        except OSError as e:
            print(f'Error on attempt {attempt + 1}: {e}')
            time.sleep(2)  # Wait before retrying
        
    print(f'Failed to connect to {ssid} after {attempts} attempts')
    return False

# Function to synchronize time with NTP server
def sync_time():
    try:
        ntptime.settime()  # Synchronize time from NTP server
        print("Time synchronized successfully")
    except Exception as e:
        print(f"Failed to synchronize time: {e}")

# Main Function
def main():
    if not connect_to_wifi(wifi_ssid, wifi_password):
        connect_to_wifi(wifi_ssid_test, wifi_password_test)
    sync_time()  # Synchronize time before connecting to MQTT
    if connect_mqtt():
        check_mqtt_messages()

if __name__ == '__main__':
    main()
