#!/usr/bin/env python3

import serial
import time
import os
import glob

def get_rs485_port():
    """Get the actual ttyUSB device that rs485 symlink points to"""
    try:
        if os.path.exists('/dev/rs485'):
            return os.path.basename(os.path.realpath('/dev/rs485'))
    except:
        pass
    return None

def send_at_command(port, command, timeout=2):
    """Send AT command and return response"""
    try:
        ser = serial.Serial(port, 115200, timeout=timeout)
        time.sleep(0.1)
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Send command
        ser.write((command + '\r\n').encode())
        time.sleep(0.5)
        
        # Read response
        response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        ser.close()
        
        return response
    except Exception as e:
        return None

def main():
    # Get RS485 port to exclude
    rs485_port = get_rs485_port()
    print(f"RS485 port: {rs485_port if rs485_port else 'Not found'}")
    
    # Get all ttyUSB ports
    usb_ports = sorted(glob.glob('/dev/ttyUSB*'))
    
    if not usb_ports:
        print("No ttyUSB ports found!")
        return
    
    print(f"Found {len(usb_ports)} USB serial ports")
    
    # Try each port
    for port in usb_ports:
        port_name = os.path.basename(port)
        
        # Skip RS485 port
        if rs485_port and port_name == rs485_port:
            print(f"Skipping {port} (RS485)")
            continue
        
        print(f"Testing {port}...", end=' ')
        
        # Send AT command
        response = send_at_command(port, 'AT')
        
        if response and 'OK' in response:
            print("✓ Modem found!")
            print(f"  Configuring network on {port}...")
            
            # Send configuration command
            config_response = send_at_command(port, 'AT+QNETDEVCTL=1,1,1', timeout=5)
            
            if config_response:
                print(f"  Response: {config_response.strip()}")
                if 'OK' in config_response:
                    print(f"  ✓ Configuration successful on {port}")
                    return  # Exit after configuring first modem port
            else:
                print(f"  ✗ No response to configuration command")
        else:
            print("✗ No response or not a modem")
    
    print("\nNo modem port found!")

if __name__ == "__main__":
    main()