'''
    Calendar widget

    Uses free FontAwesome svg icons (see fontawesome.py)
'''

import logging
from PIL import Image
from widgets.textfun import Text
from widgets.fontawesome import FontAwesome
from datetime import date, datetime, timedelta

wName = 'Calendar'     

class Calendar:
    def __init__(self, cfg, width, height, pos):
        self.name   = __name__
        self.logger = logging.getLogger(self.name)

        if wName not in cfg.sections():
            self.logger.warning('No parameters in config file, using defaults.')

        # Below parameters not used by class itself but stored here
        self.width  = width
        self.height = height
        self.pos    = pos

        self.refreshInterval = int(cfg.get(wName, 'refreshInterval', fallback = 10))
        self.fastUpdate = cfg.getboolean(wName, 'fastUpdate', fallback = False)
        self.invert = cfg.getboolean(wName, 'invert', fallback = False)

        # Widget-specific parameters
        self.margin = int(cfg.get(wName, 'margin', fallback = 6))
        self.fontSize = int(cfg.get(wName, 'fontSize', fallback = 22))
        self.titleSize = int(cfg.get(wName, 'titleSize', fallback = 36))
        self.font = cfg.get(wName, 'font', fallback = 'Roboto-Regular')

        self.dateFmt = cfg.get(wName, 'dateFmt', fallback = '%A %d %b')

        self.textWidth = self.width - 2 * self.margin
        self.spacing = int(self.margin * 1.5)
        self.vertPos = 0

        # Choose and load calendar provider
        provider = cfg.get(wName, 'provider', fallback = None)
        if provider == 'Google':
            from ._calendar_google import Google
            self.provider = Google(cfg)
        elif provider == 'Demo':
            from ._calendar_demo import Demo
            self.provider = Demo(cfg)
        else:
            self.provider = None

        self.days_ahead = int(cfg.get(wName, 'daysAhead', fallback = 3))
        self.max_lines = int(cfg.get(wName, 'maxLines', fallback = 3))

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)
        # Icons
        self.fa = FontAwesome(cfg)

    def _dates_ahead(self, dt):
        today = dt.date()
        dates = []
        for i in range(self.days_ahead + 1):
            dates.append(today + timedelta(days = i))
        return dates

    def cal_list(self, title, items):
        '''
            Write a list of calendar items with a title above
        '''

        self.vertPos += self.spacing // 2

        if title:
            titleSize = self.fontSize + 2
            self.text.write(self.canvas, 
                title,
                pos = (self.margin, self.vertPos),
                font = self.font, fontsize = titleSize)
            self.vertPos += titleSize + self.spacing

        if not items:
            self.fa.paste_icon(self.canvas,
                'regular/calendar-check', self.fontSize - 2,
                (self.margin, self.vertPos + 1)
            )
            self.text.write(self.canvas, 
                'No calendar items.',
                pos = (int(self.fontSize * 1.2) + self.margin, self.vertPos),
                font = self.font, fontsize = self.fontSize)
            self.vertPos += self.fontSize + self.spacing

        for item in items:
            self.fa.paste_icon(self.canvas,
                'regular/calendar', self.fontSize - 2,
                (self.margin, self.vertPos + 1)
            )

            textPos = (int(self.fontSize * 1.2) + self.margin, self.vertPos)

            time = item['time'] if not item['all_day'] else None

            if time:
                timeBox = list(self.text.bbox(self.canvas, 
                    '{}'.format(time),
                    pos = (self.width - self.margin, self.vertPos),
                    font = self.font, fontsize = self.fontSize,
                    anchor='ra'))
                timeBox[2] = self.width

                max_width = timeBox[0] - textPos[0] - self.fontSize // 5
            else:
                max_width = self.width - self.margin - textPos[0]

            box_size = self.text.textbox(self.canvas,
                '{}'.format(item['summary']),
                max_width,
                pos = textPos,
                max_lines = self.max_lines,
                font = self.font,
                fontsize = self.fontSize,
                spacing = (self.spacing // 2)
            )

            if time:
                self.canvas.paste(0xFF, box=tuple(timeBox))

                self.text.write(self.canvas, 
                    '{}'.format(time),
                    pos = (self.width - self.margin, self.vertPos),
                    font = self.font, fontsize = self.fontSize,
                    anchor='ra')

            self.vertPos += box_size[1] + self.spacing
            if self.vertPos > (self.height - self.fontSize):
                return

    def draw(self, **kwargs):

        # Clear canvas
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        dt = kwargs.get('datetime')

        # Format date, default as 'Tuesday 14 Dec'
        dateString = dt.strftime(self.dateFmt)

        titleSize = self.titleSize

        # Decrease title size if it doesn't fit
        while titleSize > 8 and (
            self.text.size(
                self.canvas, dateString, font = self.font,
                fontsize = titleSize)[0] > self.textWidth
            ):
            self.logger.debug('Title size {} too big'.format(titleSize))
            titleSize = titleSize - 2

        self.text.write(self.canvas, 
            dateString,
            pos = (self.margin, self.margin),
            font = self.font, fontsize = titleSize, anchor = 'la')

        # Keep track of vertical position
        self.vertPos = self.margin + titleSize + self.spacing

        if not self.provider:
            self.text.textbox(self.canvas,
                'No calendar provider configured',
                self.width - 2 * self.margin,
                pos = (self.margin, self.vertPos * 2),
                font = self.font,
                fontsize = self.fontSize,
                spacing = (self.spacing // 2)
            )
            return self

        ## Start populating calendar items
        items = self.provider.get_calendar_items(dt, self.days_ahead)

        dates_ahead = self._dates_ahead(dt)

        for days, ddate in enumerate(dates_ahead):

            # Filter items by day
            items_day = [it for it in items if it['days_ahead'] == days]

            if days == 0:
                dateStr = '' #'Today'
            elif days == 1:
                dateStr = 'Tomorrow'
            else:
                dateStr = ddate.strftime('%A')

            self.cal_list(dateStr, items_day)

            if self.vertPos >= (self.height - self.fontSize - self.spacing):
                break

        return self


    def getCanvas(self):
        return self.canvas



