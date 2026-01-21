"""
Diagnostic module for datalogger application.

Handles:
- Pre-startup diagnostics (modem configuration, network validation, internet connectivity)
- Continuous internet monitoring with auto-restart capability
- Extensibility for future diagnostic features
"""

import logging
import time
import subprocess
import threading
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
import requests
import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    check_name: str
    success: bool
    message: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def __str__(self):
        status = "PASS" if self.success else "FAIL"
        return f"[{status}] {self.check_name}: {self.message}"


class DiagnosticMonitor:
    """
    Continuous monitoring thread for internet connectivity.

    Monitors internet connectivity at regular intervals and triggers
    auto-restart if internet is unavailable for extended period.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Status tracking
        self._last_internet_success: Optional[datetime] = None
        self._last_check_time: Optional[datetime] = None
        self._last_restart_time: Optional[datetime] = None
        self._restart_count = 0
        self._consecutive_failures = 0

        # Configuration (loaded from environment)
        self._check_interval_minutes = 5
        self._internet_timeout_minutes = 30
        self._auto_restart_enabled = True
        self._restart_cooldown_minutes = 30

        # Load configuration from environment
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables."""
        try:
            self._check_interval_minutes = int(
                os.getenv('DIAGNOSTIC_CHECK_INTERVAL_MINUTES', '5')
            )
            self._internet_timeout_minutes = int(
                os.getenv('DIAGNOSTIC_INTERNET_TIMEOUT_MINUTES', '30')
            )
            self._auto_restart_enabled = os.getenv(
                'DIAGNOSTIC_AUTO_RESTART_ENABLED', 'true'
            ).lower() == 'true'
            self._restart_cooldown_minutes = int(
                os.getenv('DIAGNOSTIC_RESTART_COOLDOWN_MINUTES', '30')
            )

            logger.info(
                f"Diagnostic configuration loaded: "
                f"check_interval={self._check_interval_minutes}min, "
                f"timeout={self._internet_timeout_minutes}min, "
                f"auto_restart={self._auto_restart_enabled}, "
                f"cooldown={self._restart_cooldown_minutes}min"
            )
        except Exception as e:
            logger.warning(f"Error loading diagnostic config, using defaults: {e}")

    def start(self):
        """Start the diagnostic monitoring thread."""
        with self._lock:
            if self._running:
                logger.warning("Diagnostic monitor already running")
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="DiagnosticMonitor"
            )
            self._thread.start()
            logger.info("Diagnostic monitoring thread started")

    def stop(self):
        """Stop the diagnostic monitoring thread."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            logger.info("Diagnostic monitoring thread stopping")

        if self._thread:
            self._thread.join(timeout=10)

    def _monitoring_loop(self):
        """Main monitoring loop."""
        logger.info("Diagnostic monitoring loop started")

        while self._running:
            try:
                self._perform_check()

                # Sleep in small intervals to allow quick shutdown
                sleep_seconds = self._check_interval_minutes * 60
                for _ in range(sleep_seconds):
                    if not self._running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in diagnostic monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying after error

        logger.info("Diagnostic monitoring loop stopped")

    def _perform_check(self):
        """Perform a single internet connectivity check and handle results."""
        self._last_check_time = datetime.now()

        # Check internet connectivity
        result = check_internet_connectivity()

        if result.success:
            self._last_internet_success = datetime.now()
            self._consecutive_failures = 0
            logger.debug("Internet connectivity check: PASS")
        else:
            self._consecutive_failures += 1
            logger.warning(
                f"Internet connectivity check: FAIL "
                f"(consecutive failures: {self._consecutive_failures})"
            )

            # Check if we should trigger restart
            if self._last_internet_success:
                time_without_internet = datetime.now() - self._last_internet_success
                minutes_without_internet = time_without_internet.total_seconds() / 60

                logger.warning(
                    f"Time without internet: {minutes_without_internet:.1f} minutes "
                    f"(threshold: {self._internet_timeout_minutes} minutes)"
                )

                if minutes_without_internet >= self._internet_timeout_minutes:
                    self._handle_internet_timeout()

    def _handle_internet_timeout(self):
        """Handle internet timeout condition (potentially trigger restart)."""
        if not self._auto_restart_enabled:
            logger.warning(
                "Internet timeout threshold reached, but auto-restart is disabled"
            )
            return

        # Check restart cooldown
        if self._last_restart_time:
            time_since_restart = datetime.now() - self._last_restart_time
            cooldown_minutes = time_since_restart.total_seconds() / 60

            if cooldown_minutes < self._restart_cooldown_minutes:
                logger.warning(
                    f"Restart cooldown active "
                    f"({cooldown_minutes:.1f}/{self._restart_cooldown_minutes} minutes), "
                    f"skipping restart"
                )
                return

        # Trigger restart
        logger.critical(
            f"Internet unavailable for {self._internet_timeout_minutes}+ minutes, "
            f"triggering system restart"
        )

        self._restart_count += 1
        self._last_restart_time = datetime.now()

        # Send error notification before restarting
        try:
            from modules.network import send_error_to_endpoint
            send_error_to_endpoint(
                "INTERNET_TIMEOUT_RESTART",
                f"No internet for {self._internet_timeout_minutes}+ minutes. "
                f"Auto-restarting system (restart #{self._restart_count})."
            )
        except Exception as e:
            logger.error(f"Failed to send error notification before restart: {e}")

        # Trigger system reboot
        try:
            logger.critical("Executing system reboot command")
            subprocess.run(['sudo', 'reboot'], check=True, timeout=10)
        except subprocess.TimeoutExpired:
            logger.critical("Reboot command timed out, but should still execute")
        except Exception as e:
            logger.critical(f"Failed to execute reboot command: {e}")

    def get_status(self) -> dict:
        """Get current monitoring status."""
        with self._lock:
            status = {
                'running': self._running,
                'last_check_time': self._last_check_time,
                'last_internet_success': self._last_internet_success,
                'consecutive_failures': self._consecutive_failures,
                'restart_count': self._restart_count,
                'last_restart_time': self._last_restart_time,
                'config': {
                    'check_interval_minutes': self._check_interval_minutes,
                    'internet_timeout_minutes': self._internet_timeout_minutes,
                    'auto_restart_enabled': self._auto_restart_enabled,
                    'restart_cooldown_minutes': self._restart_cooldown_minutes,
                }
            }

            # Calculate time without internet
            if self._last_internet_success:
                time_without_internet = datetime.now() - self._last_internet_success
                status['minutes_without_internet'] = time_without_internet.total_seconds() / 60
            else:
                status['minutes_without_internet'] = None

            return status


# Global diagnostic monitor instance
diagnostic_monitor = DiagnosticMonitor()


def find_quectel_modem() -> Optional[str]:
    """
    Find Quectel EC200U/G modem AT command port on Raspberry Pi.

    Quectel modems create multiple /dev/ttyUSB* ports. The AT command port
    is typically /dev/ttyUSB2 or /dev/ttyUSB3. This function tests each
    Quectel port to find the one that responds to AT commands.

    Returns:
        Port name (e.g., '/dev/ttyUSB2') or None if not found
    """
    logger.info("Scanning for Quectel EC200U/G modem AT port...")

    # Known RS485 converter identifiers to exclude
    rs485_identifiers = [
        'CH340',  # Common USB-to-RS485 converter
        'FT232',  # FTDI USB-to-RS485
        'CP210',  # Silicon Labs USB-to-RS485
    ]

    # Quectel modem identifiers
    quectel_identifiers = [
        'Quectel',
        'EC200',
        '2C7C',  # Quectel vendor ID
    ]

    try:
        ports = serial.tools.list_ports.comports()
        quectel_ports = []

        for port in ports:
            # Only consider /dev/ttyUSB* ports on Raspberry Pi
            if not port.device.startswith('/dev/ttyUSB'):
                continue

            port_info = f"{port.device}: {port.description} [{port.manufacturer}]"

            # Check if it's an RS485 converter (exclude these)
            is_rs485 = any(
                identifier.lower() in str(port).lower()
                for identifier in rs485_identifiers
            )

            if is_rs485:
                logger.debug(f"Skipping RS485 converter: {port_info}")
                continue

            # Check if it's a Quectel modem
            is_quectel = any(
                identifier.lower() in str(port).lower()
                for identifier in quectel_identifiers
            )

            if is_quectel:
                logger.info(f"Found Quectel port: {port_info}")
                quectel_ports.append(port.device)

        # Test each Quectel port to find the AT command port
        for port_device in quectel_ports:
            logger.debug(f"Testing {port_device} for AT command response...")
            try:
                with serial.Serial(port_device, baudrate=115200, timeout=1) as ser:
                    time.sleep(0.3)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    # Send AT command
                    ser.write(b"AT\r\n")
                    time.sleep(0.3)

                    # Read response
                    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')

                    if 'OK' in response:
                        logger.info(f"Found AT command port: {port_device}")
                        return port_device
                    else:
                        logger.debug(f"{port_device} did not respond to AT command")
            except Exception as e:
                logger.debug(f"Failed to test {port_device}: {e}")
                continue

        logger.warning("Quectel modem AT port not found")
        return None

    except Exception as e:
        logger.error(f"Error scanning for modem: {e}", exc_info=True)
        return None


def configure_quectel_modem(port: str, max_retries: int = 3) -> DiagnosticResult:
    """
    Configure Quectel modem by sending AT commands to enable network.

    Commands:
    1. Switch from RNDIS to ECM mode: AT+QCFG="usbnet",1
    2. Configure APN: at+qicsgp=1,1,"apn"
    3. Check context activation: AT+QIACT?
    4. Dial network: at+qnetdevctl=1,1,1

    Args:
        port: Serial port name (e.g., '/dev/ttyUSB2')
        max_retries: Maximum number of retry attempts

    Returns:
        DiagnosticResult indicating success or failure
    """
    logger.info(f"Configuring Quectel modem on {port}...")

    # Get APN from environment variable (default to common APN if not set)
    apn = os.getenv('MODEM_APN', 'airtelgprs.com')
    logger.info(f"Using APN: {apn}")

    at_commands = [
        ('AT', 'OK', 'Check modem response'),
        ('AT+QCFG="usbnet",1', 'OK', 'Switch to ECM mode'),
        (f'AT+QICSGP=1,1,"{apn}"', 'OK', f'Configure APN: {apn}'),
        ('AT+QIACT?', '+QIACT', 'Check context activation'),
        ('AT+QNETDEVCTL=1,1,1', 'OK', 'Dial network'),
    ]

    for attempt in range(max_retries):
        try:
            with serial.Serial(port, baudrate=115200, timeout=3) as ser:
                time.sleep(0.5)  # Allow port to stabilize

                # Clear any pending data
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Send AT commands
                for command, expected_response, description in at_commands:
                    logger.debug(f"Sending: {command} ({description})")

                    # Send command
                    ser.write(f"{command}\r\n".encode())
                    time.sleep(1)  # Wait for modem to process

                    # Read response
                    response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    logger.debug(f"Response: {response.strip()}")

                    # Check for expected response
                    if expected_response not in response:
                        # For QIACT check, if we get "ERROR" it might mean already activated
                        if command.startswith('AT+QIACT?') and 'ERROR' in response:
                            logger.debug("Context might already be activated, continuing...")
                        else:
                            raise Exception(
                                f"Unexpected response to '{command}': {response.strip()}"
                            )

                logger.info("Modem configuration successful")
                return DiagnosticResult(
                    "Modem Configuration",
                    True,
                    f"Successfully configured on {port} with APN {apn}"
                )

        except Exception as e:
            logger.warning(
                f"Modem configuration attempt {attempt + 1}/{max_retries} failed: {e}"
            )

            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retry
            else:
                logger.error(f"Failed to configure modem after {max_retries} attempts")
                return DiagnosticResult(
                    "Modem Configuration",
                    False,
                    f"Failed after {max_retries} attempts: {str(e)}"
                )

    return DiagnosticResult(
        "Modem Configuration",
        False,
        "Failed: Maximum retries exceeded"
    )


def check_network_interface(interface: str = 'eth0', max_wait_seconds: int = 120) -> DiagnosticResult:
    """
    Check if network interface has an IP address assigned.

    Waits up to max_wait_seconds for IP assignment.

    Args:
        interface: Network interface name (e.g., 'eth0', 'usb0')
        max_wait_seconds: Maximum time to wait for IP assignment

    Returns:
        DiagnosticResult indicating success or failure
    """
    logger.info(f"Checking network interface {interface} (max wait: {max_wait_seconds}s)...")

    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        try:
            # Use 'ip addr show' command to check interface
            result = subprocess.run(
                ['ip', 'addr', 'show', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                output = result.stdout

                # Look for 'inet ' followed by IP address
                if 'inet ' in output:
                    # Extract IP address
                    for line in output.split('\n'):
                        if 'inet ' in line:
                            ip_addr = line.strip().split()[1].split('/')[0]
                            logger.info(f"Interface {interface} has IP: {ip_addr}")
                            return DiagnosticResult(
                                "Network Interface",
                                True,
                                f"{interface} has IP address: {ip_addr}"
                            )

            # Wait before checking again
            time.sleep(5)
            elapsed = time.time() - start_time
            logger.debug(
                f"Waiting for {interface} IP assignment... ({elapsed:.0f}s/{max_wait_seconds}s)"
            )

        except subprocess.TimeoutExpired:
            logger.warning("Command timeout while checking network interface")
        except Exception as e:
            logger.warning(f"Error checking network interface: {e}")

    # Timeout reached
    logger.warning(f"Network interface {interface} did not get IP within {max_wait_seconds}s")
    return DiagnosticResult(
        "Network Interface",
        False,
        f"{interface} did not get IP address within {max_wait_seconds}s"
    )


def check_internet_connectivity(timeout: int = 10) -> DiagnosticResult:
    """
    Check internet connectivity by attempting HTTP requests to multiple endpoints.

    Tries multiple fallback endpoints to increase reliability.

    Args:
        timeout: Request timeout in seconds

    Returns:
        DiagnosticResult indicating success or failure
    """
    # Multiple endpoints for redundancy
    endpoints = [
        ('https://www.google.com', 'Google'),
        ('https://1.1.1.1', 'Cloudflare DNS'),
        ('http://portal.cpcbocems.com', 'CPCB Portal'),
    ]

    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code in [200, 301, 302, 303, 307, 308]:
                return DiagnosticResult(
                    "Internet Connectivity",
                    True,
                    f"Connected (verified via {name})"
                )
        except requests.exceptions.RequestException:
            continue  # Try next endpoint

    # All endpoints failed
    return DiagnosticResult(
        "Internet Connectivity",
        False,
        "Unable to reach any test endpoint"
    )


def run_internet_check() -> DiagnosticResult:
    """
    Wrapper for internet connectivity check.

    Returns:
        DiagnosticResult from check_internet_connectivity()
    """
    return check_internet_connectivity()


def run_pre_startup_diagnostics() -> List[DiagnosticResult]:
    """
    Run all pre-startup diagnostic checks.

    This function orchestrates all diagnostic checks that should run
    before the main application starts:
    1. Find and configure Quectel modem
    2. Wait for network interface to get IP
    3. Check internet connectivity
    4. Wait 30 seconds for network stability

    Returns:
        List of DiagnosticResult objects
    """
    logger.info("=" * 70)
    logger.info("Running pre-startup diagnostics...")
    logger.info("=" * 70)

    results: List[DiagnosticResult] = []

    # Step 1: Find Quectel modem
    modem_port = find_quectel_modem()

    if modem_port:
        results.append(
            DiagnosticResult("Modem Detection", True, f"Found on {modem_port}")
        )

        # Step 2: Configure modem
        config_result = configure_quectel_modem(modem_port)
        results.append(config_result)
    else:
        results.append(
            DiagnosticResult(
                "Modem Detection",
                False,
                "Quectel modem not found (ethernet may work)"
            )
        )

    # Step 3: Check network interface
    network_result = check_network_interface('eth0', max_wait_seconds=120)
    results.append(network_result)

    # Step 4: Check internet connectivity
    internet_result = check_internet_connectivity()
    results.append(internet_result)

    # Step 5: Wait for network stability
    if network_result.success:
        logger.info("Waiting 30 seconds for network stability...")
        time.sleep(30)
        results.append(
            DiagnosticResult(
                "Network Stability Wait",
                True,
                "Waited 30 seconds for network stabilization"
            )
        )

    # Log summary
    logger.info("=" * 70)
    logger.info("Pre-startup diagnostic results:")
    for result in results:
        logger.info(f"  {result}")
    logger.info("=" * 70)

    # Set initial internet success time if connectivity check passed
    if internet_result.success:
        diagnostic_monitor._last_internet_success = datetime.now()

    return results
