'''
    Some functions for pasting widgets on the canvas etc.
'''
import re
from PIL import Image, ImageOps, ImageDraw

class ImageFun:
    def __init__(self, config, lock):
        self.borders     = config.getboolean('main', 'borders',
            fallback = True )
        self.borderWidth = int(config.get('main',    'borderWidth',
            fallback = 2    ))
        self.borderCol   = int(config.get('main',    'borderCol',
            fallback = 127  ))

        self.lines      = config.getboolean('main', 'lines', fallback = False)
        lines_hor       = config.get('main', 'lines_hor', fallback = None)
        lines_vert      = config.get('main', 'lines_vert', fallback = None)

        pattern = '(\d+),\s*(?:(?:(\d+)-(\d+))|(\d+))'

        self.lines_hor  = []
        self.lines_vert = []

        for horizontal_line in lines_hor.split('\n'):
            match = re.search(pattern, horizontal_line)
            if match == None:
                continue
            row = int(match.group(1))
            if match.group(4) != None:
                col_start = int(match.group(4))
                col_end = col_start + 1
            else:
                col_start = int(match.group(2))
                col_end = int(match.group(3))

            self.lines_hor.append({
                'row':          row,
                'col_start':    col_start,
                'col_end':      col_end
            })

        for vertical_line in lines_vert.split('\n'):
            match = re.search(pattern, vertical_line)
            if match == None:
                continue
            col = int(match.group(1))
            if match.group(4) != None:
                row_start = int(match.group(4))
                row_end = row_start + 1
            else:
                row_start = int(match.group(2))
                row_end = int(match.group(3))

            self.lines_vert.append({
                'col':          col,
                'row_start':    row_start,
                'row_end':      row_end
            })

        self.rows       = int(config.get('main', 'rows', fallback = 6))
        self.cols       = int(config.get('main', 'cols', fallback = 8))

        self.lock = lock

    def pasteWidget(self, widget, canvas):
        widgetCanvas = widget.getCanvas()

        if widget.invert:
            widgetCanvas = ImageOps.invert(widgetCanvas)

        pos = widget.pos

        if self.borders or self.lines:
            margin = self.borderWidth // 2 + 1
            box = (
                margin, margin, 
                widgetCanvas.width - margin, widgetCanvas.height - margin
            )
            widgetCanvas = widgetCanvas.crop(box)
            pos = (pos[0] + margin, pos[1] + margin)

        with self.lock:
            canvas.paste(widgetCanvas, box = pos)

    @staticmethod
    def circle(draw, center, radius, fill):
        '''
            By Michiel Overtoom, CC BY-SA 3.0
            https://stackoverflow.com/a/33078958
        '''
        draw.ellipse((
            center[0] - radius + 1, center[1] - radius + 1 ,
            center[0] + radius - 1, center[1] + radius - 1), 
            fill=fill, outline=None)

    def drawBorders(self, widgets, canvas):
        if not self.borders:
            return

        with self.lock:
            d = ImageDraw.Draw(canvas)

            for widget in widgets:
                d.line([
                    (widget.pos[0],                 widget.pos[1]),
                    (widget.pos[0] + widget.width-1,  widget.pos[1]),
                    (widget.pos[0] + widget.width-1,  widget.pos[1] + widget.height),
                    (widget.pos[0],                 widget.pos[1] + widget.height),
                    (widget.pos[0],                 widget.pos[1])
                ], fill=self.borderCol, width=self.borderWidth)

    def drawLines(self, canvas):
        if not self.lines:
            return

        row_height = canvas.height // self.rows;
        col_width = canvas.width // self.cols;

        with self.lock:
            d = ImageDraw.Draw(canvas)
            for hl in self.lines_hor:
                xy1, xy2 = [
                    (hl['col_start'] * col_width,   hl['row'] * row_height),
                    (hl['col_end']   * col_width,   hl['row'] * row_height)
                ]
                d.line([xy1, xy2], fill=self.borderCol, width=self.borderWidth)
                self.circle(d, xy1, self.borderWidth // 2, self.borderCol)
                self.circle(d, xy2, self.borderWidth // 2, self.borderCol)

            for vl in self.lines_vert:
                xy1, xy2 = [
                    (vl['col'] * col_width, vl['row_start'] * row_height),
                    (vl['col'] * col_width, vl['row_end']   * row_height)
                ]
                d.line([xy1, xy2], fill=self.borderCol, width=self.borderWidth)
                self.circle(d, xy1, self.borderWidth // 2, self.borderCol)
                self.circle(d, xy2, self.borderWidth // 2, self.borderCol)
                





