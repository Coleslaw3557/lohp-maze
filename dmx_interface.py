import time
import logging
from pyftdi.ftdi import Ftdi
from threading import Lock

logger = logging.getLogger(__name__)

class DMXInterface:
    DMX_CHANNELS = 512
    START_CODE = 0
    BAUDRATE = 250000
    BREAK_TIME = 0.000176  # 176µs break time
    MAB_TIME = 0.000012  # 12µs mark after break
    FRAME_DELAY = 0.000001  # 1µs frame delay
    FRAME_TIME = 0.025  # Aim for 40Hz refresh rate (25ms)

    def __init__(self, url='ftdi://ftdi:232:A10NI4B7/1'):
        self.url = url
        self.port = None
        self.data = bytearray(self.DMX_CHANNELS + 1)
        self.data[0] = self.START_CODE
        self.lock = Lock()
        self.last_send_time = 0
        self.changed_channels = set()
        self._initialize_port()

    def _initialize_port(self):
        try:
            self.port = Ftdi.create_from_url(self.url)
            self.port.reset()
            self.port.set_baudrate(baudrate=self.BAUDRATE)
            self.port.set_line_property(bits=8, stopbit=2, parity='N', break_=False)
            self.port.purge_buffers()
            logger.info(f"DMX Interface initialized with URL: {self.url}")
        except Exception as e:
            logger.error(f"Failed to initialize DMX Interface: {str(e)}")
            raise

    def set_channel(self, channel, value):
        if 1 <= channel <= self.DMX_CHANNELS:
            with self.lock:
                if self.data[channel] != value:
                    self.data[channel] = value
                    self.changed_channels.add(channel)
            logger.debug(f"Set DMX channel {channel} to value {value}")
        else:
            logger.warning(f"Invalid DMX channel {channel}. Must be between 1 and {self.DMX_CHANNELS}.")

    def set_multiple_channels(self, channel_values):
        with self.lock:
            for channel, value in channel_values.items():
                if 1 <= channel <= self.DMX_CHANNELS:
                    if self.data[channel] != value:
                        self.data[channel] = value
                        self.changed_channels.add(channel)
                else:
                    logger.warning(f"Invalid DMX channel {channel}. Must be between 1 and {self.DMX_CHANNELS}.")

    def send_dmx(self):
        current_time = time.time()
        time_since_last_send = current_time - self.last_send_time
        
        if time_since_last_send < self.FRAME_TIME:
            time.sleep(self.FRAME_TIME - time_since_last_send)
        
        try:
            with self.lock:
                if self.changed_channels:
                    self.port.set_break(True)
                    time.sleep(self.BREAK_TIME)
                    self.port.set_break(False)
                    time.sleep(self.MAB_TIME)
                    self.port.write_data(self.data)
                    time.sleep(self.FRAME_DELAY)
                    self.changed_channels.clear()
                    logger.debug("DMX frame sent")
                else:
                    logger.debug("No changes, skipping DMX frame")
        except Exception as e:
            logger.error(f"Error sending DMX frame: {str(e)}", exc_info=True)
            self._handle_port_error()
        
        self.last_send_time = time.time()

    def send_dmx_with_timing(self):
        self.send_dmx()

    def _handle_port_error(self):
        if not self.port.is_open:
            logger.error("DMX port is closed. Attempting to reopen.")
            try:
                self._initialize_port()
            except Exception as e:
                logger.error(f"Failed to reopen DMX port: {str(e)}", exc_info=True)

    def close(self):
        if self.port:
            self.port.close()
            logger.info("DMX Interface closed")

    def __del__(self):
        self.close()

    def check_status(self):
        try:
            # Attempt to get the modem status
            self.port.modem_status()
            return True
        except Exception:
            return False

    def reset_all_channels(self):
        with self.lock:
            for i in range(1, self.DMX_CHANNELS + 1):
                self.data[i] = 0
        logger.info("All DMX channels reset to 0")
