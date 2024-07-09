import gc
import ntptime  # Import NTP module
import time
import network
import usocket
import ussl
import ubluetooth as bluetooth
from umqtt.simple import MQTTClient
from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD, SSID_TEST, PASSWORD_TEST
from BROKER import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PW, MQTT_TOPIC, MQTT_OTA_UPDATE, MQTT_SSL

# Define the UUID of the characteristic
CHARACTERISTIC_UUID = '00001101-0000-1000-8000-00805F9B34FB'

# Create a BLE object
ble = bluetooth.BLE()

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

def scan_callback(event, data):
    try:
        print('BLE-Scan Event:', event, 'with data:', data)
        if event == 1:  # EVT_GAP_SCAN_RESULT
            _, addr_type, addr, _, _, adv_data = data
            print("Found device with address:", addr)
            print("Address type:", addr_type)
            print("Advertisement data:", adv_data)
        elif event == 5:  # EVT_GAP_SCAN_RESULT
            addr_type, addr, adv_type, rssi, adv_data = data
            print("Found device with address:", bytes(addr))
            print("Address type:", addr_type)
            print("Advertisement data:", bytes(adv_data))
            print("RSSI:", rssi)
            print("Advertisment type:", adv_type)
        elif event == 3:  # EVENT_ADV_IND
            addr_type, addr, adv_type, rssi, adv_data = data
            if addr == ble_address:
                ble_connection = bluetooth.BLE()
                ble_connection.active(True)
                peripheral = ble_connection.connect(addr)
                services = peripheral.services()
                for service in services:
                    characteristics = service.characteristics()
                    for char in characteristics:
                        if char.uuid() == CHARACTERISTIC_UUID:
                            while True:
                                value = char.read()
                                print('Received value:', value)
                                publish_to_mqtt(mqtt_topic, value)
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
    ble.active(True)
    ble.gap_scan(10000)
    ble.irq(scan_callback)
    print("BLE scan started.")

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