'''
    Public transport widget
    Displays departure timetables for a specific stop
'''

import logging
from PIL import Image, ImageDraw
from helpers.textfun import Text
from helpers.fontawesome import FontAwesome
from datetime import date, datetime, timedelta
from math import ceil

wName = 'Transport'     

class Transport:
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
        self.invert     = cfg.getboolean(wName, 'invert', fallback = False)

        # Global parameters
        self.margin     = int(cfg.get('main', 'widgetMargin', fallback = 6))
        self.font       = cfg.get('main', 'font', fallback = 'Roboto-Regular')

        # Widget-specific parameters
        self.fontSize   = int(cfg.get(wName, 'fontSize', fallback = 22))
        self.titleSize  = int(cfg.get(wName, 'titleSize', fallback = 24))
        
        self.lineWidth  = int(cfg.get(wName, 'lineWidth', fallback = 1))
        self.lineCol    = int(cfg.get(wName, 'lineCol', fallback = 0))
        
        self.fetchInterval = int(cfg.get(wName, 'fetchInterval', fallback = 5))
        
        self.portrait   = cfg.get(wName, 'orientation', fallback = 'portrait').strip().lower() == 'portrait'
        
        self.showHeader = cfg.getboolean(wName, 'showHeader', fallback = True)
        self.showHeaderTime = cfg.getboolean(wName, 'showHeaderTime', fallback = False)
        self.showFooter = False if self.portrait else cfg.getboolean(wName, 'showFooter', fallback = False)

        self.departureMins = cfg.getboolean(wName, 'departureMins', fallback = False)
        filterText = cfg.get(wName, 'filterLineNumbers', fallback = '')
        self.filterLineNumbers = [x.strip() for x in filterText.split(',') if x]
        
       # Choose and load calendar provider
        provider = cfg.get(wName, 'provider', fallback = None)
        if provider == 'vertrektijd':
            from ._transport_vertrektijd import VertrektijdInfo
            self.provider = VertrektijdInfo(cfg)
        else:
            self.provider = None
        
        self.departureInfo = {
            'success': False,
            'timestamp': datetime(1970, 1, 1),
            'departures': []
        }

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)
        # Icons
        self.fa = FontAwesome(cfg)
        
        self._calculate_geometry()
        
        self.update_departures()
        
    def _calculate_geometry(self):
        # Calculate sizes and spacings for layout
        vertSize = self.height - 2 * self.margin
        self.footerHeight = self.fontSize + 0 * self.margin if self.showFooter else 0
        
        if self.portrait:
            self.headerHeight = self.titleSize*2 + 2 * self.margin if self.showHeader else 0
        else:
            self.headerHeight = self.titleSize + 1 * self.margin if self.showHeader else 0
        
        self.bodyHeight = vertSize - (self.headerHeight if self.showHeader else 0) - (self.footerHeight if self.showFooter else 0)
        
        self.padding = max(self.margin - 2, 0)
        if self.portrait:
            self.itemHeight = 2 * self.fontSize + self.margin + self.padding + self.lineWidth
        else:
            self.itemHeight = self.fontSize + self.padding
        
        self.numItems = self.bodyHeight // self.itemHeight
        
        self.sparePadding = (self.bodyHeight - self.numItems * self.itemHeight) // (self.numItems+1)
        
        self.logger.debug(f'Portrait orientation: {self.portrait}')
        
        self.logger.debug(f'body height: {self.bodyHeight}')
        self.logger.debug(f'item height: {self.itemHeight}')
        
        self.logger.debug(f'Fits {self.numItems} items, spare {self.sparePadding} px')

        horSize = self.width - 2 * self.margin
        self.textWidth = horSize
        if self.portrait:
            self.lineNoWidth = horSize // 2
            self.timeWidth = horSize // 2
            self.lineNameWidth = horSize
        else:
            #self.lineNoWidth = self.fontSize * 3
            #self.timeWidth = self.fontSize * 7
            w, _ = self.text.size(
                self.canvas, 'Line' if self.showFooter else '000', font = self.font,
                fontsize = self.fontSize)
            self.lineNoWidth = w + self.margin
            w, _ = self.text.size(
                self.canvas, '00 min' if self.departureMins else '20:00', font = self.font,
                fontsize = self.fontSize)
            self.timeWidth = w + self.margin
            self.lineNameWidth = horSize - 2 * self.padding - self.lineNoWidth - self.timeWidth
    
    def _get_vehicle_icon(self, vehicleType):
        # Types: Bus/Tram/Metro/Veer
        if vehicleType == 'Bus':
            return 'solid/stopwatch'
        if vehicleType == 'Tram':
            return 'solid/stopwatch'
        if vehicleType == 'Metro':
            return 'solid/stopwatch'
        if vehicleType == 'Veer':
            return 'solid/stopwatch'
        return 'solid/stopwatch'
    
    def update_departures(self):
        response = self.provider.get_departures()
        
        if response['success']:
            self.departureInfo = response
            return True
        
        return False
    
    def _get_announcement(self, dt):
        depInfo = self.departureInfo
        
        if not depInfo['success']:
            return ""
        
        for announcement in depInfo['announcements']:
            start = announcement['start_dt']
            end = announcement['end_dt']
            
            if start <= dt <= end:
                return announcement['agency'] + ": " + announcement['content']
        
        return ""
    
    def _draw_message(self, message):
        self.text.textbox(self.canvas,
                message,
                self.width - 2 * self.margin,
                pos = (self.margin, self.margin),
                font = self.font,
                fontsize = self.fontSize,
                spacing = self.margin)
    
    def _draw_header(self, dt, stopName, show_dt=True):
        # Get ImageDraw object
        draw = ImageDraw.Draw(self.canvas)
        
        headerString = f"{dt.hour:0>2d}:{dt.minute:0>2d} • " if show_dt else ""
        headerString += stopName
        
        # Draw black box
        draw.rectangle(
            [0, 0, self.width, self.headerHeight + self.margin],
            fill = 0x0)
        
        # Write header text
        self.text.textbox(self.canvas,
            headerString,
            self.width - 2 * self.margin,
            pos = (self.margin, self.margin),
            fill=0xFF,
            font = self.font,
            fontsize = self.titleSize,
            max_lines = 2 if self.portrait else 1,
            spacing = self.margin)
            # TODO: single line header for portrait as well?
    
    def _draw_footer(self, announcementText):
        # Get ImageDraw object
        draw = ImageDraw.Draw(self.canvas)
        vertPos = self.height - self.margin - self.footerHeight
        
        # Draw horizontal line
        if self.lineWidth:
            draw.line(
                [0, vertPos, self.width, vertPos],
                width = self.lineWidth,
                fill = self.lineCol)
        
        if announcementText:
            # Show announcements in footer
            self.text.write(self.canvas,
                announcementText,
                max_width = self.width - 2 * self.margin,
                pos = (self.margin, vertPos),
                font = self.font, fontsize = self.fontSize, anchor = 'la')
            return True
        else:
            # Show static footer
            self.text.write(self.canvas,
                'Line',
                pos = (self.margin, vertPos),
                font = self.font, fontsize = self.fontSize, anchor = 'la')
            
            self.text.write(self.canvas,
                'Destination',
                pos = (self.margin + self.lineNoWidth + self.padding, vertPos),
                font = self.font, fontsize = self.fontSize, anchor = 'la')
            
            self.text.write(self.canvas,
                'Time',
                pos = (self.margin + self.textWidth - self.timeWidth, vertPos),
                font = self.font, fontsize = self.fontSize, anchor = 'la')
        return False
        
    def _draw_body(self, dt, announcementText, announcementShown):
        # Get ImageDraw object
        draw = ImageDraw.Draw(self.canvas)
        # Keep track of vertical position
        vertPos = self.headerHeight + self.margin + self.sparePadding
        
        # TODO: replace time by Bus/Tram/Metro/Veer icons when imminent
        
        # Filter out departures in the past and departures not in filter
        departures = []
        
        for departure in self.departureInfo['departures']:
            if self.filterLineNumbers and departure['lineNumber'] not in self.filterLineNumbers:
                continue
        
            secondsRemaining = round((departure['expectedDeparture'] - dt) / timedelta(seconds=1))
            
            if secondsRemaining <= -60:
                continue
            
            dep = departure.copy()
            dep['secondsRemaining'] = secondsRemaining
            
            departures.append(dep)

        # Draw departures
        for i, departure in enumerate(departures):
            # Stop if screen is full, or stop one short if an announcement stillneeds to be displayed
            if i >= (self.numItems-1 if announcementText and not announcementShown else self.numItems):
                break
            
            if self.departureMins:
                # Show time until expected departure in minutes
                minsRemaining = ceil(departure['secondsRemaining']/60)
                formattedTime = f"{minsRemaining} min"
            else:
                # Show time of expected departure (hh:mm)
                formattedTime = departure['expectedDepartureTime']
                
            departureImminent = departure['secondsRemaining'] <= 0
            
            if self.portrait:
                # Draw a horizontal line after every entry
                if self.lineWidth and i > 0:
                    vp = vertPos - self.padding//2
                    draw.line(
                        [self.margin, vp, self.width-self.margin, vp],
                        width = self.lineWidth,
                        fill = self.lineCol)
                
                # Write departure time
                if self.departureMins and departureImminent:
                    # Vehicle is departing any moment, show icon instead of time
                    icon = self._get_vehicle_icon(departure['type'])
                    self.fa.paste_icon(self.canvas,
                        icon, self.fontSize - 2,
                        (self.margin, vertPos + 3)
                    )
                else:
                    self.text.write(self.canvas, 
                        formattedTime,
                        pos = (self.margin, vertPos),
                        font = self.font, fontsize = self.fontSize, anchor = 'la') 
                
                # Write vehicle type and line number
                self.text.write(self.canvas, 
                    f"{departure['type']} {departure['lineNumber']}",
                    pos = (self.width - self.margin, vertPos),
                    font = self.font, fontsize = self.fontSize, anchor = 'ra')
                
                # Write destination name
                self.text.write(self.canvas,
                    departure['name'],
                    max_width = self.width - 2 * self.margin,
                    pos = (self.margin, vertPos + self.fontSize + self.margin),
                    font = self.font,
                    fontsize = self.fontSize)
                
            else:
                # Write line number
                self.text.write(self.canvas, 
                    departure['lineNumber'],
                    pos = (self.margin, vertPos),
                    font = self.font, fontsize = self.fontSize, anchor = 'la')
                
                # Write destination name
                self.text.write(self.canvas,
                    departure['name'],
                    max_width = self.lineNameWidth,
                    pos = (self.margin + self.lineNoWidth + self.padding, vertPos),
                    font = self.font, fontsize = self.fontSize, anchor = 'la')
                
                # Write departure time
                if self.departureMins and departureImminent:
                    # Vehicle is departing any moment, show icon instead of time
                    icon = self._get_vehicle_icon(departure['type'])
                    self.fa.paste_icon(self.canvas,
                        'solid/stopwatch', self.fontSize - 2,
                        (self.margin + self.textWidth - self.timeWidth//2 - self.fontSize//2, vertPos + 3)
                    )
                else:
                    self.text.write(self.canvas,
                        formattedTime,
                        pos = (self.margin + self.textWidth - self.timeWidth, vertPos),
                        font = self.font, fontsize = self.fontSize, anchor = 'la')
                
            vertPos += self.itemHeight + self.sparePadding
        
        # Write announcement as last entry (if available)
        if announcementText and not announcementShown:
            # Draw horizontal line
            if self.portrait and self.lineWidth:
                vp = vertPos - self.padding//2
                draw.line(
                    [self.margin, vp, self.width-self.margin, vp],
                    width = self.lineWidth,
                    fill = self.lineCol)
            # Write announcement text
            self.text.textbox(self.canvas,
                announcementText,
                self.width - 2 * self.margin,
                pos = (self.margin, vertPos),
                font = self.font,
                fontsize = self.fontSize,
                max_lines = 2 if self.portrait else 1,
                spacing = self.margin)

    def draw(self, **kwargs):
        # Clear canvas
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        dt = kwargs.get('datetime')
        
        if not self.provider:
            self._draw_message("No transport provider configured")
            return self
        
        if dt.minute % self.fetchInterval == 0:
            self.update_departures()
        
        depInfo = self.departureInfo
        
        age_minutes = (dt - depInfo['timestamp']) / timedelta(minutes = 1)
        
        if (not depInfo['success']) or age_minutes > 120:
            msg = "No current data (last successful fetch: "
            if not depInfo['success']:
                msg += "never)"
            elif age_minutes < 1440:
                msg += f"{int(age_minutes/60)} hours ago)"
            else:
                msg += f"{int(age_minutes/1440)} days ago)"
            self._draw_message(msg)
            return self

        announcementText = self._get_announcement(dt)
        announcementShown = False
        
        stopName = depInfo['stopName']
        
        # Draw header
        if self.showHeader:
            self._draw_header(dt, stopName, self.showHeaderTime)
        
        # Draw footer
        if self.showFooter:
            announcementShown = self._draw_footer(announcementText)
        
        # Draw departures
        self._draw_body(dt, announcementText, announcementShown)

        return self


    def getCanvas(self):
        return self.canvas
