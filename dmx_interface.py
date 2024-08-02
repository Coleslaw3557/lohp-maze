import time
import logging
import threading
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

    def __init__(self, url='ftdi://ftdi:232:A10NI4B7/1', frequency=40):
        self.url = url
        self.port = None
        self.data = bytearray(self.DMX_CHANNELS + 1)
        self.data[0] = self.START_CODE
        self.lock = Lock()
        self.last_send_time = 0
        self.set_frequency(frequency)
        self._initialize_port()
        self.dmx_thread = threading.Thread(target=self._dmx_send_loop, daemon=True)
        self.dmx_thread.start()

    def set_frequency(self, frequency):
        self.frequency = frequency
        self.FRAME_TIME = 1 / frequency

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
                self.data[channel] = value
            logger.debug(f"Set DMX channel {channel} to value {value}")
        else:
            logger.warning(f"Invalid DMX channel {channel}. Must be between 1 and {self.DMX_CHANNELS}.")

    def set_multiple_channels(self, channel_values):
        with self.lock:
            for channel, value in channel_values.items():
                if 1 <= channel <= self.DMX_CHANNELS:
                    self.data[channel] = value
                else:
                    logger.warning(f"Invalid DMX channel {channel}. Must be between 1 and {self.DMX_CHANNELS}.")

    def _dmx_send_loop(self):
        while True:
            self._send_dmx_frame()
            time.sleep(self.FRAME_TIME)

    def _send_dmx_frame(self):
        try:
            with self.lock:
                self.port.set_break(True)
                time.sleep(self.BREAK_TIME)
                self.port.set_break(False)
                time.sleep(self.MAB_TIME)
                self.port.write_data(self.data)
                time.sleep(self.FRAME_DELAY)
            logger.debug("DMX frame sent")
        except Exception as e:
            logger.error(f"Error sending DMX frame: {str(e)}", exc_info=True)
            self._handle_port_error()

    def send_dmx(self):
        # This method is now a no-op as sending is handled by the _dmx_send_loop
        pass

    def send_dmx_with_timing(self):
        # This method is now a no-op as sending is handled by the _dmx_send_loop
        pass

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
