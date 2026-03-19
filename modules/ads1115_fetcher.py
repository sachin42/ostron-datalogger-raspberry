"""
ADS1115 16-bit ADC fetcher for Raspberry Pi (I2C)

Fixed hardware config:
  - I2C address: 0x48 (ADDR pin → GND)
  - Gain: 1 (±4.096V range)
  - Shunt resistor: 150Ω  →  4mA=0.6V, 20mA=3.0V

Scaling methods (configured per channel):
  range  – linearly maps 4-20mA to [min_value, max_value]
  factor – value = current_mA * factor
"""
from typing import Optional, Dict, Any, List

from .constants import logger

# Fixed hardware constants
SHUNT_OHMS  = 150       # Shunt resistor in ohms
I2C_ADDRESS = 0x48      # ADDR pin → GND
GAIN        = 1         # ±4.096V range

# 4-20mA current boundaries derived from shunt
MA_MIN = 4.0
MA_MAX = 20.0
V_AT_4MA  = MA_MIN  * SHUNT_OHMS / 1000   # 0.6 V
V_AT_20MA = MA_MAX  * SHUNT_OHMS / 1000   # 3.0 V

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


def _read_voltage(channel: int) -> Optional[float]:
    """Read voltage from one ADS1115 channel (fixed address and gain)."""
    if not ADS1115_AVAILABLE:
        logger.error("ADS1115 library not available")
        return None

    channel_map = {0: ADS.P0, 1: ADS.P1, 2: ADS.P2, 3: ADS.P3}
    if channel not in channel_map:
        logger.error(f"Invalid ADS1115 channel {channel}, must be 0-3")
        return None

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=I2C_ADDRESS)
        ads.gain = GAIN
        chan = AnalogIn(ads, channel_map[channel])
        voltage = chan.voltage
        logger.debug(f"ADS1115 A{channel}: {voltage:.4f}V  raw={chan.value}")
        return voltage
    except Exception as e:
        logger.error(f"Error reading ADS1115 channel {channel}: {e}")
        return None


def _voltage_to_ma(voltage: float) -> float:
    """Convert measured voltage to milliamps using the fixed shunt resistor."""
    return voltage / SHUNT_OHMS * 1000.0


def _scale_range(current_ma: float, min_value: float, max_value: float) -> float:
    """
    Linear interpolation: maps 4-20mA onto [min_value, max_value].
    Result is clamped to the configured range.
    """
    span_ma  = MA_MAX - MA_MIN                      # 16 mA
    span_val = max_value - min_value
    ratio    = (current_ma - MA_MIN) / span_ma
    value    = min_value + ratio * span_val
    return max(min_value, min(max_value, value))    # clamp


def _scale_factor(current_ma: float, factor: float) -> float:
    """Direct proportional scaling: value = current_mA × factor."""
    return current_ma * factor


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
                min_value = float(sensor.get('min_value', 0.0))
                max_value = float(sensor.get('max_value', 100.0))
                value     = _scale_range(current_ma, min_value, max_value)
            elif scale_method == 'factor':
                factor = float(sensor.get('factor', 1.0))
                value  = _scale_factor(current_ma, factor)
            else:
                logger.error(f"Unknown scale_method '{scale_method}' for channel {channel}")
                continue

            result[param_name] = {'value': str(round(value, 4)), 'unit': unit}
            logger.debug(f"ADS1115 A{channel} → {param_name}: {value:.4f} {unit} "
                         f"({current_ma:.3f}mA, {voltage:.4f}V)")

        except Exception as e:
            logger.error(f"Error scaling ADS1115 channel {channel} ({param_name}): {e}")

    return result
