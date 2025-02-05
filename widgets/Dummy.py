'''
    Dummy widget to show bare-bone structure
'''
import logging
from PIL import Image
from helpers.textfun import Text

class Dummy:
    def __init__(self, name, cfg, width, height, pos):
        self.name   = name
        self.logger = logging.getLogger(self.name)

        self.logger.info('Hello!')

        if self.name not in cfg.sections():
            self.logger.warning('No parameters in config file, using defaults.')

        # Below parameters not used by class itself but stored here
        self.width  = width
        self.height = height
        self.pos    = pos

        self.refreshInterval = int(cfg.get(self.name, 'refreshInterval', fallback = 10))
        self.fastUpdate = cfg.getboolean(self.name, 'fastUpdate', fallback = False)
        self.invert     = cfg.getboolean(self.name, 'invert', fallback = False)

        # Global parameters
        self.margin     = int(cfg.get('main', 'widgetMargin', fallback = 6))
        self.font       = cfg.get('main', 'font', fallback = 'Roboto-Regular')

        # Widget-specific parameters
        self.dummyParam = int(cfg.get(self.name, 'dummyParam', fallback = 42))

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)

    def draw(self, **kwargs):
        '''
            Widget drawing function, this is called by the scheduler to redraw the widget.
            Make sure this function has a timeout so it does not take longer than 10 or so seconds!

            Optional keyword arguments:
            datetime: `datetime` object for time that the widget will be drawn on screen.
        '''
        # Clear canvas
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        datetime    = kwargs.get('datetime')

        hours   = datetime.hour
        mins    = datetime.minute
        secs    = datetime.second

        # Drawing functions go here
        self.text.centered(self.canvas,
            self.name,
            font = self.font,
            fontsize = 40, 
            offset = (0, -20)
        )

        self.text.centered(self.canvas,
            '{:0>2d}:{:0>2d}:{:0>2d}'.format(hours, mins, secs),
            font = self.font,
            fontsize = 24, 
            offset = (0, 20)
        )

        # Leave this in! Widgets should always return themselves when finished drawing
        return self


    def getCanvas(self):
        return self.canvas

    def cleanup(self):
        # Add code that runs before the display is shut down here (e.g. saving a state)
        self.logger.info('Cleaning up!')
        return
