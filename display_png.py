import logging

from PIL import Image

logger = logging.getLogger(__name__)


class Display:
    def __init__(self, cfg):
        self.logger = logging.getLogger(__name__)
        self.filename = 'display.png'
        self.height = cfg.getint('main', 'height', fallback=600)
        self.width = cfg.getint('main', 'width', fallback=800)
        self.frame_buf = Image.new('L', (self.width, self.height), 0xFF)

    def clear(self):
        self.clearBuf()
        self.draw_full()

    def clearBuf(self):
        self.frame_buf.paste(0xFF, box=(0, 0, self.width, self.height))

    def getBuf(self):
        return self.frame_buf.copy()

    def updateBuf(self, buf):
        self.frame_buf.paste(buf)

    def refresh(self, partial=False, greyscale=True, flash=True):
        if not greyscale:
            if flash:
                # Go to white image first
                tmpBuf = self.getBuf()
                self.clearBuf()
                self.draw_full()
                self.updateBuf(tmpBuf)

        if partial:
            self.draw_partial()
        else:
            self.draw_full()

    def draw_partial(self):
        self.frame_buf.save(self.filename)

    def draw_full(self):
        self.frame_buf.save(self.filename)
