'''
    Weather widget

    Many thanks to Milan Damen for the inspiration and base of the parser
    https://github.com/milandamen/WeatherSiteParser

    First couple of functions are for getting and parsing the Weerplaza site.
    `_draw_forecast` is the big long function that draws everything onto the canvas.

    General layout:

    First row (current weather):

                            Feels like x°C      [arrow]  x Bft
    [icon]  Temperature     [drop]    x mm      [gauge]  x hPa
                            [sunrise] hh:mm     [sunset] hh:mm

    Second row (hourly forecast):

    hh:mm   |   hh:mm   |   hh:mm   | (...)
    [icon]  |   [icon]  |   [icon]  |
     x°C    |   x°C     |   x°C     |
     x mm   |   x mm    |   x mm    |
    [wind]  |   [wind]  |   [wind]  |

    Third row (daily forecast):

    [Weekday]   [icon]  [temp] x°C to y°C   [drop] xx%, y mm    [arrow] x Bft
    -------------------------------------------------------------------------
    [Weekday]   [icon]  [temp] x°C to y°C   [drop] xx%, y mm    [arrow] x Bft
    -------------------------------------------------------------------------
    (...)

'''
import re
import logging
import requests
from PIL import Image, ImageDraw
from lxml.html import fromstring
from helpers.textfun import Text
from helpers.fontawesome import FontAwesome
from datetime import date, datetime, timedelta

logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

wName = 'Weather'

class Weather:
    _API_URL = "https://www.weerplaza.nl/"
    # e.g. https://www.weerplaza.nl/nederland/eindhoven/9020/

    _weekdays = ["ma", "di", "wo", "do", "vr", "za", "zo"]
    _wind_dir = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW",
        "SW", "WSW", "W", "WNW", "NW", "NNW"]

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
        self.lineWidth  = int(cfg.get(wName, 'lineWidth', fallback = 1))
        self.lineCol    = int(cfg.get(wName, 'lineCol', fallback = 0))
        self.locationID = cfg.get(wName, 'locationID',
            fallback = 'nederland/eindhoven/9020/')
        self.numHours   = int(cfg.get(wName, 'hours', fallback = 48))
        self.numDays    = int(cfg.get(wName, 'days', fallback = 7))

        self.timeout      = 16

        # Horizontal and vertical spacing between elements
        self.spacing      = 10
        self.vert_spacing = 20

        self.row_heights = [
            self.height // 5,
            2 * self.height // 5 - self.margin - self.vert_spacing,
            2 * self.height // 5 - self.margin - self.vert_spacing
        ]

        self.dt = None

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)
        # Icons
        self.fa = FontAwesome(cfg)

    def _get_page(self):
        '''
            Get content of Weerplaza page
        '''
        url = '{}{}'.format(self._API_URL, self.locationID)
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
        }

        try:
            r = requests.get(
                url,
                headers = headers,
                timeout = self.timeout
            )
            r.raise_for_status()
        except requests.exceptions.Timeout:
            self.logger.warning("Request timed out")
        except requests.exceptions.HTTPError as e:
            self.logger.warning("HTTP error {}".format(e))
        except requests.exceptions.RequestException as e:
            self.logger.error(e)
        else:
            return r.text

        return None

    def _parse_now(self, root):
        '''
            Parse current weather information
        '''
        now = {
            "id": None,             # 'weather ID' svg name
            "temperature": None,    # Temperature [°C]
            "rain": None,           # Precipitation [mm]
            "wind": {
                "direction": None,  # Cardinal direction
                "speed": None       # Wind speed (Bft)
            },
            "pressure": None,       # Barometric pressure [hPa]
            "humidity": None,       # Relative humidity [%]
            "sun": {
                "rise": None,       # Sunrise time [H:M]
                "set": None         # Sunset time [H:M]
            },
            "moon": {
                "rise": None,       # Moonrise time [H:M]
                "set": None         # Moonset time [H:M]
            }
        }

        # Get div with current weather
        div = root.cssselect(".row .weather")

        if not div:
            return now

        # First div: weather icon and temperature
        id_tmp = div[0].getchildren()[0]

        iconStyle = id_tmp.cssselect(".wx")[0].attrib["style"]
        iconRegex = re.search("background-image: url\('.+\/(.+).svg'\)", iconStyle)
        if iconRegex:
            now["id"] = iconRegex.group(1)

        tempText = id_tmp.cssselect(".temp")[0].text
        tempRegex = re.search("(-?\d+) *°", tempText)
        if tempRegex:
            now["temperature"] = int(tempRegex.group(1))

        # Second div: summary of other params
        summary = div[0].getchildren()[1]
        params = ['rain', 'wind', 'pressure', 'humidity']
        for param in params:
            text = summary.cssselect(".{}".format(param))[0].getchildren()[0].text

            if param == 'rain':
                rainRegex = re.search("(\d+[,.]\d+|\d+)", text)
                if rainRegex:
                    now["rain"] = float(rainRegex.group(1).replace(',', '.'))

            elif param == 'wind':
                windRegex = re.search("([A-Z]+) (\d+)", text)
                if windRegex:
                    now["wind"]["direction"] = self._trns_wind_dir(
                        windRegex.group(1))
                    now["wind"]["speed"] = int(windRegex.group(2))
                
            elif param == 'pressure':
                presRegex = re.search("(\d+[,.]\d+|\d+) hPa", text)
                if presRegex:
                    now["pressure"] = float(presRegex.group(1).replace(',', '.'))
                
            elif param == 'humidity':
                humRegex = re.search("(\d+[,.]\d+|\d+)%", text)
                if humRegex:
                    now["humidity"] = int(humRegex.group(1).replace(',', '.'))

        # Get div with astrological information
        div = root.cssselect(".forecast-astro")
        if not div:
            return now

        rows = div[0].getchildren()[0].cssselect(".box")[0].cssselect(".row")

        timeRegex = "(\d{2}:\d{2})"

        # Row 0: sun
        sunrise = rows[0].getchildren()[0].cssselect("span")[0].text_content()
        sunset  = rows[0].getchildren()[1].cssselect("span")[0].text_content()

        # Row 1: moon
        moonrise = rows[1].getchildren()[0].cssselect("span")[0].text_content()
        moonset  = rows[1].getchildren()[1].cssselect("span")[0].text_content()

        sunrise = re.search(timeRegex, sunrise)
        if sunrise:
            now["sun"]["rise"] = sunrise.group(1)

        sunset = re.search(timeRegex, sunset)
        if sunset:
            now["sun"]["set"] = sunset.group(1)

        moonrise = re.search(timeRegex, moonrise)
        if moonrise:
            now["moon"]["rise"] = moonrise.group(1)

        moonset = re.search(timeRegex, moonset)
        if moonset:
            now["moon"]["set"] = moonset.group(1)

        return now

    def _parse_48h(self, root):
        '''
            Parse hourly forecast for the next 48 hours
        '''
        hourly = []

        # Get div with 48 hour prediction
        div = root.cssselect(".forecast-hourly .content table")
        if not div:
            return hourly

        table = div[0]
        tbody = table.getchildren()[0]

        # First row: datetimes and weather icon ID
        row = tbody.getchildren()[0]
        for td in row.getchildren():
            if len(hourly) >= self.numHours:
                break

            # Set up format
            hourly.append({
                "datetime": None,       # Datetime object
                "date": None,           # Formatted date [Y-m-d]
                "time": None,           # Formatted time [H:M]
                "id": None,             # 'weather ID' svg name
                "temperature": {
                    "max": None,        # Max. temperature [°C]
                    "chill": None       # Wind chill [°C]
                },    
                "rain": {
                    "amount": None      # Precipitation [mm]
                },
                "wind": {
                    "direction": None,  # Cardinal direction
                    "speed": None       # Wind speed (Bft)
                }
            })

            d = hourly[-1]

            # Weekday and time
            day     = td.getchildren()[0].getchildren()[0].text.strip()
            time    = td.getchildren()[0].getchildren()[1].text.split(":")

            dayIndex= self._weekdays.index(day)
            now     = self.dt

            # Get the correct datetime for the target day
            if now.weekday() == dayIndex:
                destDay = now
            elif dayIndex > now.weekday():
                destDay = now + timedelta(days=(dayIndex - now.weekday()))
            else:
                destDay = now + timedelta(days=(7-(now.weekday() - dayIndex)))

            destDay = destDay.replace(
                hour = int(time[0]),
                minute = int(time[1]),
                second = 0, microsecond = 0
            )

            d["datetime"] = destDay
            d["date"] = destDay.strftime("%Y-%m-%d")
            d["time"] = destDay.strftime("%H:%M")

            # Weather icon
            weatherStyle = td.cssselect(".wx")[0].attrib["style"]
            weatherRegex = re.search(
                "background-image: url\('.+\/(.+).svg'\)",
                weatherStyle
            )
            if weatherRegex:
                d["id"] = weatherRegex.group(1)

        # Second row: max temperature
        row = tbody.getchildren()[1]
        for i in range(len(hourly)):
            td = row[i]

            tempText = td.cssselect("div.red.temp")[0].text
            tempRegex = re.search("(-?\d+) *°C", tempText)

            if tempRegex:
                hourly[i]["temperature"]["max"] = int(tempRegex.group(1))

        # Third row: wind chill
        row = tbody.getchildren()[2]
        # Graph part is two columns, only select first one which has tooltip
        col1 = row.cssselect(".graph-col1")
        for i in range(len(hourly)):
            td = col1[i]

            tooltip = td.cssselect(".tooltip")[0]
            chillText = tooltip.getchildren()[0].cssselect("span")[0].text

            tempRegex = re.search("(-?\d+) *°C", chillText)
            if tempRegex:
                hourly[i]["temperature"]["chill"] = int(tempRegex.group(1))

        # Fourth row: precipitation
        row = tbody.getchildren()[3]
        for i in range(len(hourly)):
            td = row[i]

            rainAmount = td.getchildren()[0].text
            rainRegex = re.search("(\d+[,.]\d+|\d+)", rainAmount)

            if rainRegex:
                hourly[i]["rain"]["amount"] = float(
                    rainRegex.group(1).replace(',', '.')
                )

        # Sixth row: wind direction and speed
        row = tbody.getchildren()[5]
        for i in range(len(hourly)):
            td = row[i]

            windDescription = td.getchildren()[0].text
            windRegex = re.search("([A-Z]+) (\d+)", windDescription)

            if windRegex:
                hourly[i]["wind"]["direction"] = self._trns_wind_dir(
                    windRegex.group(1))
                hourly[i]["wind"]["speed"] = int(windRegex.group(2))

        return hourly

    def _parse_7d(self, root):
        '''
            Parse daily forecast for the next 7 days
        '''

        daily = []

        # Get div with 7 day prediction
        div = root.cssselect(".forecast-fullday .content")
        if not div:
            return daily

        table_7d = div[0].cssselect("table")[0]

        tbody = table_7d.getchildren()[0]

        # First row: date, rating, weather icon ID
        row = tbody.getchildren()[0]
        for td in row.getchildren():
            if len(daily) >= self.numDays:
                break

            # Set up format
            daily.append({
                "datetime": None,       # Datetime object
                "date": None,           # Formatted date [Y-m-d]
                "id": None,             # 'weather ID' svg name
                "rating": None,         # Weather rating [1-10]
                "sun": {
                    "chance": None,     # Chance of sun [%]
                    "uv": None          # UV index
                },
                "temperature": {
                    "max": None,        # Max. temperature [°C]
                    "min": None         # Min. temperature [°C]
                },    
                "rain": {
                    "chance": None,     # Chance of rain [%]
                    "amount": None      # Precipitation [mm]
                },
                "wind": {
                    "direction": None,  # Cardinal direction
                    "speed": None       # Wind speed (Bft)
                }
            })

            d = daily[-1]

            ddate = td.attrib["data-day"] # Day (DDMMYY)

            d["datetime"] = datetime.strptime(ddate, '%d%m%Y').date()
            d["date"] = d["datetime"].strftime("%Y-%m-%d")

            d["rating"] = int(td.cssselect(".weather-rating")[0].text)

            weatherStyle = td.cssselect(".wx")[0].attrib["style"]
            weatherRegex = re.search(
                "background-image: url\('.+\/(.+).svg'\)",
                weatherStyle
            )
            if weatherRegex:
                d["id"] = weatherRegex.group(1)

        # Second row: sun
        row = tbody.getchildren()[1]
        for i in range(len(daily)):
            td = row[i]

            sunChance = td.getchildren()[0].text_content()
            sunChanceRegex = re.search(
                "(\d+[,.]\d+|\d+)%",
                sunChance
            )
            if sunChanceRegex:
                daily[i]["sun"]["chance"] = int(sunChanceRegex.group(1))

            uv = int(td.getchildren()[1].getchildren()[1].text)
            daily[i]["sun"]["uv"] = uv

        # Fourth row: temperatures
        row = tbody.getchildren()[3]
        for i in range(len(daily)):
            td = row[i]

            temp_max = td.cssselect("div.red.temp")[0].text
            temp_min = td.cssselect("div.blue.temp")[0].text

            tempRegex = "(-?\d+) *°C"

            res = re.search(tempRegex, temp_max)
            if res:
                daily[i]["temperature"]["max"] = int(res.group(1))

            res = re.search(tempRegex, temp_min)
            if res:
                daily[i]["temperature"]["min"] = int(res.group(1))

        # Sixth row: rain
        row = tbody.getchildren()[5]
        for i in range(len(daily)):
            td = row[i]

            rainChance = td.getchildren()[0].text_content()
            rainAmount = td.getchildren()[1].text_content()

            chanceRegex = re.search("(\d+[,.]\d+|\d+)%", rainChance)
            if chanceRegex:
                daily[i]["rain"]["chance"] = int(chanceRegex.group(1))

            rainRegex = re.search("(\d+[,.]\d+|\d+)", rainAmount)
            if rainRegex:
                daily[i]["rain"]["amount"] = float(
                    rainRegex.group(1).replace(',', '.')
                )

        # Eigth row: wind
        row = tbody.getchildren()[7]
        for i in range(len(daily)):
            td = row[i]

            windDescription = td.getchildren()[0].text
            windRegex = re.search("([A-Z]+) (\d+)", windDescription)

            if windRegex:
                daily[i]["wind"]["direction"] = self._trns_wind_dir(
                    windRegex.group(1))
                daily[i]["wind"]["speed"] = int(windRegex.group(2))

        return daily

    def _parse_page(self, text):
        '''
            Parse Weerplaza page
        '''
        root = fromstring(text)

        try:
            now = self._parse_now(root)
        except Exception as e:
            self.logger.error("Error parsing current weather")
            self.logger.error(e)
            now = None

        try:
            forecast_48h = self._parse_48h(root)
        except Exception as e:
            self.logger.error("Error parsing 48h forecast")
            self.logger.error(e)
            forecast_48h = []

        try:
            forecast_7d = self._parse_7d(root)
        except Exception as e:
            self.logger.error("Error parsing 7d forecast")
            self.logger.error(e)
            forecast_7d = []

        weather = {
            "now": now,
            "48h": forecast_48h,
            "7d":  forecast_7d
        }

        success = not any([val == None for val in weather.values()])

        return weather if success else None



    def _draw_forecast(self, weather):

        draw = ImageDraw.Draw(self.canvas)

        ### First row: current weather ###
        now = weather["now"]
        hor_pos = self.margin
        vert_pos = self.margin * 2
        height = self.row_heights[0]

        # Weather icon
        icon = self._icon_to_fontawesome(now['id'])
        self.fa.paste_icon(self.canvas, icon, size = height - 8,
            pos = (hor_pos + 4, vert_pos + 4)
        )

        # Big temperature
        hor_pos += height + self.spacing
        temp_text = '{}°'.format(now['temperature'])

        width, _ = self.text.size(self.canvas,
            temp_text,
            font = self.font,
            fontsize = height
        )

        self.text.write(self.canvas,
            temp_text,
            pos = (hor_pos, vert_pos + height // 2),
            font = self.font,
            fontsize = height,
            anchor = 'lm'
        )

        hor_pos += width + int(self.spacing * 2)
        table_start = hor_pos

        width_remain = self.width - table_start - self.margin

        # Vertical spacing between elements
        vert_spacing_mini = 4
        row_height = (height - 2 * vert_spacing_mini) // 3

        # Minitable row 1/3: wind chill, [wind] wind
        if weather["48h"]:
            chillTemp = weather["48h"][0]["temperature"]["chill"]
            chillText = 'Feels like {}°C'.format(chillTemp)
            textwidth, _ = self.text.size(self.canvas,
                chillText,
                font = self.font,
                fontsize = row_height + 2
            )
            self.text.write(self.canvas,
                chillText,
                pos = (hor_pos, vert_pos + row_height // 2),
                font = self.font,
                fontsize = row_height + 2,
                anchor = 'lm'
            )
            hor_pos += width_remain // 2

        self._draw_windvane(
            now["wind"]["direction"],
            row_height - 4,
            pos = (hor_pos, vert_pos + 2)
        )
        hor_pos += row_height + self.spacing // 2
        self.text.write(self.canvas,
            '{} Bft'.format(now["wind"]["speed"]),
            pos = (hor_pos, vert_pos + row_height // 2),
            font = self.font,
            fontsize = row_height + 2,
            anchor = 'lm'
        )

        hor_pos = table_start
        vert_pos += row_height + vert_spacing_mini

        # Minitable row 2/3: [tint] rain, [tachometer-alt] pressure

        self.fa.paste_icon(self.canvas,
            'solid/tint',
            size = row_height - 4,
            pos = (hor_pos, vert_pos + 2)
        )
        hor_pos += row_height + self.spacing // 2
        text = '{} mm'.format(self._format_rain(now["rain"]))
        self.text.write(self.canvas,
            text,
            pos = (hor_pos, vert_pos + row_height // 2),
            font = self.font,
            fontsize = row_height + 2,
            anchor = 'lm'
        )

        hor_pos = table_start + width_remain // 2

        self.fa.paste_icon(self.canvas,
            'solid/tachometer-alt',
            size = row_height,
            pos = (hor_pos - 2, vert_pos + 1)
        )
        hor_pos += row_height + self.spacing // 2
        self.text.write(self.canvas,
            '{} hPa'.format(now["pressure"]),
            pos = (hor_pos, vert_pos + row_height // 2),
            font = self.font,
            fontsize = row_height + 2,
            anchor = 'lm'
        )

        hor_pos = table_start
        vert_pos += row_height + vert_spacing_mini

        # Minitable row 3/3: sunrise, sunset
        self.fa.paste_icon(self.canvas,
            'sunrise2',
            size = row_height + 2,
            pos = (hor_pos - 4, vert_pos - 1)
        )
        hor_pos += row_height + self.spacing // 2
        self.text.write(self.canvas,
            now["sun"]["rise"],
            pos = (hor_pos, vert_pos + row_height // 2),
            font = self.font,
            fontsize = row_height + 2,
            anchor = 'lm'
        )

        hor_pos = table_start + width_remain // 2

        self.fa.paste_icon(self.canvas,
            'sunset2',
            size = row_height + 2,
            pos = (hor_pos - 4, vert_pos + 1)
        )
        hor_pos += row_height + self.spacing // 2
        self.text.write(self.canvas,
            now["sun"]["set"],
            pos = (hor_pos, vert_pos + row_height // 2),
            font = self.font,
            fontsize = row_height + 2,
            anchor = 'lm'
        )


        ### Second row: hourly forecast ###

        forecast_48h = weather["48h"]

        vert_pos = self.margin * 2 + self.row_heights[0] + self.vert_spacing
        hor_pos = self.margin
        height = self.row_heights[1]

        # Vertical spacing between elements
        vert_spacing_mini = 4
        icon_size = 24

        # Height of text elements
        element_height = (height - (vert_spacing_mini * 4 + icon_size)) // 4

        num_hours = len(forecast_48h)
        if num_hours > 0:
            hour_width = (self.width - 2 * self.margin) // num_hours

        # Vertical: time, icon, temperature, precip, wind
        for hour in forecast_48h:
            yy = vert_pos

            # Time
            self.text.write(self.canvas,
                hour["time"],
                pos = (hor_pos + hour_width // 2, yy),
                font = self.font,
                fontsize = element_height,
                anchor = 'mt'
            )
            yy += element_height + vert_spacing_mini

            # Icon
            icon = self._icon_to_fontawesome(hour["id"])
            self.fa.paste_icon(self.canvas, 
                icon,
                size = icon_size,
                pos = (hor_pos + (hour_width - icon_size) // 2, yy)
            )
            yy += icon_size + vert_spacing_mini + 2

            # Temperature, Rain

            items = [
                '{}°C'.format(hour["temperature"]["max"]),
                '{} mm'.format(self._format_rain(hour["rain"]["amount"]))
            ]

            for item in items:
                self.text.write(self.canvas,
                    item,
                    pos = (hor_pos + hour_width // 2, yy),
                    font = self.font,
                    fontsize = element_height - 2,
                    anchor = 'ma'
                )
                yy += element_height + vert_spacing_mini

            # Wind
            yy += 2
            self._draw_windvane(
                hour["wind"]["direction"],
                element_height - 2,
                pos = (
                    hor_pos + hour_width // 2 - element_height,
                    yy
                )
            )
            yy += (element_height - 2) // 2
            self.text.write(self.canvas,
                '{}'.format(hour["wind"]["speed"]),
                pos = (hor_pos + hour_width // 2 + 2, yy),
                font = self.font,
                fontsize = element_height - 2,
                anchor = 'lm'
            )

            hor_pos += hour_width

            if hour != forecast_48h[-1]: #don't draw line to right
                draw.line(
                    [hor_pos, vert_pos, hor_pos, vert_pos + height],
                    width = self.lineWidth,
                    fill = self.lineCol
                )

        forecast_7d = weather["7d"]

        vert_pos = (self.margin * 2 + self.row_heights[0] +
            self.row_heights[1] + 2 * self.vert_spacing)
        height = self.row_heights[2]

        # Vertical spacing between elements
        vert_spacing_mini = 4

        num_days = len(forecast_7d)
        if num_days > 0:
            day_height = height // num_days

        icon_size = day_height - 2 * vert_spacing_mini - 2
        text_size = icon_size - 4

        smalltext_size = text_size - 6
        smallicon_size = icon_size - 4

        dayname_width, _ = self.text.size(self.canvas,
            'Wed:', font = self.font, fontsize = text_size
        )

        # Width of last three elements
        element_width = (self.width - 3 * self.spacing - dayname_width - 4 * self.spacing) // 3

        # Vertical: time, icon, temperature, precip, wind
        for day in forecast_7d:
            xx = self.spacing

            # Get y position of center
            center_height = vert_pos + day_height // 2

            # Name of day, abbreviated (Mon .. Sun)
            self.text.write(self.canvas,
                day["datetime"].strftime('%a'),
                pos = (xx, center_height),
                font = self.font,
                fontsize = text_size,
                anchor = 'lm'
            )
            xx += dayname_width + self.spacing

            # Icon
            icon = self._icon_to_fontawesome(day["id"])
            self.fa.paste_icon(self.canvas, 
                icon,
                size = icon_size,
                pos = (xx, center_height - icon_size // 2)
            )
            xx += icon_size + 2 * self.spacing

            # Temperature
            self.fa.paste_icon(self.canvas, 
                'solid/thermometer-half',
                size = smallicon_size,
                pos = (xx, center_height - smallicon_size // 2)
            )
            
            self.text.write(self.canvas,
                '{}°C to {}°C'.format(
                    day["temperature"]["min"],
                    day["temperature"]["max"]
                ),
                pos = (xx + smallicon_size, center_height),
                font = self.font,
                fontsize = smalltext_size,
                anchor = 'lm'
            )

            xx += element_width

            # Rain
            self.fa.paste_icon(self.canvas, 
                'solid/tint',
                size = smallicon_size,
                pos = (xx, center_height - smallicon_size // 2)
            )
            
            self.text.write(self.canvas,
                '{}%, {} mm'.format(
                    day["rain"]["chance"],
                    self._format_rain(day["rain"]["amount"])
                ),
                pos = (xx + smallicon_size + 4, center_height),
                font = self.font,
                fontsize = smalltext_size,
                anchor = 'lm'
            )

            xx += 5 * element_width // 4

            self._draw_windvane(
                day["wind"]["direction"],
                smallicon_size - 2,
                pos = (xx, center_height - smallicon_size // 2 + 1)
            )

            self.text.write(self.canvas,
                '{} Bft'.format(day["wind"]["speed"]),
                pos = (xx + smallicon_size + 4, center_height),
                font = self.font,
                fontsize = smalltext_size,
                anchor = 'lm'
            )


            vert_pos += day_height

            if day != forecast_7d[-1]: #don't draw line after last item
                draw.line([
                        self.spacing * 2,
                        vert_pos, 
                        self.width - 2 * self.spacing,
                        vert_pos
                    ],
                    width = self.lineWidth,
                    fill = self.lineCol
                )



    def draw(self, **kwargs):

        self.dt = kwargs.get('datetime')

        text = self._get_page()

        if not text:
            return self        

        weather = self._parse_page(text)

        if weather:
            # Clear canvas
            self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

            self._draw_forecast(weather)

        return self


    def getCanvas(self):
        return self.canvas

    def _draw_windvane(self, direction, size, pos = (0,0)):

        icon = self.fa.get_icon('arrow', size=size)
        angle = self._direction_to_angle(direction) - 180

        if icon:
            icon = icon.rotate(
                angle = -angle, # argument is counter-clockwise
                fillcolor = 255
            )
            box = (
                pos[0], pos[1],
                pos[0] + size, pos[1] + size
            )
            self.canvas.paste(icon, box)

    def _direction_to_angle(self, direction):
        '''
            Convert cardinal wind direction (e.g. 'N' or 'WSW') to degrees
        '''

        try:
            index = self._wind_dir.index(direction)
        except ValueError:
            return 0.0

        increment = 360.0 / len(self._wind_dir)
        return round(index * increment)

    @staticmethod
    def _format_rain(precip):
        '''
            Format precipitation as .1f, remove trailing zeros
        '''
        float_string = '{:.1f}'.format(precip)
        if float_string[-2:] == '.0':
            return float_string[:-2]
        else:
            return float_string

    @staticmethod
    def _trns_wind_dir(direction):
        '''
            Translate Dutch abbreviated cardinal direction to English
            e.g. ZZW -> SSW
        '''
        return direction.replace('Z', 'S').replace('O', 'E')

    @staticmethod
    def _icon_to_fontawesome(weatherID):
        '''
            Translate Weerplaza 'weather ID' svg name to FontAwesome icon name
        '''
        parse = re.search("([A-M])(\d{3})([D|N])", weatherID)
        if not parse:
            return 'regular/question-circle'

        letter = parse.group(1)
        num = int(parse.group(2))

        dayNight = parse.group(3)
        day = (dayNight == 'D')

        # Could be replaced by match-case but that forces python >= 3.10
        if letter == 'A':
            if num == 5:
                return 'solid/cloud'
            elif num == 1:
                return 'solid/sun' if day else 'solid/moon'
            else:
                return 'solid/cloud-sun' if day else 'solid/cloud-moon'

        elif letter == 'B':
            if num == 6:
                return 'solid/temperature-low'
            elif num == 5:
                return 'solid/temperature-high'
            elif num == 4:
                return 'solid/wind'
            else:
                return 'solid/smog'

        elif letter == 'C':
            return 'solid/cloud-sun-rain' if day else 'solid/cloud-moon-rain'

        elif letter == 'D':
            if num in [3,4]:
                return 'solid/cloud-showers-heavy'
            else:
                return 'solid/cloud-rain'

        elif letter in ['E', 'I']:
            return 'solid/cloud-sun-rain' if day else 'solid/cloud-moon-rain'

        elif letter == 'F':
            if num == 6:
                return 'solid/car-crash'
            else:
                return 'solid/cloud-rain'

        elif letter in ['G', 'H']:
            return 'solid/snowflake'

        elif letter == 'J':
            if num in [3,4,5]:
                return 'solid/cloud-showers-heavy'
            else:
                return 'solid/cloud-rain'

        elif letter == 'K':
            if num in [3,4]:
                return 'solid/poo-storm'
            else:
                return 'solid/bolt'

        elif letter == 'L':
            if num in [3,4,5,6]:
                return 'solid/poo-storm'
            else:
                return 'solid/bolt'

        elif letter == 'M':
            return 'solid/poo-storm'

        # Default
        return 'regular/question-circle'

