""" Script to capture data from SwitchBot devices and save in csv file.

* refer to https://github.com/OpenWonderLabs/SwitchBotAPI-BLE 

Quick start:
    * Create venv and install library
        $ python3 -m venv venv
        $ source venv/bin/activate (Linux)
        $ venv/Scripts/activate    (Windows)
        $ pip install bleak
    * Specify the absolute path where data is saved in `LOG_DIRECTORY` variable
      The folder structure should be:
        LOG_DIRECTORY
          0123456789AB    # folder is automatically created. the name is each MAC address
            20240801.csv  # files are separated by day
            20240802.csv
            ...
          123456789ABC
            20240801.csv
            20240802.csv
            ...
    * Run
        $ python main.py
        $ sudo venv/bin/python main.py (if permission is denied)
"""

import os
import datetime
import asyncio
from bleak import BleakScanner

# [USER SETTING] absolute path of data directory
LOG_DIRECTORY = "C:/Users/user/Documents/switchBotLog"

# dictionary to store the previous value of each device
# key: device MAC, value: tuple
prev_val = {}

# dictionary to store the latest data arraival time of each device
# key: device MAC, value: datetime.datetime
prev_time = {}


def decode_plug_power(mf_data: bytes) -> float:
    seqNum = mf_data[6]
    state  = mf_data[7]
    power  = ((mf_data[10] & 0x7f) << 8) + mf_data[11]
    power /= 10.0  # [W]
    return power

def decode_meter_temp_and_hum(mf_data: bytes) -> tuple[float, float]:
    temp_float = mf_data[8] & 0x0f
    temp_int   = mf_data[9] & 0x7f
    temp_sign  = 1 if (mf_data[9] & 0x80) == 0x80 else -1
    temp       = temp_sign * temp_int + 0.1 * temp_float
    hum        = mf_data[10] & 0x7f
    return (temp, hum)

def is_value_different(devaddr, value) -> bool:
    if prev_val.get(devaddr) == None:
        return True
    if prev_val.get(devaddr) != value:
        return True
    return False

def is_day_different(devaddr, now) -> bool:
    if prev_time.get(devaddr) == None:
        return True
    if prev_time.get(devaddr).day != now.day:
        return True
    return False

def update_log_file(address: str, time: datetime.datetime, value):
    # write log only when different value has arrived or the first time after the day has changed
    if is_value_different(address, value) or is_day_different(address, time):
        dir_path = os.path.join(LOG_DIRECTORY, address.replace(":",""))
        file_name = time.strftime("%Y%m%d") + ".csv"
        os.makedirs(dir_path, exist_ok=True)  # create directory if not exist
        with open(os.path.join(dir_path, file_name), "a", encoding="utf-8") as f:
            row = time.strftime("%H:%M:%S.%f")[:-3]  # milli seconds
            row += ","
            row += ",".join([str(i) for i in value])  # tuple to str. eg) [12, 14] -> "12,14"
            f.write(row + "\n")
            print(address, row)


async def main():

    stop_event = asyncio.Event()

    def callback(device, advertising_data):

        # data received time
        now = datetime.datetime.now()

        # manufacturer_data is dictionary and the keys are Bluetooth SIG assigned Company Identifiers
        # the company identifier of SwitchBot is 2409 (Woan Technology (Shenzhen) Co., Ltd.)
        if 2409 in advertising_data.manufacturer_data:

            # type of the device is contained in service_data[0]. so service data should exist
            if advertising_data.service_data:
                service_data_bytes = advertising_data.service_data['0000fd3d-0000-1000-8000-00805f9b34fb']
                manufacturer_data_bytes = advertising_data.manufacturer_data[2409]

                # Meter device
                if service_data_bytes[0] == 0x54 or service_data_bytes[0] == 0x77:
                    # get temperature and humidity from data bytes
                    (temp, hum) = decode_meter_temp_and_hum(manufacturer_data_bytes)

                    # write log only when different value has arrived or day has changed
                    if is_value_different(device.address, (temp, hum)) or is_day_different(device.address, now):
                        update_log_file(
                            device.address,
                            now,
                            (temp, hum)
                        )
                        prev_val[device.address] = (temp, hum)
                        prev_time[device.address] = now
                
                # Plug device
                if service_data_bytes[0] == 0x6a:
                    # get power from data bytes
                    power = decode_plug_power(manufacturer_data_bytes)

                    # write log only when different value has arrived or day has changed
                    if is_value_different(device.address, (power, )) or is_day_different(device.address, now):
                        update_log_file(
                            device.address,
                            now,
                            (power, )
                        )
                        prev_val[device.address] = (power, )
                        prev_time[device.address] = now

    async with BleakScanner(callback) as scanner:
        await stop_event.wait()


asyncio.run(main())
