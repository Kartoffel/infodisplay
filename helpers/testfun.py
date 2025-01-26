'''
    Test / development functions
'''
import logging
from time import sleep, perf_counter

def runWidget(config, display, canvas, name):
    '''
        Run only a single widget for a short while
        useful for developing
        e.g. `python3 run.py Clock`
    '''
    if canvas == None:
        print('Canvas not initialised!')
        return

    import logging
    from helpers.imagefun import ImageFun
    from threading import Lock
    from datetime import datetime, timedelta
    from importlib import import_module

    # Set global log level debug
    logging.getLogger().setLevel(logging.DEBUG)

    # Get ImageFun functions
    lock = Lock()
    imgFun = ImageFun(config, lock)

    row_height = canvas.height // imgFun.rows
    col_width = canvas.width // imgFun.cols

    # Import widget
    if not name in config.sections():
        print('Widget {} not in config file!'.format(name))
        return

    row = config.get(name, 'row', fallback='0').split('-')
    col = config.get(name, 'col', fallback='0').split('-')

    pos = (int(col[0]) * col_width, int(row[0]) * row_height)

    width =  (col_width if len(col) == 1
        else (col_width * (1 + int(col[1]) - int(col[0]))))
    height = (row_height if len(row) == 1
        else (row_height * (1 + int(row[1]) - int(row[0]))))

    fastUpdate = config.getboolean(name, 'fastUpdate', fallback = False)

    try:
        wdgClass = getattr(
            import_module('widgets.{}'.format(name)), 
            name
        )
        widget = wdgClass(config,
            width = width,
            height = height,
            pos = pos
        )
    except Exception as e:
        print("Failed to add widget {}".format(name))
        print("{}".format(e))
        return
    else:
        print("Imported {} ({})".format(name,
            'fast' if fastUpdate else 'normal'))

    timeNext = datetime.now() + timedelta(seconds = 1)

    tic = perf_counter()
    widget.draw(datetime = timeNext)
    imgFun.pasteWidget(widget, canvas)
    toc = perf_counter()

    print("Drawing widget: {:.1f} ms".format(
        1000.0 * (toc - tic)
    ))

    imgFun.drawBorders(widget, canvas)
    imgFun.drawLines(canvas)

    tic = perf_counter()
    display.updateBuf(canvas)
    display.refresh(flash = False)
    toc = perf_counter()

    print("Full display refresh: {:.1f} ms".format(
        1000.0 * (toc - tic)
    ))

    if fastUpdate:
        sleep(2.5)

        print("Running 10 second loop..")

        for i in range(10):
            tic = perf_counter()

            # Update widget
            timeNext = datetime.now() + timedelta(seconds = 1)
            widget.draw(datetime = timeNext)
            imgFun.pasteWidget(widget, canvas)

            toc = perf_counter()

            # Refresh display
            display.updateBuf(canvas)
            display.refresh(greyscale = False, partial = True, flash = False)

            tac = perf_counter()

            print("Loop {}, redraw: {:.1f} ms, refresh: {:.1f} ms".format(
                i,
                1000.0 * (toc - tic),
                1000.0 * (tac - toc)
            ))

            sleepTime = 1 - (tac - tic)
            if sleepTime > 0:
                sleep(sleepTime)

    print("Cleaning up..")
    try:
        widget.cleanup()
    except:
        pass
