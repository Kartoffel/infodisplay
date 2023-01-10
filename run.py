#!/usr/bin/env python3
'''
    Main file, run this by hand or as a system service.
    Run without arguments to operate as usual.
    Run with an argument specifying the name of a widget if you want to run that specific widget for testing, e.g. `python3 run.py Clock`.
'''
import sys
import signal
import configparser
import logging
from threading import Thread
from time import sleep, perf_counter
from PIL import Image, ImageOps, ImageDraw
from display import Display
from scheduler import Scheduler, Metronome
from helpers.testfun import runWidget

display = None
canvas = None

config = configparser.ConfigParser()
try:
    if config.read('config.ini') == []:
        print("Config file config.ini does not exist or is empty!")
        sys.exit(1)
except Exception as e:
    print("Error reading config file: {}".format(e))
    sys.exit(1)

quiet = config.getboolean('main', 'quiet', fallback = False)
debug = config.getboolean('main', 'debug', fallback = True)

logLevel = logging.DEBUG if debug else (
    logging.WARNING if quiet else logging.INFO)
logging.basicConfig(level = logLevel, 
    format = '%(levelname)s (%(name)s): %(message)s')
logger = logging.getLogger(__name__)


def init():
    '''
        Open connection to display, create canvas
    '''
    global display, canvas
    display = Display(config)
    display.clear()

    logger.info('Connected to display.')
    logger.info('Width: {} px, height {} px'.format(
        display.width, display.height))

    # Create blank canvas for the full display, in 8bpp mode
    canvas = Image.new('L', (display.width, display.height), 
        int(config.get('main', 'background', fallback = '255')))

def signal_handler(sig, frame):
    logger.info("Received {}, shutting down..".format(
        signal.Signals(sig).name
    ))
    Metronome._instance.stop()
    scheduler.unloadWidgets()
    sys.exit(0)

if __name__ == '__main__':
    init()

    if len(sys.argv) == 2:
        runWidget(config, display, canvas, sys.argv[1])
        sys.exit(0)

    scheduler = Scheduler(config, display, canvas)
    scheduler.loadWidgets()

    scheduler.populateDisplay()

    # Seconds between runs of refreshDisplay()
    clockInterval = 1 if scheduler.fastUpdates else 60

    # Set up Metronome (scheduler.py) to run periodic
    Metronome(
        clockInterval,
        scheduler.refreshDisplay,
        name = 'refreshDisplay',
        wait = True
    )

    metroThread = Thread(
        target = Metronome._instance.run,
        name = 'Metronome',
        daemon = True
    )

    # Start Metronome in thread
    metroThread.start()

    # Catch signals to enable graceful exit
    for sig in [signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGTERM]:
        signal.signal(sig, signal_handler)

    # Wait indefinitely for signals
    while True:
        signal.pause()
