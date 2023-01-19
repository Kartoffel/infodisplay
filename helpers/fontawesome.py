'''
    Use FontAwesome svg's, internally converted to raster images using cairosvg
    Operates similar to textfun.py, keeping previously used icons at specific size in memory

    Check 'README.md' in the 'fa' folder on how to download and extract icons

    Icon list at https://fontawesome.com/v5.15/icons?d=gallery&p=2&s=brands,regular,solid&m=free
'''
import logging
from threading import Lock
from io import BytesIO
from cairosvg import svg2png
from PIL import Image

logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

class FontAwesome:
    _icons = {}
    _lock = Lock()

    def __init__(self, cfg):
        self.logger = logging.getLogger(__name__)
        self._default_size = 18

    def get_icon(self, icon, size = None):
        if size == None:
            size = self._default_size

        # Return previously used icons from memory
        if icon in FontAwesome._icons:
            if size in FontAwesome._icons[icon]:
                return FontAwesome._icons[icon][size]

        # Load new icon
        path = 'fa/{}.svg'.format(icon)
        try:
            f = open(path, 'rb')
        except IOError:
            self.logger.error('Could not load icon: {}'.format(icon))
            return None

        with f:
            output = svg2png(file_obj=f, 
                parent_width = size,
                parent_height = size
            )

        icon_png = Image.open(BytesIO(output))

        # Paste transparent icon onto white background
        canvas = Image.new("RGBA", icon_png.size, "WHITE")
        canvas.alpha_composite(icon_png)

        canvas = canvas.convert('L')

        if canvas.width != size or canvas.height != size:
            self.logger.warning("Unexpected canvas size ({}, {})".format(
                canvas.width, canvas.height
            ))

        # Add new icon to memory
        with FontAwesome._lock:
            if icon not in FontAwesome._icons:
                FontAwesome._icons[icon] = {}
            FontAwesome._icons[icon][size] = canvas

        self.logger.debug('Loaded icon {} size {}'.format(icon, size))

        return canvas

    def paste_icon(self, canvas, name, size = None, pos = (0,0)):

        icon = self.get_icon(name, size)

        if icon:
            box = (
                pos[0], pos[1],
                pos[0] + icon.width, pos[1] + icon.height
            )
            canvas.paste(icon, box)
