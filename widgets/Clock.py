import logging
from PIL import Image
from helpers.textfun import Text

class Clock:
    def __init__(self, name, cfg, width, height, pos):
        self.name   = name
        self.logger = logging.getLogger(self.name)

        if self.name not in cfg.sections():
            self.logger.warning('No parameters in config file, using defaults.')

        # Below parameters not used by class itself but stored here
        self.width  = width
        self.height = height
        self.pos    = pos

        self.refreshInterval = int(cfg.get(self.name, 'refreshInterval', fallback = 1))
        self.fastUpdate = cfg.getboolean(self.name, 'fastUpdate', fallback = True)
        self.invert = cfg.getboolean(self.name, 'invert', fallback = False)

        # Parameters used by function
        self.textcolor  = int(cfg.get(self.name, 'textColor', fallback = 0))
        self.seconds    = cfg.getboolean(self.name, 'displaySeconds', fallback = True)
        self.flashColon = cfg.getboolean(self.name, 'flashColon', fallback = False)

        font    = cfg.get('main', 'font', fallback = 'Roboto-Regular')
        font2   = cfg.get(self.name, 'fontSecs', fallback = font)

        self.hhmm_size  = int(cfg.get(self.name, 'fontSize', fallback = 24))
        self.ss_size    = self.hhmm_size // 2

        self.hhmm_font  = font
        self.ss_font    = font2

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)

        # One-time computation of coordinates:
        # Get width of 00:00 clock
        hhmm_size = self.text.size(self.canvas,
            '88:88',
            font = self.hhmm_font,
            fontsize = self.hhmm_size
        )
        # Get width of (optional) seconds
        ss_size = (self.text.size(self.canvas,
            '88',
            font = self.ss_font,
            fontsize = self.ss_size
        ) if self.seconds else (0,0))

        # Get center bottom anchor for ':'
        self._center_anchor = (
            (self.width - ss_size[0]) // 2,
            (height + hhmm_size[1]) // 2
        )

        # Get left bottom anchor for 'HH'
        self._hh_anchor = (
            self._center_anchor[0] - (hhmm_size[0] // 2),
            self._center_anchor[1]
        )

        # Get right bottom anchor for 'MM'
        self._mm_anchor = (
            self._center_anchor[0] + (hhmm_size[0] // 2),
            self._center_anchor[1]
        )

        # Get left bottom anchor for 'ss'
        self._ss_anchor = (
            self._center_anchor[0] + (hhmm_size[0] // 2) + (ss_size[0] // 10),
            self._center_anchor[1]
        )

    def draw(self, **kwargs):
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        datetime    = kwargs.get('datetime')

        hours   = datetime.hour
        mins    = datetime.minute
        secs    = datetime.second

        self.text.write(self.canvas,
            '{hh:0>2d}'.format(hh = hours),
            pos = self._hh_anchor,
            font = self.hhmm_font,
            fontsize = self.hhmm_size,
            fill = self.textcolor,
            anchor='lb'
        )
        self.text.write(self.canvas,
            '{mm:0>2d}'.format(mm = mins),
            pos = self._mm_anchor,
            font = self.hhmm_font,
            fontsize = self.hhmm_size,
            fill = self.textcolor,
            anchor='rb'
        )

        if not self.flashColon or (self.sec % 2 == 0):
            self.text.write(self.canvas,
                ':',
                pos = self._center_anchor,
                font = self.hhmm_font,
                fontsize = self.hhmm_size,
                fill = self.textcolor,
                anchor='mb'
            )

        if self.seconds:
            self.text.write(self.canvas,
                '{ss:0>2d}'.format(ss = secs),
                pos = self._ss_anchor,
                font = self.ss_font,
                fontsize = self.ss_size,
                fill = self.textcolor,
                anchor='lb'
            )
        return self

    def getCanvas(self):
        return self.canvas
