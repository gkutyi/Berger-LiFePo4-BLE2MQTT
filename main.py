from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD, SSID_TEST, PASSWORD_TEST
from BROKER import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PW, MQTT_TOPIC, MQTT_OTA_UPDATE, MQTT_SSL
from umqtt.simple import MQTTClient
import ubluetooth as bluetooth
import time
import network
import machine
import urequests
import ussl
import socket

# SSL/TLS Parameters
root_ca = "/flash/ssl/fullchain.pem"  # Path to the root CA certificate

# Load the CA certificate
with open(root_ca, "r") as f:
    ca_cert = f.read()

# Define the UUID of the characteristic
CHARACTERISTIC_UUID = '00001101-0000-1000-8000-00805F9B34FB'

# Create a BLE object
ble = bluetooth.BLE()

# MAC-Adresse des BLE-Geräts
ble_address = 'XX:XX:XX:XX:XX:XX'

# MQTT-Verbindungsdetails
mqtt_broker = MQTT_BROKER
mqtt_port = MQTT_PORT
mqtt_user = MQTT_USER
mqtt_password = MQTT_PW
mqtt_topic = MQTT_TOPIC
ota_topic = MQTT_OTA_UPDATE
mqtt_ssl = MQTT_SSL

# Wi-Fi-Verbindungsdetails
wifi_ssid = SSID
wifi_password = PASSWORD
wifi_ssid_test = SSID_TEST
wifi_password_test = PASSWORD_TEST

# MQTT-Client-Instanz erstellen
mqtt_client = None

# Callback-Funktion für das BLE-Scanergebnis
def scan_callback(event, data):
    print('BLE-Scan')
    print("Event:", event, "with data:", data)
    if event == 1: # EVT_GAP_SCAN_RESULT
        # Parse the data to extract information about the scanned device
        _, addr_type, addr, _, _, adv_data = data
        print("Found device with address:", addr)
        print("Address type:", addr_type)
        print("Advertisement data:", adv_data)
    if event == 3: # EVENT_ADV_IND
        addr_type, addr, adv_type, rssi, adv_data = data
        if addr == ble_address:
            # Verbindung herstellen
            ble_connection = bluetooth.BLE()
            ble_connection.active(True)
            peripheral = ble_connection.connect(addr)

            # Dienst und Charakteristik für Nachrichtenlesen
            services = peripheral.services()
            for service in services:
                characteristics = service.characteristics()
                for char in characteristics:
                    if char.uuid() == 'UUID_der_Charakteristik':
                        while True:
                            value = char.read()
                            # Hier können Sie die empfangenen Werte verarbeiten
                            print('Received value:', value)
                            # Sende Wert über MQTT
                            publish_to_mqtt(value)

# Callback-Funktion für eingehende MQTT-Nachrichten
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
    
# Verbindung zu MQTT-Broker herstellen
def connect_mqtt():
    # Create an SSL context
    ssl_params = {
        'server_hostname': mqtt_broker,
        'certfile': None,
        'keyfile': None,
        'cert_reqs': ussl.CERT_REQUIRED,
        'cadata': ca_cert,
    }
    global mqtt_client
    mqtt_client = MQTTClient('esp32', mqtt_broker, port=mqtt_port, user=mqtt_user, password=mqtt_password, ssl=mqtt_ssl, ssl_params=ssl_params)
    mqtt_client.set_callback(mqtt_callback)  # Set the callback function
    try:
        mqtt_client.connect()
        print('Connected to MQTT-Broker')
        return True
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return False

# Nachricht über MQTT veröffentlichen
def publish_to_mqtt(topic, value):
    global mqtt_client
    mqtt_client.publish(topic, str(value))

# Auf MQTT-Nachrichten prüfen
def check_mqtt_messages():
    # Über MQTT prüfen, ob ein OTA-Update erforderlich ist
    mqtt_client.subscribe(ota_topic)
    while True:
        try:
            mqtt_client.check_msg()  # Check for incoming message
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

# OTA-Update durchführen
def perform_ota_update():
    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    if ota_updater.download_and_install_update_if_available():
        return True
    else: return False

# BLE-Scan starten
def start_ble_scan():
    ble.active(True)
    ble.gap_scan(0)  # Start scanning, 0 means continuous scanning
    ble.irq(scan_callback) # Set the scan callback
#    ble.gap_scan(1)  # Enable scanning     

# Function to reset the WiFi interface
def reset_wifi_interface():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)

# Function to connect to a WiFi network
def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()  # Ensure we start with a clean state
    
    attempts = 3  # Number of attempts to connect
    for attempt in range(attempts):
        try:
            wlan.connect(ssid, password)
            
            timeout = 2  # Seconds to wait for connection
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
        
        # Reset WiFi interface before retrying
        reset_wifi_interface()
        time.sleep(2)  # Short delay to ensure reset is processed
    
    print(f'Failed to connect to {ssid} after {attempts} attempts')
    return False


# Hauptfunktion
def main():
    # Try to connect to the primary WiFi network
    if not connect_to_wifi(wifi_ssid, wifi_password):
        # If the primary connection fails, try the secondary WiFi network
        connect_to_wifi(wifi_ssid_test, wifi_password_test)
    connect_mqtt()
    start_ble_scan()
    check_mqtt_messages()

if __name__ == '__main__':
    main()
