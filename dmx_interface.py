import threading
import time
import logging
from pyftdi.ftdi import Ftdi

logger = logging.getLogger(__name__)

class DMXOutputManager(threading.Thread):
    DMX_CHANNELS = 512
    START_CODE = 0
    BAUDRATE = 250000
    BREAK_TIME = 0.000176  # 176µs break time
    MAB_TIME = 0.000012  # 12µs mark after break
    FRAME_DELAY = 0.000001  # 1µs frame delay

    def __init__(self, dmx_state_manager, url='ftdi://ftdi:232:A10NI4B7/1', universe=0):
        super().__init__()
        self.dmx_state_manager = dmx_state_manager
        self.url = url
        self.universe = universe
        self.port = None
        self.running = True
        self.data = bytearray(self.DMX_CHANNELS + 1)
        self.data[0] = self.START_CODE
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

    def run(self):
        while self.running:
            self.send_dmx_data()
            time.sleep(0.025)  # 40Hz update rate

    def send_dmx_data(self):
        try:
            state = self.dmx_state_manager.get_full_state()
            self.data[1:] = state
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

    def _handle_port_error(self):
        if not self.port.is_open:
            logger.error("DMX port is closed. Attempting to reopen.")
            try:
                self._initialize_port()
            except Exception as e:
                logger.error(f"Failed to reopen DMX port: {str(e)}", exc_info=True)

    def stop(self):
        self.running = False

    def set_frequency(self, hz):
        self.frequency = hz
        logger.info(f"DMX output frequency set to {hz} Hz")

    def __del__(self):
        self.stop()
        if self.port:
            self.port.close()
            logger.info("DMX Interface closed")
