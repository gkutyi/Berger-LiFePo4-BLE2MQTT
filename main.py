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
#import machine
#import urequests
#import ussl
#import socket
#import random
#import struct
#import micropython

import sys

# ruff: noqa: E402
sys.path.append("")

from micropython import const

import asyncio
import aioble
#import bluetooth

import random
import struct

# Wi-Fi-Verbindungsdetails
wifi_ssid = SSID
wifi_password = PASSWORD
wifi_ssid_test = SSID_TEST
wifi_password_test = PASSWORD_TEST

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)

# OTA-Update durchführen
def perform_ota_update():
    firmware_url = "https://raw.githubusercontent.com/gkutyi/Berger-LiFePo4-BLE2MQTT/"
    ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
    if ota_updater.download_and_install_update_if_available():
        return True
    else: return False

# Helper to decode the temperature characteristic encoding (sint16, hundredths of a degree).
def _decode_temperature(data):
    return struct.unpack("<h", data)[0] / 100


async def find_temp_sensor():
    # Scan for 5 seconds, in active mode, with very low interval/window (to
    # maximise detection rate).
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            # See if it matches our name and the environmental sensing service.
            if result.name() == "mpy-temp" and _ENV_SENSE_UUID in result.services():
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
            temp_service = await connection.service(_ENV_SENSE_UUID)
            temp_characteristic = await temp_service.characteristic(_ENV_SENSE_TEMP_UUID)
        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            return

        while connection.is_connected():
            temp_deg_c = _decode_temperature(await temp_characteristic.read())
            print("Temperature: {:.2f}".format(temp_deg_c))
            await asyncio.sleep_ms(1000)


asyncio.run(main())
    
    
