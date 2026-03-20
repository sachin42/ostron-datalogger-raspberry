"""
ADS1115 16-bit ADC fetcher for Raspberry Pi (I2C)

Fixed hardware config:
  - I2C address: 0x48 (ADDR pin → GND)
  - Gain: 1 (±4.096V range)
  - Shunt resistor: 150Ω  →  4mA=0.6V, 20mA=3.0V

Scaling methods (configured per channel):
  range  – linearly maps 4-20mA to [min_value, max_value]
  factor – value = current_mA * factor

I2C/ADS objects are created once on first use and reused for the life of the
process. atexit cleanup ensures the I2C bus is released cleanly on exit so
the kernel driver doesn't hold a stale file descriptor if the app is restarted.
"""
import atexit
import threading
from typing import Optional, Dict, Any, List

from .constants import logger

# Fixed hardware constants
SHUNT_OHMS  = 150       # Shunt resistor in ohms
I2C_ADDRESS = 0x48      # ADDR pin → GND
GAIN        = 1         # ±4.096V range

# 4-20mA current boundaries
MA_MIN = 4.0
MA_MAX = 20.0

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    ADS1115_AVAILABLE = True
    logger.debug("ADS1115 library loaded successfully")
except ImportError:
    ADS1115_AVAILABLE = False
    logger.warning("ADS1115 library not available. "
                   "On Raspberry Pi run: pip install adafruit-circuitpython-ads1x15")

# ---------------------------------------------------------------------------
# Singleton I2C / ADS1115 objects — created once, reused forever
# ---------------------------------------------------------------------------
_i2c: Optional[object] = None
_ads: Optional[object] = None
_init_lock = threading.Lock()          # guards one-time initialisation


def _init_hardware() -> bool:
    """
    Initialise I2C bus and ADS1115 exactly once for the lifetime of the process.
    Thread-safe via double-checked locking.
    Returns True if hardware is ready to use.
    """
    global _i2c, _ads

    if _ads is not None:               # fast path — already initialised
        return True

    if not ADS1115_AVAILABLE:
        logger.error("ADS1115 library not available")
        return False

    with _init_lock:
        if _ads is not None:           # re-check inside lock
            return True
        try:
            logger.info("Initialising ADS1115 I2C hardware (once per process)...")
            _i2c = busio.I2C(board.SCL, board.SDA)
            _ads = ADS.ADS1115(_i2c, address=I2C_ADDRESS)
            _ads.gain = GAIN
            logger.info(f"ADS1115 ready — I2C 0x{I2C_ADDRESS:02X}, gain={GAIN} (±4.096V)")
            atexit.register(_cleanup_hardware)
            return True
        except Exception as e:
            logger.error(f"Failed to initialise ADS1115: {e}")
            _i2c = None
            _ads = None
            return False


def _cleanup_hardware() -> None:
    """
    Release the I2C bus on process exit.
    Registered automatically with atexit when hardware is first initialised.
    Prevents 'Device or resource busy' errors on Pi if the app is restarted.
    """
    global _i2c, _ads
    logger.info("Releasing ADS1115 I2C bus...")
    try:
        if _i2c is not None:
            _i2c.deinit()
            logger.info("ADS1115 I2C bus released cleanly")
    except Exception as e:
        logger.warning(f"ADS1115 cleanup warning: {e}")
    finally:
        _i2c = None
        _ads = None


# ---------------------------------------------------------------------------
# Channel validation
# ---------------------------------------------------------------------------
def _channel_pin(channel: int) -> int:
    """Validate and return the channel number (0-3).
    AnalogIn accepts plain integers — P0/P1/P2/P3 are just 0/1/2/3."""
    if channel not in (0, 1, 2, 3):
        raise ValueError(f"Invalid channel {channel}, must be 0-3")
    return channel


# ---------------------------------------------------------------------------
# Core read
# ---------------------------------------------------------------------------
def _read_voltage(channel: int) -> Optional[float]:
    """Read voltage from one ADS1115 channel using the shared hardware objects."""
    if not _init_hardware():
        return None
    try:
        chan = AnalogIn(_ads, _channel_pin(channel))
        voltage = chan.voltage
        logger.debug(f"ADS1115 A{channel}: {voltage:.4f}V  raw={chan.value}")
        return voltage
    except Exception as e:
        logger.error(f"Error reading ADS1115 channel {channel}: {e}")
        return None


# ---------------------------------------------------------------------------
# Scaling helpers
# ---------------------------------------------------------------------------
def _voltage_to_ma(voltage: float) -> float:
    """Convert measured voltage to milliamps using the fixed shunt resistor."""
    return voltage / SHUNT_OHMS * 1000.0


def _scale_range(current_ma: float, min_value: float, max_value: float) -> float:
    """Linear interpolation: maps 4-20mA onto [min_value, max_value], clamped."""
    ratio = (current_ma - MA_MIN) / (MA_MAX - MA_MIN)
    value = min_value + ratio * (max_value - min_value)
    return max(min_value, min(max_value, value))


def _scale_factor(current_ma: float, factor: float) -> float:
    """Direct proportional scaling: value = current_mA × factor."""
    return current_ma * factor


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def fetch_ads1115_sensors(sensors_config: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch data from enabled ADS1115 channels.

    Args:
        sensors_config: List of ads1115 sensor dicts (all 4 channels stored,
                        only ones with enabled=True are read).
    Returns:
        {param_name: {value, unit}} for each enabled channel that reads successfully.
    """
    result = {}

    for sensor in sensors_config:
        if not sensor.get('enabled', False):
            continue

        param_name = sensor.get('param_name', '').strip()
        unit       = sensor.get('unit', '')
        channel    = int(sensor.get('channel', 0))

        if not param_name:
            logger.warning(f"ADS1115 channel {channel} enabled but param_name is empty")
            continue

        voltage = _read_voltage(channel)
        if voltage is None:
            continue

        current_ma   = _voltage_to_ma(voltage)
        scale_method = sensor.get('scale_method', 'range')

        try:
            if scale_method == 'range':
                value = _scale_range(
                    current_ma,
                    float(sensor.get('min_value', 0.0)),
                    float(sensor.get('max_value', 100.0))
                )
            elif scale_method == 'factor':
                value = _scale_factor(current_ma, float(sensor.get('factor', 1.0)))
            else:
                logger.error(f"Unknown scale_method '{scale_method}' for channel {channel}")
                continue

            result[param_name] = {'value': str(round(value, 4)), 'unit': unit}
            logger.debug(f"ADS1115 A{channel} → {param_name}: {value:.4f} {unit} "
                         f"({current_ma:.3f}mA, {voltage:.4f}V)")

        except Exception as e:
            logger.error(f"Error scaling ADS1115 channel {channel} ({param_name}): {e}")

    return result
