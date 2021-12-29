# infodisplay

Modular information display framework aimed at e-ink devices.

![](/assets/sample.jpg)

Built using Python 3.7 and [pillow](https://pillow.readthedocs.io/en/stable/). Works out of the box with [IT8951](https://github.com/GregDMeyer/IT8951)-powered e-paper displays.

## Setting up

TODO

## Structure

Have a look through the example [config file](config.ini.example). This has one `main` section with global configuration parameters, all other sections are specific to widgets.

The display is divided into a grid, where each widget is given a canvas spanning one or more grid cells. The [scheduler](scheduler.py) calls each widget to update their canvas, pastes updated widgets onto the global canvas, and triggers a display update at the right time.

The most basic example of a widget is given in [Dummy.py](widgets/Dummy.py). Widgets are automatically loaded if their name exists as a section in your `config.ini`. These sections should have names matching files in the `widgets/` folder with corresponding widget classes that go by the same name (e.g. there is a 'Dummy' section in `config.ini` and `widgets/Dummy.py` has a class named `Dummy`).

Looking to add support for your own type of (e-ink) display? You should only have to modify [display.py](display.py). Keep in mind that the default canvas is of [image mode](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#modes) `L`, or 8-bit greyscale. You will have to modify this to suit your display.

In due time this information should be moved to the wiki section and expanded.
