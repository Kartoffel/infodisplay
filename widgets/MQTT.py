'''
    Widget to show data from MQTT
'''
import logging
from PIL import Image
from helpers.textfun import Text
import paho.mqtt.client as mqtt

wName = 'MQTT'

class MQTT:
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
        self.fontSize   = int(cfg.get(wName, 'fontSize', fallback = 32))
        self.titleSize  = int(cfg.get(wName, 'titleSize', fallback = 24))

        # Parse element config
        self.elements   = []
        elements = cfg.get(wName, 'elements', fallback = "")
        for element in elements.split('\n'):
            if element:
                parts = element.split(',')
                if len(parts) not in [3,4]:
                    continue
                self.elements.append({
                    'title': parts[0],
                    'topic': parts[1],
                    'format': parts[2],
                    'unit': parts[3] if len(parts) > 3 else '',
                    'last': '-'
                })

        # Sizes
        vertSize = self.height - 2 * self.margin
        self.titleHeight = vertSize * self.titleSize // (self.titleSize + self.fontSize)
        self.valueHeight = vertSize * self.fontSize // (self.titleSize + self.fontSize)
        self.padding = 6

        horSize = self.width - 2 * self.margin
        self.cellWidth = horSize // len(self.elements)

        # Set up MQTT
        self.server     = cfg.get(wName, 'server')
        self.port       = int(cfg.get(wName, 'port', fallback = 1883))
        self.connected  = False

        self.mqttc = mqtt.Client()
        self.mqttc.on_connect = self.onConnect
        self.mqttc.on_disconnect = self.onDisconnect
        self.mqttc.on_message = self.onMessage
        self.mqttc.disable_logger()

        self.mqttc.connect(self.server, self.port)

        # Define canvas
        self.canvas = Image.new('L', (self.width, self.height), 0xFF)

        # Text manipulation
        self.text = Text(cfg)

        self.mqttc.loop_start()


    def onConnect(self, client, userdata, flags, rc):
        self.connected = True
        self.logger.debug("Connected to MQTT server")
        for element in self.elements:
            client.subscribe(element['topic'], qos=2)


    def onDisconnect(self, client, userdata, rc):
        self.connected = False
        self.logger.debug("Disconnected from MQTT server")


    def onMessage(self, client, userdata, message):
        self.logger.debug("Message on topic {}: {}".format(message.topic, message.payload))

        el = next((element for element in self.elements if element['topic'] == message.topic), None)

        if el == None:
            return

        if el['format'] == 'raw':
            string = "{:s}{:s}".format(message.payload, el['unit'])
        else:
            number = float(message.payload.split()[0])
            string = "{:.{dec}f}{:s}".format(number, el['unit'], dec=el['format'])

        el['last'] = string
        self.logger.debug("Parsed: {}".format(string))


    def draw(self, **kwargs):
        # Clear canvas
        self.canvas.paste(0xFF, box=(0, 0, self.width, self.height))

        for i, element in enumerate(self.elements):
            horPos = self.margin + self.cellWidth // 2 + i * self.cellWidth
            self.text.write(self.canvas,
                element['title'],
                pos = (horPos, self.margin + self.titleHeight - self.padding),
                font = self.font,
                fontsize = self.titleSize,
                anchor = 'ms'
            )
            self.text.write(self.canvas,
                element['last'],
                pos = (horPos, self.margin + self.titleHeight + self.padding),
                font = self.font,
                fontsize = self.fontSize,
                anchor = 'mt'
            )

        return self


    def getCanvas(self):
        return self.canvas


    def cleanup(self):
        self.mqttc.loop_stop()
        return


