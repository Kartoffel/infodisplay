'''
    Vertrektijd.info public transport interface for 'Transport' widget

    Needs 'apiKey' client API key in config.ini, obtained following https://www.vertrektijd.info/starten.html
'''
import logging
from datetime import date, datetime, timedelta
from dateutil.parser import isoparse
import requests
from urllib.parse import quote

wName = 'Transport'

class VertrektijdInfo:
    _API_BASE_URL = "https://api.vertrektijd.info"
    # Request API version
    _API_VERSION = "1.5.0"
    
    # Request headers
    # Accept: application/json
    # X-Vertrektijd-Client-Api-Key
    
    
    # GET /stop/_nametown/{town}/{stop}/ → ScheduleName, [Type, Town, StopName, StopCode, Latitude, Longitude, SimilarStops]
    # GET /stop/lines/{schedule_stop}/ (ScheduleName → schedule_stop) → List: LineId, LineNumber, LineName, Agency, TransportType
    
    # GET /departures/_nametown/{town}/{stop}/ → TRAIN / BTMF
    #   BTMF (list) → Station_Info → StopCode, StopName, Town
    #               → Station_Messages → MessageTimeStamp, AgencyCode, MessageStart/EndTime, MessageContent
    #               → Departures (list) → LineNumber, LineName, Destination, DestinationCode, TransportType, AgencyCode, ...
    
    # GET /departures/_stopcode/{stop_code}/ (stop_code can be comma delimited list)

    def __init__(self, cfg):
        self.name   = __name__
        self.logger = logging.getLogger(self.name)

        self.api_key = cfg.get(wName, 'apiKey', fallback = "")
        
        self.stopName = cfg.get(wName, 'stopName', fallback = "")
        self.stopCodes = cfg.get(wName, 'stopCodes', fallback = "")
        
        self.lastStopName = ""
        
        self.timeout = 10
        
        # Default GET header for requests
        self.headers = {
            'Accept': 'application/json',
            'Accept-Version': self._API_VERSION,
            'X-Vertrektijd-Client-Api-Key': self.api_key
        }
        
        self.logger.debug(f"stopCodes from config: {self.stopCodes}")
        
        if self.stopName:
            self._get_stopcodes()
            self.logger.debug(f"stopCodes total: {self.stopCodes}")
        
        if not self.stopCodes:
            self.logger.error(f"No stopCodes or valid stopName configured!")
    
    def _get_stopcodes(self):
        town, stop = [x.strip() for x in self.stopName.split(',', 1)]
        result = self._get_departures_nametown(town, stop)
        
        if not result:
            self.logger.error(f"Unable to get departures for stop {stop} in {town}")
            return
        
        for station in result['TRAIN']:
            info = station['Station_Info']
            self.logger.debug(f"** Train station {info['StopName']} in {info['Town']} **")
            self.logger.debug(f"StopCode: {info['StopCode']}")
            self.logger.debug(f"Departures:")
            
            for departure in station['Departures']:
                self.logger.debug(
                    f"* {departure['PlannedDeparture']} +{departure['Delay']} min "
                    f"[Platform {departure['Platform']}] "
                    f"{departure['TransportTypeCode']} to {departure['Destination']}"
                )
                for tip in departure['Tips']:
                    self.logger.debug(f"Tip: {tip}")
                
                for comment in departure['Comments']:
                    self.logger.debug(f"Comment: {comment}")
            
        for stop in result['BTMF']:
            info = stop['Station_Info']
            self.logger.debug(f"** BTMF stop {info['StopName']} in {info['Town']} **")
            self.logger.debug(f"StopCode: {info['StopCode']}")
            
            self.stopCodes += ("," if self.stopCodes else "") + info['StopCode']
            
            if 'Station_Messages' in stop:
                msg = stop['Station_Messages']
                self.logger.debug(
                    "Message (valid "
                    f"{msg['MessageStartTime']} to {msg['MessageEndTime']}):"
                )
                self.logger.debug(
                    f"{msg['MessageTimeStamp']} [{msg['AgencyCode']}]: "
                    f"{msg['MessageContent']}"
                )
            
            self.logger.debug(f"Departures:")
            for departure in stop['Departures']:
                if 'Destination' in departure: # weird bugfix for some future Metros
                    self.logger.debug(
                        f"* {departure['PlannedDeparture']} → {departure['ExpectedDeparture']} "
                        f"{departure['AgencyCode']} {departure['TransportType']} "
                        f"{departure['LineNumber']} to {departure['Destination']} "
                        f"({departure['VehicleStatus']})"
                    )
    
    def _parse_timestamp(self, time_string):
        # Parse ISO 8601 and convert to datetime object in current timezone
        dt = isoparse(time_string).astimezone()
        # Remove timezone attribute to make it offset-naive
        return dt.replace(tzinfo=None)
    
    def _format_timestamp(self, dt):
        return f"{dt.hour:0>2d}:{dt.minute:0>2d}"
    
    def get_departures(self):
        response = {
            'success': False,
            'timestamp': datetime.now(),
            'stopName': "",
            'departures': [],
            'announcements': []
        }
        
        if not self.stopCodes:
            # Retry getting stopCodes from stopName
            self.logger.warning(f"No stopCodes! Retrying..")
            self._get_stopcodes()
            self.logger.warning(f"Got stopCodes: {self.stopCodes}")
        
        if not self.stopCodes:
            return response
        
        result = self._get_departures_stopcode(self.stopCodes)
        
        if not result:
            return response
        
        for stop in result['BTMF']:
            info = stop['Station_Info']
            if info['StopName']:
                response['stopName'] = info['StopName']
                # Keep track of last non-empty stopName
                self.lastStopName = info['StopName']
            
            if 'Station_Messages' in stop:
                msg = stop['Station_Messages']
                
                response['announcements'].append({
                    'stopCode': info['StopCode'],
                    'timestamp': msg['MessageTimeStamp'],
                    'agency': msg['AgencyCode'],
                    'start_dt': self._parse_timestamp(msg['MessageStartTime']),
                    'end_dt': self._parse_timestamp(msg['MessageEndTime']),
                    'content': msg['MessageContent']
                })
            
            for departure in stop['Departures']:
                dt_plan = self._parse_timestamp(departure['PlannedDeparture'])
                dt_exp = self._parse_timestamp(departure['ExpectedDeparture'])
                
                if 'Destination' not in departure: # weird bugfix for some future Metros
                    dest = "???"
                else:
                    dest = departure['Destination']
                
                dep = {
                    'stopCode': info['StopCode'],
                    'agency': departure['AgencyCode'],
                    'lineNumber': departure['LineNumber'],
                    'lineName': departure['LineName'],
                    'name': dest,
                    'type': departure['TransportType'],
                    'plannedDeparture': dt_plan,
                    'expectedDeparture': dt_exp,
                    'delayMins': round((dt_exp - dt_plan) / timedelta(minutes=1)),
                    'expectedDepartureTime': self._format_timestamp(dt_exp),
                    'vehicleStatus': departure['VehicleStatus']
                }
                response['departures'].append(dep)
        
        # Sort announcements by start date ascending
        response['announcements'].sort(key = lambda x: x['start_dt'].timestamp())
        
        # Sort departures by expected departure time ascending
        response['departures'].sort(key = lambda x: x['expectedDeparture'].timestamp())
        
        # API bug workaround
        if not response['stopName']:
            # Use last non-empty stopName
            response['stopName'] = self.lastStopName
        
        response['success'] = True
        
        return response
    
    def _get_departures_nametown(self, town, stop):
        return self._request_json(f'/departures/_nametown/{town}/{stop}/')
    
    def _get_departures_latlon(self, lat, lon, distance = 0.1):
        # Distance given in km (e.g. 0.1 = 100m), maximum 500 meters
        return self._request_json(f'/departures/_geo/{lat}/{lon}/{distance}/')
    
    def _get_departures_stopcode(self, stopCodes):
        return self._request_json(f'/departures/_stopcode/{stopCodes}/')

    def _request_json(self, url_relative):
        try:
            r = requests.get(
                self._API_BASE_URL + 
                    quote(url_relative),
                headers = self.headers,
                timeout = self.timeout
            )
            r.raise_for_status()
        except requests.exceptions.Timeout:
            self.logger.warning("Request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            self.logger.warning(f"HTTP error {e}")
            self.logger.warning(e.response.text)
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(e)
            return None
        
        if r.status_code != 200:
            self.logger.warning(f"HTTP status {r.status_code}")
            return None
        
        if r.headers['Content-Type'] != self.headers['Accept']:
            self.logger.warning(f"Unexpected content type {r.headers['Content-Type']}")
            return None
        
        json = r.json()
        if 'code' in json and json['code'] != 200:
            # API error
            self.logger.warning(f"API error {json['code']}: {json['status']}")
            return None
        
        return json


