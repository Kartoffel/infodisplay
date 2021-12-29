'''
    This module handles all interfacing with the display.
    Theoretically this is the only file that should be changed
    when using a different display.
'''
import sys
import logging
from IT8951 import constants
from IT8951.display import AutoEPDDisplay

class const:
    PARTIAL             = 50
    FULL                = 51
    GREYSCALE           = 0
    GREYSCALE_NOFLASH   = 1
    MONOCHROME          = 2
    MONOCHROME_NOFLASH  = 3

# GC16: 16-level greyscale refresh with flashingblack box in between (450 ms)
# GL16: 16-level greyscale refresh without flash (450 ms)
# DU: 2-level greyscale refresh without flash (260 ms) - only works with 0x00 / 0xFF pixels

class Display:
    def __init__(self, cfg):
        self.logger = logging.getLogger(__name__)

        try:
            self.display = display = AutoEPDDisplay(
                vcom = float(cfg.get('main', 'vcom', fallback = -2.08)),
                rotate = cfg.get('main', 'rotate', fallback = 'None')
                    if cfg.get('main', 'rotate', fallback = 'None') != 'None'
                    else None,
                spi_hz = int(cfg.get('main', 'spi_hz', fallback = 24000000)))
        except Exception as e:
            self.logger.error('Unable to connect to display!')
            self.logger.error('{}'.format(e))
            sys.exit(1)

    def clear(self):
        self.display.clear();

    def clearBuf(self):
        self.display.frame_buf.paste(0xFF,
            box=(0, 0, self.display.width, self.display.height))

    def getBuf(self):
        return self.display.frame_buf.copy()

    def updateBuf(self, buf):
        self.display.frame_buf.paste(buf)

    @property
    def width(self):
        return self.display.width

    @property
    def height(self):
        return self.display.height

#    def _refresh_greyscale_full(self):
#        self.display.draw_full(constants.DisplayModes.GC16)
#
#    def _refresh_greyscale_partial(self):
#        self.display.draw_partial(constants.DisplayModes.GC16)
#
#    def _refresh_monochrome_full(self):
#        self.display.draw_full(constants.DisplayModes.DU)
#
#    def _refresh_monochrome_partial(self):
#        self.display.draw_partial(constants.DisplayModes.DU)

    def refresh(self, partial = False, greyscale = True, flash = True):
        if not greyscale:
            # Monochrome
            LUT = constants.DisplayModes.DU
            # Only black/white changes updated with DU mode

            if flash:
                # Go to white image first
                tmpBuf = self.getBuf()
                self.clearBuf()
                self.display.draw_full(LUT)
                self.updateBuf(tmpBuf)

        else:
            # Greyscale
            LUT = (constants.DisplayModes.GC16 if flash
                else constants.DisplayModes.GL16)

        if partial:
            self.display.draw_partial(LUT)
        else:
            self.display.draw_full(LUT)
        
        


