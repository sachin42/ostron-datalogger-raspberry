"""
LED status indicators via Raspberry Pi GPIO (BCM numbering).

  GPIO 17 — Internet connectivity   ON = connected,       OFF = no internet
  GPIO 27 — CPCB server             ON = last send OK,    OFF = last send failed
  GPIO 22 — Data fetch heartbeat    double-blink on each successful fetch cycle

Design:
  - GPIO objects initialised once on first use; atexit cleanup turns LEDs off
    and calls GPIO.cleanup() so the kernel releases the pins cleanly.
  - GPIO 17 is polled every 30 s inside the LED thread.
  - GPIO 27 is driven immediately by notify_cpcb_success/failure() called from
    the logger thread — no polling delay.
  - GPIO 22 is driven by an Event set by notify_fetch() from the data collection
    thread; the LED thread blinks it within 1 s of the actual fetch.
"""
import atexit
import socket
import threading
import time

from .constants import logger

# GPIO pin assignments (BCM numbering)
GPIO_INTERNET = 17
GPIO_CPCB     = 27
GPIO_FETCH    = 22

INTERNET_CHECK_INTERVAL = 30   # seconds

# ---------------------------------------------------------------------------
# RPi.GPIO — graceful fallback when running off-Pi
# ---------------------------------------------------------------------------
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    logger.debug("RPi.GPIO loaded successfully")
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available — LED status indicators disabled")

_gpio_ready = False
_gpio_lock  = threading.Lock()


def _init_gpio() -> bool:
    """Initialise all three GPIO pins once. Thread-safe."""
    global _gpio_ready
    if _gpio_ready:
        return True
    if not GPIO_AVAILABLE:
        return False

    with _gpio_lock:
        if _gpio_ready:            # re-check inside lock
            return True
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in (GPIO_INTERNET, GPIO_CPCB, GPIO_FETCH):
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            atexit.register(_cleanup_gpio)
            _gpio_ready = True
            logger.info(
                f"LED GPIO ready — "
                f"internet=GPIO{GPIO_INTERNET}  cpcb=GPIO{GPIO_CPCB}  fetch=GPIO{GPIO_FETCH}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialise LED GPIO: {e}")
            return False


def _cleanup_gpio() -> None:
    """Turn off all LEDs and release GPIO pins on process exit."""
    global _gpio_ready
    logger.info("Releasing LED GPIO pins...")
    try:
        if _gpio_ready:
            for pin in (GPIO_INTERNET, GPIO_CPCB, GPIO_FETCH):
                GPIO.output(pin, GPIO.LOW)
            GPIO.cleanup([GPIO_INTERNET, GPIO_CPCB, GPIO_FETCH])
            logger.info("LED GPIO released cleanly")
    except Exception as e:
        logger.warning(f"LED GPIO cleanup warning: {e}")
    finally:
        _gpio_ready = False


# ---------------------------------------------------------------------------
# Low-level LED helpers
# ---------------------------------------------------------------------------
def _set_led(pin: int, on: bool) -> None:
    if not _gpio_ready:
        return
    try:
        GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)
    except Exception as e:
        logger.debug(f"LED pin {pin} set error: {e}")


def _blink(pin: int, count: int = 2, on_time: float = 0.15) -> None:
    """Brief blink — runs inside the LED thread, blocks for count * on_time * 2 seconds."""
    if not _gpio_ready:
        return
    try:
        for _ in range(count):
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(on_time)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(on_time)
    except Exception as e:
        logger.debug(f"LED pin {pin} blink error: {e}")


# ---------------------------------------------------------------------------
# Internet check
# ---------------------------------------------------------------------------
def _check_internet() -> bool:
    """TCP connect to Google DNS on port 53 — fast, no HTTP, no DNS lookup."""
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Public notify API — called from other threads
# ---------------------------------------------------------------------------
_fetch_event = threading.Event()


def notify_fetch() -> None:
    """
    Call from data_collection_thread after a successful sensor fetch.
    GPIO 22 will double-blink within 1 second.
    """
    _fetch_event.set()


def notify_cpcb_success() -> None:
    """
    Call from logger_thread after a successful CPCB send.
    GPIO 27 turns ON immediately (no waiting for LED thread loop).
    """
    if _init_gpio():
        _set_led(GPIO_CPCB, True)


def notify_cpcb_failure() -> None:
    """
    Call from logger_thread after a failed CPCB send.
    GPIO 27 turns OFF immediately.
    """
    if _init_gpio():
        _set_led(GPIO_CPCB, False)


# ---------------------------------------------------------------------------
# LED thread — start once from datalogger_app.py
# ---------------------------------------------------------------------------
def led_status_thread() -> None:
    """
    Polls internet every 30 s and reacts to fetch events.
    CPCB LED is driven directly by notify_cpcb_*() — not managed here.
    """
    if not _init_gpio():
        logger.warning("LED status thread: GPIO unavailable, thread exiting")
        return

    logger.info("LED status thread started")
    last_internet_check = 0.0

    while True:
        try:
            now = time.time()

            # Internet connectivity check every 30 seconds
            if now - last_internet_check >= INTERNET_CHECK_INTERVAL:
                online = _check_internet()
                _set_led(GPIO_INTERNET, online)
                logger.debug(f"Internet check: {'OK' if online else 'OFFLINE'}")
                last_internet_check = now

            # Fetch heartbeat — blink GPIO 22 when data collection fires
            if _fetch_event.is_set():
                _fetch_event.clear()
                _blink(GPIO_FETCH, count=2, on_time=0.15)

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error in LED status thread: {e}")
            time.sleep(5)
