# This example finds and connects to a BLE temperature sensor (e.g. the one in ble_temperature.py).

# This example demonstrates the low-level bluetooth module. For most
# applications, we recommend using the higher-level aioble library which takes
# care of all IRQ handling and connection management. See
# https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble
# and in particular the temp_client.py example included with aioble.

from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD, SSID_TEST, PASSWORD_TEST
import ubluetooth as bluetooth
#import time
import machine
#import urequests
#import ussl
#import socket
#import random
#import struct
import micropython

import sys

# ruff: noqa: E402
sys.path.append("")

from micropython import const

import asyncio
import central
#import bluetooth

import random
import struct

# Wi-Fi-Verbindungsdetails
wifi_ssid = SSID
wifi_password = PASSWORD
wifi_ssid_test = SSID_TEST
wifi_password_test = PASSWORD_TEST

# BT-Batt service-UUID
_BTBATT_UUID = bluetooth.UUID(0xFFF6)
# org.bluetooth.characteristic.temperature
#_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)

# OTA-Update durchführen
def perform_ota_update():
    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    if ota_updater.download_and_install_update_if_available():
        return True
    else: return False

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
    
# Helper to decode the temperature characteristic encoding (sint16, hundredths of a degree).
def _decode_temperature(data):
    return struct.unpack("<h", data)[0] / 100


async def find_temp_sensor():
    # Scan for 5 seconds, in active mode, with very low interval/window (to
    # maximise detection rate).
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            # See if it matches our name and the environmental sensing service.
            if result.name() == "BT-Battery" and _BTBATT_UUID in result.services():
                return result.device
    return None


async def main():
        # Try to connect to the primary WiFi network
    if not connect_to_wifi(wifi_ssid, wifi_password):
        # If the primary connection fails, try the secondary WiFi network
        connect_to_wifi(wifi_ssid_test, wifi_password_test)
    
    perform_ota_update()
    
    device = await find_temp_sensor()
    if not device:
        print("Temperature sensor not found")
        return

    try:
        print("Connecting to", device)
        connection = await device.connect()
    except asyncio.TimeoutError:
        print("Timeout during connection")
        return

    async with connection:
        try:
            temp_service = await connection.service(_BTBATT_UUID)
            #temp_characteristic = await temp_service.characteristic(_ENV_SENSE_TEMP_UUID)
        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            return

        while connection.is_connected():
            temp_deg_c = _decode_temperature(await temp_characteristic.read())
            print("Temperature: {:.2f}".format(temp_deg_c))
            await asyncio.sleep_ms(1000)


asyncio.run(main())
    
    
