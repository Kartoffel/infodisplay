'''
    This module handles redrawing of the widgets with the right interval,
    and updating the display.
'''
import sys
import time
import logging
from threading import Thread, Lock
from multiprocessing.pool import ThreadPool, TimeoutError
from datetime import datetime, timedelta
from importlib import import_module
from helpers.imagefun import ImageFun

class Metronome:
    '''
        Run a threaded function on a regular interval, on the second.

        Param wait: wait for the thread to finish before starting a new one,
            may cause it to miss seconds.
    '''

    _instance = None

    def __init__(self, interval, function, name = '', wait = True):
        self.logger = logging.getLogger(__name__)

        self.interval = int(interval)
        self.fun = function
        self.name = name
        self.wait = wait

        self.thread = []

        self.kill = False

        Metronome._instance = self

    def run(self):
        self.logger.debug(
            'Metronome initialised with interval {}'.format(self.interval)
        )

        if self.interval % 60 == 0:
            # If interval is in round minutes, wait until start of next minute
            self.logger.debug('Waiting for next minute..')
            while datetime.now().second != 0:
                time.sleep(0.01)

        while not self.kill:
            if self.thread != [] and self.wait:
                self.thread.join()

            # Sleep for interval minus one second first
            time.sleep(self.interval - 1)

            #nextTime = (datetime.now().replace(microsecond=0) + 
            #    timedelta(seconds = 1))

            self.thread = Thread(
                target = self.fun,
                #kwargs = {'now': nextTime},
                name = self.name
            )

            # Sleep until very start of next second
            now = time.time()
            time.sleep(int(now + 1) - now)

            if not self.kill:
                self.thread.start()

    def stop(self):
        self.kill = True


class Scheduler:
    def __init__(self, cfg, display = None, canvas = None):
        self.logger = logging.getLogger(__name__)

        if canvas == None or display == None:
            self.logger.error('No canvas or display given!')
            sys.exit(1)

        self.config = cfg
        self.display = display
        self.canvas = canvas

        self.lock = Lock()
        self.imgFun = ImageFun(cfg, self.lock)

        # Whether fast updating widgets are present
        # (run update routine every second)
        self.fastUpdates = False

        self.regularWidgets = []
        self.fastWidgets = []

        # Keep track of widgets that finished updating
        self.updatedFastWidgets = []
        self.updatedRegularWidgets = []
        # Locks for changing above lists
        self.fastLock = Lock()
        self.regularLock = Lock()

        # Threadpool for fast (1s) widgets
        self.pool = ThreadPool(2)
        # Workers in threadpool for fast widgets
        self.workers = []

        # Timeout for execution of regular widgets (seconds)
        self.timeout = 40

    def loadWidgets(self):
        '''
            Scan config file and initialise widgets.
        '''
        config = self.config

        rows = int(config.get('main', 'rows', fallback = 6))
        cols = int(config.get('main', 'cols', fallback = 8))
        row_height = self.canvas.height // rows;
        col_width = self.canvas.width // cols;

        self.logger.debug("Row height: {} px, col width: {} px".format(
            row_height, col_width))

        for widget in config.sections():
            if widget == 'main':
                continue
            if not config.getboolean(widget, 'enabled', fallback = False):
                continue

            row = config.get(widget, 'row', fallback='0').split('-')
            col = config.get(widget, 'col', fallback='0').split('-')

            pos = (int(col[0]) * col_width, int(row[0]) * row_height)

            width =  (col_width if len(col) == 1
                else (col_width * (1 + int(col[1]) - int(col[0]))))
            height = (row_height if len(row) == 1
                else (row_height * (1 + int(row[1]) - int(row[0]))))

            fastUpdate = config.getboolean(widget, 'fastUpdate', fallback = False)

            try:
                wdgClass = getattr(
                    import_module('widgets.{}'.format(widget)), 
                    widget
                )
                wList = self.fastWidgets if fastUpdate else self.regularWidgets
                wList.append(wdgClass(config,
                    width = width,
                    height = height,
                    pos = pos
                ))
            except Exception as e:
                self.logger.warning("Failed to add widget {}".format(widget))
                self.logger.warning("{}".format(e))
                continue
            else:
                self.logger.debug("Imported {} ({})".format(widget, 
                    'fast' if fastUpdate else 'normal'))
            
        self.logger.info("Imported {} widgets".format(
            len(self.fastWidgets) + len(self.regularWidgets)))
        if len(self.fastWidgets) != 0:
            self.fastUpdates = True

    def unloadWidgets(self):
        '''
            Cleanup widgets and shut down worker pools
        '''
        self.pool.terminate()
        for widget in self.regularWidgets + self.fastWidgets:
            try:
                widget.cleanup()
            except:
                pass

    def pasteWidget(self, widget):
        '''
            Paste widget onto canvas.
        '''
        self.imgFun.pasteWidget(widget, self.canvas)

    def pasteRegularWidgets(self):
        with self.regularLock:
            for widget in self.updatedRegularWidgets:
                self.pasteWidget(widget)
            self.updatedRegularWidgets = []

        # Draw lines and borders
        self.imgFun.drawBorders(
            self.regularWidgets + self.fastWidgets, 
            self.canvas
        )
        self.imgFun.drawLines(self.canvas)

    def pasteFastWidgets(self):
        with self.fastLock:
            for widget in self.updatedFastWidgets:
                self.pasteWidget(widget)
            self.updatedFastWidgets = []

    def callback(self, widget):
        '''
            Callback for when fast widget is done drawing.
        '''
        self.updatedFastWidgets.append(widget)

    def redrawFastWidgets(self, datetime):
        '''
            Schedule redraw of all fast widgets.
        '''
        pool = self.pool
        # Prune finished workers from list
        self.workers = [w for w in self.workers if not w['worker'].ready()]

        for widget in self.fastWidgets:

            # Check if worker for this widget is not still running
            if not any(w['name'] == widget.name for w in self.workers):
                w = pool.apply_async(
                    widget.draw,
                    kwds={'datetime': datetime},
                    callback = self.callback
                )
                worker = {
                    'name': '{}'.format(widget.name),
                    'worker': w
                }
                self.workers.append(worker)
            else:
                self.logger.debug(
                    'Worker for {} not finished in time!'.format(widget.name)
                )

    def redrawRegularWidgets(self, datetime, forceDraw = False):
        '''
            Schedule redraw of regular widgets where necessary.
        '''
        pool = ThreadPool(3)
        regularWorkers = []

        start = time.time()

        nextMinute = datetime.minute

        for widget in self.regularWidgets:
            if (nextMinute % widget.refreshInterval == 0) or forceDraw:
                # Start worker to update widget
                w = pool.apply_async(
                    widget.draw,
                    kwds={'datetime': datetime}
                )
                worker = {
                    'name': '{}'.format(widget.name),
                    'worker': w
                }
                regularWorkers.append(worker)

        pool.close()

        while time.time() - start <= self.timeout:
            if all(worker['worker'].ready() for worker in regularWorkers):
                break
            [worker['worker'].wait(1) for worker in regularWorkers]

        for worker in regularWorkers:
            if not worker['worker'].ready():
                self.logger.warning(
                    'Regular worker for {} not finished in time!'.format(
                        worker['name']))
                continue

            try:
                widget = worker['worker'].get(1)
            except TimeoutError:
                self.logger.error('Error getting widget {} from worker'.format(
                    worker['name']))
            else:
                #self.imgFun.pasteWidget(widget, self.canvas)
                with self.regularLock:
                    self.updatedRegularWidgets.append(widget)
            
        # Terminate any still running workers in pool
        pool.terminate()


    def populateDisplay(self):
        tic = time.perf_counter()
        self.logger.debug('Drawing regular widgets..')
        self.redrawRegularWidgets(datetime.now(), forceDraw = True)

        self.logger.debug('Drawing fast widgets..')
        self.redrawFastWidgets(datetime.now() + timedelta(seconds = 1))

        [w['worker'].wait(2) for w in self.workers]

        toc = time.perf_counter()
        self.logger.debug('Drawing all widgets took {:.1f} ms'.format(
            1000.0 * (toc - tic)
        ))

        self.logger.debug('Updating display..')
        self.pasteFastWidgets()
        self.pasteRegularWidgets()
        self.display.updateBuf(self.canvas)
        self.display.refresh(greyscale = True, partial = False, flash = True)

    def refreshDisplay(self, now = None):
        '''
            Refresh display and schedule redraw of widgets.
            This function should run exactly on the second, every second or every minute.
        '''
        if now == None:
            now = datetime.now()

        if (not self.fastUpdates) and False:
            self.logger.debug(
                'Time is now {:0>2d}:{:0>2d}:{:0>2d} +{:.1f} ms'.format(
                    now.hour,
                    now.minute,
                    now.second,
                    now.microsecond / 1000
            ))

        # Partial greyscale display refresh every full minute,
        # partial monochrome update every second

        # Paste updated fast widgets onto canvas
        self.pasteFastWidgets()

        # Redraw fast widgets immediately for next second
        timeNext = now + timedelta(seconds = 1)
        self.redrawFastWidgets(timeNext)

        if now.second == 0 or not self.fastUpdates:
            # Paste updated regular widgets onto canvas
            self.pasteRegularWidgets()

            # Copy canvas to display buffer
            self.display.updateBuf(self.canvas)

            # TODO: refresh with `partial = False, flash = True` every hour or so to remove ghosting?
            # Does not seem necessary for IT8951, no ghosting when only using partial updates
            self.display.refresh(greyscale = True, partial = True, flash = False)

            # Schedule redraw of regular widgets

            timeNext = now + timedelta(minutes = 1)
            #self.redrawRegularWidgets(timeNext)

            thread = Thread(
                target = self.redrawRegularWidgets,
                args = (timeNext,),
                name = 'redrawRegularWidgets',
                daemon = True
            )
            thread.start()

        elif self.fastUpdates:

            self.display.updateBuf(self.canvas)
            self.display.refresh(greyscale = False, partial = True, flash = False)

            



