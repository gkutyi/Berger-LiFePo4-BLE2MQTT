import gc
import ntptime  # Import NTP module
import time
import network
import usocket
import ussl
import ubluetooth as bluetooth
import ubinascii
import struct
from umqtt.simple import MQTTClient
from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD, SSID_TEST, PASSWORD_TEST
from BROKER import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PW, MQTT_TOPIC, MQTT_OTA_UPDATE, MQTT_SSL

# Define the MAC address and UUID of the target BLE device
TARGET_MAC = b'\x04\x7f\x0e\x9e\xd1\x64:'
CHARACTERISTIC_UUID = bluetooth.UUID('fff6')

# Create a BLE object
ble = bluetooth.BLE()
ble.active(True)

# Global variables to hold the connection handle and characteristic handle
conn_handle = None
char_handle = None

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

def perform_ota_update():
    print("Starting OTA update...")
    # Disable BLE before starting OTA update to free up memory
    ble.active(False)
    gc.collect()

    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    
    success = False
    if ota_updater.download_and_install_update_if_available():
        success = True

    # Re-enable BLE after OTA update
    ble.active(True)
    gc.collect()
    print("OTA update completed.")
    return success

def ble_irq(event, data):
    global conn_handle, char_handle

    print('BLE-Scan Event:', event, 'with data:', data)
    try:
        if event == 1:  # 
            conn_handle, addr_type, addr = data
            print(f"WSP32 has connected with MAC: {ubinascii.hexlify(addr)}")
            ble.gattc_discover_services(conn_handle)  # Discover services
        
        elif event == 2:  # 
            conn_handle, addr_type, addr = data
            print("CENTRAL:DISCONNECT")

        elif event == 3:  # 
            conn_handle, addr_type, addr = data
            print("GATT_WRITE")

        elif event == 4:  # 
            conn_handle, addr_type, addr = data
            print("GATTS_READ_REQUET")
        
        elif event == 5:  # GAP scan result
            addr_type, addr, adv_type, rssi, adv_data = data
            print("Found device with address:", addr)
            print("Address type:", addr_type)
            print("Advertisement data:", adv_data)
            if addr == TARGET_MAC:
                print(f"Found Berger-BATT with MAC: {ubinascii.hexlify(addr)}")
                ble.gap_scan(None)  # Stop scanning
                print("Scanning stopped")
                ble.gap_connect(addr_type, addr)  # Connect to the device
                print("Berger-BATT connected")
            
        elif event == 6:  # 
            conn_handle, addr_type, addr = data
            print("SCAN_DONE")    

        elif event == 7:  # Connection complete
            conn_handle, addr_type, addr = data
            print(f"Berger-BATT Connected with MAC: {ubinascii.hexlify(addr)}")
            ble.gattc_discover_services(conn_handle)  # Discover services
        
        elif event == 8:  # 
            conn_handle, addr_type, addr = data
            print("PERIPHERAL DISCONNECT")
        
        elif event == 9:  # Service result
            conn_handle, start_handle, end_handle, uuid = data
            print(f"Service UUID: {uuid}")
            ble.gattc_discover_characteristics(conn_handle, start_handle, end_handle)

        elif event == 10:  # 
            conn_handle, addr_type, addr = data
            print("SERVICE DONE")  
        
        elif event == 11:  # Characteristic result
            conn_handle, def_handle, value_handle, properties, uuid = data
            print(f"Found characteristic with UUID: {uuid}")
            if uuid == CHARACTERISTIC_UUID:
                char_handle = value_handle
                print(f"Found characteristic: {uuid}")
                ble.gattc_write(conn_handle, char_handle, struct.pack('<BB', 0x01, 0x00))  # Enable notifications
    
        elif event == 18 or event == 19:  # Notification or indication
            conn_handle, value_handle, notify_data = data
            print("Event: ", event)
            print("Value_Handle: ", value_handle)
            print("Char_Handle: ", char_handle)
            if value_handle == char_handle:
                print("Notification received:", notify_data)
                # Display part of the data array
                print("Data segment:", notify_data[:5])  # Adjust the slice as needed
            
    except Exception as e:
        print(f"Error in BLE scan callback: {e}")
    
def mqtt_callback(topic, msg):
    print("Received message on topic:", topic.decode(), "with message:", msg.decode())
    if msg.decode() == 'now' and topic.decode() == ota_topic:
        print('OTA update message received.')
        if perform_ota_update():
            gc.collect()
            publish_to_mqtt(ota_topic, 'success')
        else:
            publish_to_mqtt(ota_topic, 'failure')

def start_ble_scan():
    ble.irq(ble_irq)
    ble.gap_scan(10000, 30000, 30000)  # Active scan for 10 seconds

def connect_mqtt():
    global mqtt_client
    try:
        addr_info = usocket.getaddrinfo(MQTT_BROKER, MQTT_PORT)[0][-1]
        sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
        sock.connect(addr_info)

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

def publish_to_mqtt(topic, value):
    global mqtt_client
    mqtt_client.publish(topic, str(value))
    print(f"Published to {topic}: {value}")

def check_mqtt_messages():
    global mqtt_client
    mqtt_client.subscribe(MQTT_OTA_UPDATE)
    while True:
        try:
            mqtt_client.wait_msg()
            gc.collect()
        except Exception as e:
            print(f"Error checking messages: {e}")
            reconnect_mqtt()
            gc.collect()

def reconnect_mqtt():
    global mqtt_client
    connected = False
    attempts = 0
    max_attempts = 5

    while not connected and attempts < max_attempts:
        if mqtt_client is not None:
            mqtt_client.disconnect()
        mqtt_client = None
        gc.collect()

        connected = connect_mqtt()
        if not connected:
            attempts += 1
            print(f"Retrying MQTT connection in 5 seconds... (Attempt {attempts}/{max_attempts})")
            time.sleep(5)

    if not connected:
        print("Max MQTT reconnection attempts reached. Giving up.")

def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    
    attempts = 3
    for attempt in range(attempts):
        try:
            wlan.connect(ssid, password)
            timeout = 5
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
            time.sleep(2)
        
    print(f'Failed to connect to {ssid} after {attempts} attempts')
    return False

def sync_time():
    try:
        ntptime.settime()
        print("Time synchronized successfully")
    except Exception as e:
        print(f"Failed to synchronize time: {e}")

def main():
    if not connect_to_wifi(wifi_ssid, wifi_password):
        connect_to_wifi(wifi_ssid_test, wifi_password_test)
    sync_time()
    start_ble_scan()
    if connect_mqtt():
        check_mqtt_messages()

if __name__ == '__main__':
    main()
