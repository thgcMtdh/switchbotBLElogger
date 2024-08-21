""" Script to capture data from SwitchBot devices and save in csv file.

* refer to https://github.com/OpenWonderLabs/SwitchBotAPI-BLE 

Todo:
    * Create venv and install library
        $ python3 -m venv venv
        $ source venv/bin/activate (Linux)
        $ venv/Scripts/activate    (Windows)
        $ pip install bluepy
    * Append BLE mac address of target SwitchBot devices in `SWITCHBOT_MAC_LIST`
      Address is shown in the SwitchBot App (Currently, only Plug and Meter are supported)
    * Fill in `LOG_DIRECTORY`
    * Run
        $ python main.py
        $ sudo venv/bin/python main.py (if permission is denied)

"""

import datetime
from bluepy.btle import Scanner

# BLE MAC addresses of target devices. It can be obtained by the SwitchBot App
SWITCHBOT_MAC_LIST=  [
    "40:4c:ca:a8:18:de",  # Plug Mini (EcoFlow input)
    "60:55:f9:3c:63:5e",  # Plug Mini (Aircon)
    "d3:35:34:35:65:74",  # Meter (1. FL+0.1m)
    "d2:35:34:35:32:76",  # Meter (2. FL+1.1m)
    "cf:35:34:35:3b:56",  # Meter (3. CH-0.1m)
    "c9:45:08:22:f3:99",  # Meter (outside)
]

# absolute path of data directory
# folder structure is:
#   LOG_DIRECTORY
#     0123456789ab  # folder is automatically created. the name is each MAC address
#       20240801.csv  # files are separated by day
#       20240802.csv
#       ...
#     123456789abc
#       20240801.csv
#       20240802.csv
#       ...
LOG_DIRECTORY = "/home/hibiki/Documents/temperatureLog"


def get_broadcast_message(device) -> tuple[str, str]:
    manufacturer_data = ""
    service_data = ""
    for (adtype, desc, value) in device.getScanData():
        if adtype == 0xff:
            manufacturer_data = value
        if adtype == 0x16:
            service_data = value
    return (manufacturer_data, service_data)

def decode_plug_power(mf_data: bytes) -> float:
    seqNum = mf_data[8]
    state  = mf_data[9]
    power  = ((mf_data[12] & 0x7f) << 8) + mf_data[13]
    power /= 10.0  # [W]
    return power

def decode_meter_temp_and_hum(mf_data: bytes) -> tuple[float, float]:
    temp_float = mf_data[10] & 0x0f
    temp_int   = mf_data[11] & 0x7f
    temp_sign  = 1 if (mf_data[11] & 0x80) == 0x80 else -1
    temp       = temp_sign * temp_int + 0.1 * temp_float
    hum        = mf_data[12] & 0x7f
    return (temp, hum)

def update_log_file(dir: str, time: datetime.datetime, value):
    path = dir + "/" + time.strftime("%Y%m%d") + ".csv"
    with open(path, "a", encoding="utf-8") as f:
        row = time.strftime("%Y/%m/%d %H:%M:%S")
        row += ","
        row += ",".join([str(i) for i in value])  # tuple to str. eg) [12, 14] -> "12,14"
        f.write(row + "\n")

def main():

    # previous scan time
    prev_time = None

    # dictionary to store the previous value of each device
    prev_val = {}
    for mac in SWITCHBOT_MAC_LIST:
        prev_val[mac] = None

    def is_value_different(devaddr, value) -> bool:
        if prev_val[devaddr] == None:
            return True
        if prev_val[devaddr] != value:
            return True
        return False

    def is_day_different(now) -> bool:
        if prev_time == None:
            return True
        if prev_time.day != now.day:
            return True
        return False

    scanner = Scanner()
    try:
        while True:  # infinite loop to continuously scan BLE. press Ctrl+C to stop
            now = datetime.datetime.now()
            devices = scanner.scan(1)  # scan BLE advertising packets for 1 sec

            for dev in devices:
                if dev.addr in SWITCHBOT_MAC_LIST:  # find switchbot device

                    # get broadcast message from device
                    (manufacturer_data, service_data) = get_broadcast_message(dev)

                    # skip if the message wasn't retrieved properly
                    if manufacturer_data == "" or service_data == "":
                        continue

                    # convert message(str) to bytes
                    manufacturer_data_bytes = bytes.fromhex(manufacturer_data)
                    service_data_bytes = bytes.fromhex(service_data)

                    # Meter device
                    if service_data_bytes[2] == 0x54 or service_data_bytes[2] == 0x77:
                        # get temperature and humidity from data bytes
                        (temp, hum) = decode_meter_temp_and_hum(manufacturer_data_bytes)

                        # write log only when different value has arrived or day has changed
                        if is_value_different(dev.addr, (temp, hum)) or is_day_different(now):
                            update_log_file(
                                LOG_DIRECTORY + "/" + dev.addr.replace(":",""),
                                now,
                                (temp, hum)
                            )
                            prev_val[dev.addr] = (temp, hum)
                    
                    # Plug device
                    if service_data_bytes[2] == 0x6a:
                        # get power from data bytes
                        power = decode_plug_power(manufacturer_data_bytes)
                        # if power < 0.5:  # my aircon repeats 0.3 and 0.0 on standby so ignore small value
                        #     power = 0.0

                        # write log only when different value has arrived or day has changed
                        if is_value_different(dev.addr, (power, )) or is_day_different(now):
                            update_log_file(
                                LOG_DIRECTORY + "/" + dev.addr.replace(":",""),
                                now,
                                (power, )
                            )
                            prev_val[dev.addr] = (power, )
            
            prev_time = now


    except KeyboardInterrupt:
        print("finish")


if __name__ == "__main__":
    main()
