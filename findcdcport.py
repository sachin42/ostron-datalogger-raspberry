#!/usr/bin/env python3
"""
Minimal Quectel Modem AT Commands
Uses dmesg grep to find correct ttyUSB port
"""

import subprocess
import serial
import time
import sys


def find_modem_port():
    """Find first GSM modem (option converter) port from dmesg"""
    try:
        result = subprocess.run(
            "dmesg | grep 'GSM modem'",
            shell=True,
            capture_output=True,
            text=True
        )
        # print(result)
        
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if 'ttyUSB' in line:
                print(line)
                # Extract ttyUSB number: "...attached to ttyUSB1"
                port_num = line.split('ttyUSB')[-1].strip()
                port = f'/dev/ttyUSB{port_num}'
                return port
    except:
        pass
    
    return '/dev/ttyUSB0'  # fallback


def send_at(port, command, wait=1):
    """Send AT command"""
    try:
        ser = serial.Serial(port, 115200, timeout=2)
        ser.reset_input_buffer()
        
        print(f"? {command}")
        ser.write(f"{command}\r\n".encode())
        
        time.sleep(wait)
        response = ""
        while ser.in_waiting > 0:
            response += ser.read(ser.in_waiting).decode(errors='replace')
            time.sleep(0.05)
        
        print(response) if response else print("(no response)")
        ser.close()
        return response
    
    except Exception as e:
        print(f"Error: {e}")
        return None


def setup(apn="airtelgprs.com"):
    """Quick setup sequence"""
    port = find_modem_port()
    print(f"Using port: {port}\n")
    
    send_at(port, "AT", 0.5)
    send_at(port,f'AT+QCFG="usbnet",1', 1)
    send_at(port, f'at+qicsgp=1,1,"{apn}"', 1)
    send_at(port, "AT+QIACT?", 1)
    send_at(port, "at+qnetdevctl=1,1,1", 3)



if __name__ == "__main__":
    apn = sys.argv[1] if len(sys.argv) > 1 else "airtelgprs.com"
    setup(apn)