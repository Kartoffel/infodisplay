'''
    Rain graph
    Uses Buienalarm (NL) unofficial API to get precipitation a few hours ahead
'''
import logging
import requests
from PIL import Image
from helpers.plot import Plot
from helpers.textfun import Text
from datetime import date, datetime, timedelta, timezone

logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

wName = 'Rain'

class Rain:
    _API_URL = "https://cdn-secure.buienalarm.nl/api/3.4/forecast.php"
    # https://cdn-secure.buienalarm.nl/api/3.4/forecast.php?lat={lat}&lon={lon}&region=nl&unit=mm/u

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

        # Widget-specific parameters
        self.fontSize   = int(cfg.get(wName, 'fontSize', fallback = 22))
        self.lat        = float(cfg.get(wName, 'lat', fallback = 51.44))
        self.lon        = float(cfg.get(wName, 'lon', fallback = 5.47))

        self.timeout = 16

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)
        # Plotting
        self.plot = Plot(cfg)

    def _get_precip(self):
        '''
            Get precipitation a few hours ahead
        '''

        params = {
            'lat': str(self.lat),
            'lon': str(self.lon),
            'region': 'nl',
            'unit': 'mm/u'
        }

        try:
            r = requests.get(
                self._API_URL,
                params=params,
                timeout=self.timeout
            )
            r.raise_for_status()
        except requests.exceptions.Timeout:
            self.logger.warning("Request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            self.logger.warning("HTTP error {}".format(e))
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(e)
            return None

        try:
            data = r.json()
        except requests.exceptions.JSONDecodeError as e:
            self.logger.error("Invalid JSON: {}".format(e))
            return None

        if not data.get("success"):
            self.logger.error(
                "API request failed, reason: {}".format(data.get("reason"))
            )
            return None

        return data

        # Little test datasets:
#        #precip = [0, 0.02, 0.11, 0.08, 0.07, 0.06, 0.06, 0.03, 0.01, 0, 0, 0.1, 0.2, 0.4, 1.1, 1.5, 2.0, 5.0, 5.0, 7.0, 3.5, 1.2, 0.45, 0.2]
#        #precip = [0, 0.02, 0.11, 0.08, 0.07, 0.06, 0.06, 0.03, 0.01, 0, 0, 0.15, 0.3, 0.1, 0.1, 0.15, 0.2, 0.25, 0, 0, 0, 0, 0, 0]
#        #precip = [0, 0, 0, 0, 0, 0, 0, 0, 0]
#        levels = {'light': 0.25, 'moderate': 1, 'heavy': 2.5}
#        start = datetime(2021, 12, 31, 14, 00, 0, 0).timestamp()
#        delta = 300

    def _plot_precip(self, dt, data):
        '''
            Call 'plot' helper class to make a nice plot of precipitation.
            Expected data format:
            {
                "start": [UTC unix timestamp],
                "delta": [int, seconds between data points],
                "levels": {
                    "light": [float, mm/h],
                    "moderate": [float, mm/h],
                    "heavy": [float, mm/h]
                },
                "precip": [list of floats, mm/h]
            }
        '''

        precip  = data.get('precip')
        delta   = data.get('delta')
        levels  = data.get('levels')
        start   = data.get('start')

        # Create epoch for every point
        times = [start + i * delta for i in range(len(precip))]

        self.plot.rain(self.canvas,
            self.width - 2 * self.margin, 
            self.height,
            times, precip,
            (self.margin, 0),
            fontsize = self.fontSize,
            title = 'Precipitation',
            noRainMsg = 'No rain expected'
        )


    def draw(self, **kwargs):
        dt = kwargs.get('datetime')

        data = self._get_precip()

        if not data:
            return self

        # Clear canvas
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        self._plot_precip(dt, data)

        return self


    def getCanvas(self):
        return self.canvas
