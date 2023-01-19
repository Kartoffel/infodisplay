'''
    Make plots using matplotlib and paste them to PIL images

    Matplotlib is not thread safe, so locks are used here to prevent different
    widgets from accessing this class at the same time
'''
import logging
from threading import Lock
from io import BytesIO

import numpy as np
logging.getLogger('matplotlib').setLevel(logging.WARNING)
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as path_effects
from scipy.interpolate import make_interp_spline, BSpline

from datetime import datetime

from PIL import Image
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

class Plot:
    _lock = Lock()

    def __init__(self, cfg):
        self.logger = logging.getLogger(__name__)

        self._default_fontsize = 12

        # 1 typographic point = 1/72 inch
        # Set DPI to 72 so that 1 point / ppi * dpi = 1 pixel
        self._dpi = 72.0

        # Set up plot style
        plt.style.use('grayscale')

    def _fig_to_img(self, fig):
        buf = BytesIO()
        fig.savefig(buf)
        buf.seek(0)
        return Image.open(buf)

    @staticmethod
    def fakeLog(num, base = 10):
        logBase = np.log10(base)
        return np.log10(np.asarray(num) + 1) / logBase

    def rain(self, canvas, 
        width, height, times, precip, pos = (0,0), font = '',
        fontsize = None, xlabel='', ylabel='', title='', noRainMsg = '',
        levels = None, debug = False):
        '''
            Plot function for 'Rain' widget
        '''

        if fontsize == None:
            fontsize = self._default_fontsize

        if levels == None:
            levels = {'light': 0.25, 'moderate': 1, 'heavy': 2.5}

        dt_start    = datetime.fromtimestamp(times[0])
        dt_end      = datetime.fromtimestamp(times[-1])

        with Plot._lock:
            # Set global figure parameters
            if font:
                plt.rcParams['font.family'] = 'sans-serif'
                plt.rcParams['font.sans-serif'] = [font]
                plt.rcParams['font.weight'] = 'normal'
            plt.rcParams['font.size'] = fontsize

            COLOR = 'k'
            plt.rcParams['text.color'] = COLOR
            plt.rcParams['axes.labelcolor'] = COLOR
            plt.rcParams['xtick.color'] = COLOR
            plt.rcParams['ytick.color'] = COLOR

            # Transform data to 'logarithmic' scale with base 6
            base = 6
            precip_log = self.fakeLog(precip, base).tolist()

            # Interpolate points for data fitting
            points = 350
            times_unix_interp = np.linspace(times[0], times[-1], points)
            # Convert interpolated unix times to datetime
            times_interp = [datetime.fromtimestamp(t)
                for t in times_unix_interp]

            # Repeat last data point a few times to tame end of spline
            extra = 5
            delta = (times[-1] - times[0]) / len(times)
            times_extend = times + [
                times[-1] + delta*(i+1) for i in range(extra)]
            data_extend = precip_log + [precip_log[-1] for i in range(extra)]

            # Curve fit precipitation using BSpline
            spline = make_interp_spline(times_extend, data_extend, k=3)
            precip_interp_log = spline(times_unix_interp)

            # Figure with single axes
            fig, ax = plt.subplots(
                figsize = (width/self._dpi, height/self._dpi),
                dpi = self._dpi,
                constrained_layout = True
            )

            # Fill below line
            ax.fill_between(
                times_interp,
                0.0,
                precip_interp_log,
                alpha = 0.3,
                linewidth = 1
            )
            # Draw line
            ax.plot(
                times_interp,
                precip_interp_log,
                'k',
                alpha = 0.5,
                linewidth = 3
            )

            if debug:
                # Plot original data as points connected by dashed line
                ax.plot(
                    [datetime.fromtimestamp(t) for t in times],
                    precip_log,
                    'k--s',
                    alpha = 0.75
                )

            # Determine levels to show on the plot
            levels_plot = ['light']
            if max(precip) > levels['heavy']:
                # Plot light and heavy line
                levels_plot += ['heavy']
            else:
                # Plot light and moderate line
                levels_plot += ['moderate']

            # Don't plot lines if no precipitation is expected,
            # instead write a message
            if max(precip) < levels['light'] / 5:
                levels_plot = []
                if noRainMsg:
                    t = ax.text(0.5, 0.5, noRainMsg,
                        va='center', ha='center', transform=ax.transAxes,
                        color=COLOR, fontsize=fontsize
                    )

            # Actually plot lines
            for level in levels_plot:
                y = self.fakeLog(levels[level], base)
                # Draw the line at height y
                l = ax.axhline(y, label=level, linestyle='--', linewidth=1.5)
                # Draw text on the right of the plot
                t = ax.text(dt_end, y, level, color=COLOR,
                    va='bottom', ha='right')
                # White stroke behind text
                t.set_path_effects([
                    path_effects.Stroke(linewidth=3, foreground='w'),
                    path_effects.Normal()
                ])
                t.set_clip_on(False) # Fine for text to clip figure
                l.set_zorder(4) # Draw lines above text

            y_min = levels['light'] / 5
            y_max = 2 + max(levels['moderate'], min(levels['heavy'] * 2, max(precip)))

            ax.set_ylim(bottom = self.fakeLog(y_min, base))
            ax.set_ylim(top = self.fakeLog(y_max, base))

            ax.set_xlim(dt_start, dt_end)

            # Make x ticks on every 30 minute or full hour
            ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute = [i*30 for i in range(2)]))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

            # Get rid of Y ticks
            ax.get_yaxis().set_ticks([])

            # Move X ticks inside plot
            ax.xaxis.set_tick_params(direction='in', length=8, width=3, pad=5)

            # Move first and last label inwards
            labels = ax.get_xticklabels()
            if dt_start.minute == 0 or dt_start.minute == 30:
                labels[0].set_ha('left')
            if dt_end.minute == 0 or dt_end.minute == 30:
                labels[-1].set_ha('right')

            # Disable all spines except bottom, set line width
            [ax.spines[x].set_visible(False) for x in ['top', 'right', 'left']]
            ax.spines['bottom'].set_linewidth(3)

            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)

            # Move title inwards
            t = ax.set_title(title, fontsize='medium', y=1.0, pad=-fontsize+2)
            # White stroke behind title text
            t.set_path_effects([path_effects.Stroke(linewidth=3, foreground='w'),
                path_effects.Normal()]) # White stroke behind text

            img = self._fig_to_img(fig)
            plt.close(fig)

        box = (
            pos[0], pos[1],
            pos[0] + width, pos[1] + height
        )
        canvas.paste(img, box)       

    def line(self, canvas, width, height, x_data, y_data, pos = (0,0),
        fontsize = None, xlabel='', ylabel='', title='', legend = False):
        '''
            Basic line plot, not very useful.
        '''

        if fontsize == None:
            fontsize = self._default_fontsize

        with Plot._lock:
            # Convert lists to numpy
            # TODO: handle multi-dimensional lists/dicts for multiple lines
            x_data = np.asarray(x_data)
            y_data = np.asarray(y_data)

            # Set global figure parameters
            plt.rcParams['font.size'] = fontsize

            COLOR = 'k'
            plt.rcParams['text.color'] = COLOR
            plt.rcParams['axes.labelcolor'] = COLOR
            plt.rcParams['xtick.color'] = COLOR
            plt.rcParams['ytick.color'] = COLOR

            # Figure with single axes
            fig, ax = plt.subplots(
                figsize = (width/self._dpi, height/self._dpi),
                dpi = self._dpi,
                constrained_layout = True
            )

            ax.plot(x_data, y_data)

            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(title, fontsize='medium')

            if (legend):
                ax.legend()

            img = self._fig_to_img(fig)
            plt.close(fig)

        box = (
            pos[0], pos[1],
            pos[0] + width, pos[1] + height
        )
        canvas.paste(img, box)
