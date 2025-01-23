'''
    Wrapper for PIL text functions
    Mainly to keep used fonts loaded and reduce file accesses

    Fonts are probably in /usr/share/fonts/truetype/
'''
import logging
from threading import Lock
from PIL import Image, ImageDraw, ImageFont

class Text:
    # Class variable stores all instances of previously used fonts with sizes
    _fonts = {}
    _lock = Lock()

    def __init__(self, cfg):
        self.logger = logging.getLogger(__name__)

        self._default_font = 'DejaVuSans'
        self._default_size = 20

    def _get_font(self, font = None, fontsize = None):
        if font == None:
            font = self._default_font
        if fontsize == None:
            fontsize = self._default_size

        if font in Text._fonts:
            if fontsize in Text._fonts[font]:
                return Text._fonts[font][fontsize]

        try:
            newFont = ImageFont.truetype('{}.ttf'.format(font), fontsize)
        except OSError:
            self.logger.warning('Could not load font {}, using default'.format(
                font))
            try:
                newFont = ImageFont.truetype('FreeSans.ttf', fontsize)
            except OSError:
                newFont = ImageFont.truetype('DejaVuSans.ttf', fontsize)
        else:
            self.logger.debug('Loaded font {} size {}'.format(font, fontsize))

        with Text._lock:
            if font not in Text._fonts:
                Text._fonts[font] = {}

            # Add to dict
            Text._fonts[font][fontsize] = newFont
        return newFont

    def bbox(self, buffer, text, pos = (0,0), font = None,
                fontsize = None, anchor = 'la'):
        draw = ImageDraw.Draw(buffer)
        dFont = self._get_font(font, fontsize)
        return draw.textbbox(pos, text, dFont, anchor=anchor)

    def size(self, *args, **kwargs):
        bbox = self.bbox(*args, **kwargs)
        width = abs(bbox[2] - bbox[0])
        height = abs(bbox[3] - bbox[1])
        return (width, height)

    def write(self, buffer, text, pos = (0,0), font = None,
                fontsize = None, fill = None, anchor = 'la', max_width = 0):
        '''
            Useful reference for text anchors:
            https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html#text-anchors
        '''
        draw = ImageDraw.Draw(buffer)
        dFont = self._get_font(font, fontsize)
        
        if not max_width:        
            draw.text(pos, text, font=dFont, fill=fill, anchor=anchor)
            return
        
        w, _ = self.size(buffer, text, pos, font=font, fontsize=fontsize)
        if w <= max_width:
            draw.text(pos, text, font=dFont, fill=fill, anchor=anchor)
            return
        
        line = ''
        
        for word in text.split():
            tmp = ' '.join([line, word]) if line != '' else word
            w, _ = self.size(buffer, tmp, pos, font=font, fontsize=fontsize)
            
            if w <= max_width:
                line = tmp
            else:
                while w > max_width:
                    word = word[:-1]
                    tmp = ' '.join([line, word]) if line != '' else word
                    w, _ = self.size(buffer, tmp, pos, font=font, fontsize=fontsize)
                line = tmp[:-1] + '..'
                break
        draw.text(pos, line, font=dFont, fill=fill, anchor=anchor)
            
        

    def centered(self, buffer, text, offset = (0,0), font = None,
                    fontsize = None, fill = None, anchor = 'mm'):
        buf_width, buf_height = buffer.size
        pos = (buf_width // 2 + offset[0], buf_height // 2 + offset[1])
        self.write(buffer, text, pos, font, fontsize, fill, anchor)

    def textbox(self, buffer, text, width, pos = (0,0), max_lines = None,
        font = None, fontsize = None, fill = None, spacing = 0, **kwargs):
        '''
            Fill text into box with automatic line breaks, optional maximum height
            Returns (width, height) of final box
        '''

        if fontsize == None:
            raise ValueError("Font size needs to be specified!")

        # Split text into separate lines first
        lines = []
        cur_line = ''
        for word in text.split():
            tmp = ' '.join([cur_line, word]) if cur_line != '' else word
            size = self.size(buffer, tmp, pos, font=font, fontsize=fontsize, **kwargs)
            if size[0] <= width:
                cur_line = tmp
            else:
                lines.append(cur_line)
                cur_line = word
                if max_lines != None and len(lines) >= max_lines:
                    lines[-1] += '..'
                    break

        if cur_line and (max_lines == None or len(lines) < max_lines):
            lines.append(cur_line)

        hh = pos[1]

        for line in lines:
            if not line:
                continue
            self.write(buffer,
                line,
                pos = (pos[0], hh),
                font = font,
                fontsize = fontsize,
                fill=fill,
                **kwargs
            )
            hh += (fontsize + spacing)

        hh = max(hh, fontsize)

        return (width, hh - pos[1])
