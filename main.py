from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD
from BROKER import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PW, MQTT_TOPIC, MQTT_OTA_UPDATE, MQTT_SSL
from umqtt.simple import MQTTClient
import ubluetooth as bluetooth
import time
import network
import machine
import urequests

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

# MQTT-Client-Instanz erstellen
mqtt_client = None

# Callback-Funktion für das BLE-Scanergebnis
def scan_callback(event, data):
    print('BLE-Scan')
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
    
# Verbindung zu MQTT-Broker herstellen
def connect_mqtt():
    global mqtt_client
    mqtt_client = MQTTClient('esp32', mqtt_broker, port=mqtt_port, user=mqtt_user, password=mqtt_password, ssl=mqtt_ssl)
    mqtt_client.set_callback(mqtt_callback)  # Set the callback function
    mqtt_client.connect()
    print('Connected to MQTT-Broker')

# Nachricht über MQTT veröffentlichen
def publish_to_mqtt(topic, value):
    global mqtt_client
    if mqtt_client is None or not mqtt_client.isconnected():
        connect_mqtt()
    mqtt_client.publish(topic, str(value))

# Funktion zum Prüfen und Ausführen des OTA-Updates
def check_ota_update():
    # Über MQTT prüfen, ob ein OTA-Update erforderlich ist
    mqtt_client.subscribe(ota_topic)
    while True:
        msg = mqtt_client.check_msg()  # Check for incoming message
        time.sleep(1)  # Wait a short time
        print('Message received:', msg)
        if msg is not None and msg.topic.decode() == ota_topic:
            # Nachricht zum Starten des OTA-Updates empfangen
            print('OTA update message received.')
            # Hier können Sie das OTA-Update durchführen
            perform_ota_update()

# OTA-Update durchführen
def perform_ota_update():
    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    ota_updater.download_and_install_update_if_available()
    pass

# BLE-Scan starten
def start_ble_scan():
    ble.active(True)
    ble.gap_scan(0)  # Start scanning, 0 means continuous scanning
    ble.irq(scan_callback) # Set the scan callback
#    ble.gap_scan(1)  # Enable scanning     

# Wi-Fi-Verbindung herstellen
def connect_wifi():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('Verbindung zum WLAN herstellen...')
        sta_if.active(True)
        sta_if.connect(wifi_ssid, wifi_password)
        while not sta_if.isconnected():
            pass
    print('Verbunden:', sta_if.ifconfig())

# Hauptfunktion
def main():
    connect_wifi()
    connect_mqtt()
    start_ble_scan()
    check_ota_update()

if __name__ == '__main__':
    main()
