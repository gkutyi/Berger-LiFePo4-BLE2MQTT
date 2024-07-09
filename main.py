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
import usocket
import struct
import ubinascii

# SSL/TLS Parameters
CA_CRT_PATH = "/ssl/ca.crt"  # Path to the root CA certificate

# Define the UUID of the characteristic
CHARACTERISTIC_UUID = bluetooth.UUID('fff6')

# Create a BLE object
ble = bluetooth.BLE()
ble.active(True)

# MAC address of the BLE device
TARGET_MAC = b'\x04\x7f\x0e\x9e\xd1\x64:'

# MQTT connection details
mqtt_broker = MQTT_BROKER
mqtt_port = MQTT_PORT
mqtt_user = MQTT_USER
mqtt_password = MQTT_PW
mqtt_topic = MQTT_TOPIC
ota_topic = MQTT_OTA_UPDATE
mqtt_ssl = MQTT_SSL
CLIENT_ID = 'ESP32WoMoClient'

# Wi-Fi connection details
wifi_ssid = SSID
wifi_password = PASSWORD
wifi_ssid_test = SSID_TEST
wifi_password_test = PASSWORD_TEST

# MQTT client instance
mqtt_client = None

# Global variables to hold the BLE connection handle and characteristic handle
conn_handle = None
char_handle = None

# Callback function for BLE scan result
def ble_irq(event, data):
    global conn_handle, char_handle

    if event == 1:  # GAP scan result
        addr_type, addr, adv_type, rssi, adv_data = data
        if addr == TARGET_MAC:
            print(f"Found target device with MAC: {ubinascii.hexlify(addr)}")
            ble.gap_scan(None)  # Stop scanning
            ble.gap_connect(addr_type, addr)  # Connect to the device

    elif event == 7:  # Connection complete
        conn_handle, addr_type, addr = data
        print(f"Connected to device with MAC: {ubinascii.hexlify(addr)}")
        ble.gattc_discover_services(conn_handle)  # Discover services

    elif event == 8:  # Service result
        conn_handle, start_handle, end_handle, uuid = data
        print(f"Service UUID: {uuid}")
        ble.gattc_discover_characteristics(conn_handle, start_handle, end_handle)

    elif event == 9:  # Characteristic result
        conn_handle, def_handle, value_handle, properties, uuid = data
        if uuid == CHARACTERISTIC_UUID:
            char_handle = value_handle
            print(f"Found characteristic with UUID: {uuid}")
            ble.gattc_write(conn_handle, char_handle, struct.pack('<BB', 0x01, 0x00))  # Enable notifications

    elif event == 11:  # Notification or indication
        conn_handle, value_handle, notify_data = data
        if value_handle == char_handle:
            print("Notification received:", notify_data)
            # Display part of the data array
            print("Data segment:", notify_data[:5])  # Adjust the slice as needed
            publish_to_mqtt(mqtt_topic, notify_data[:5])

# Callback function for incoming MQTT messages
def mqtt_callback(topic, msg):
    print("Received message on topic:", topic.decode(), "with message:", msg.decode())
    if msg.decode() == 'now' and topic.decode() == ota_topic:
        # Nachricht zum Starten des OTA-Updates empfangen
        print('OTA update message received.', msg.decode)
        # Hier können Sie das OTA-Update durchführen
        if perform_ota_update():
            # Sende Wert über MQTT
            publish_to_mqtt(ota_topic, 'success')
        else:
            publish_to_mqtt(ota_topic, 'failure')

# Verbindung zu MQTT-Broker herstellen
def connect_mqtt():
    # Create an SSL context
    context = ussl.SSLContext()
    context.load_verify_locations(CA_CRT_PATH)

    # Create a secure socket
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    addr = usocket.getaddrinfo(MQTT_BROKER, MQTT_PORT)[0][-1]
    sock.connect(addr)
    sock = context.wrap_socket(sock)
    
    global mqtt_client
    mqtt_client = MQTTClient(CLIENT_ID, mqtt_broker, port=mqtt_port, user=mqtt_user, password=mqtt_password, ssl=mqtt_ssl)
    mqtt_client.set_callback(mqtt_callback)  # Set the callback function
    try:
        mqtt_client.set_sock(sock)
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
    else:
        return False

# BLE-Scan starten
def start_ble_scan():
    ble.irq(ble_irq)
    ble.gap_scan(10000, 30000, 30000)  # Active scan for 10 seconds

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

# Synchronize time with an NTP server
def synchronize_time():
    try:
        import ntptime
        ntptime.settime()
        print("Time synchronized successfully")
        return True
    except Exception as e:
        print(f"Failed to synchronize time: {e}")
        return False

# Hauptfunktion
def main():
    # Try to connect to the primary WiFi network
    if not connect_to_wifi(wifi_ssid, wifi_password):
        # If the primary connection fails, try the secondary WiFi network
        connect_to_wifi(wifi_ssid_test, wifi_password_test)

    # Synchronize time before connecting to MQTT broker
    if not synchronize_time():
        print("Time synchronization failed. Continuing without time sync.")

    if connect_mqtt():
        check_mqtt_messages()

    start_ble_scan()

if __name__ == '__main__':
    main()