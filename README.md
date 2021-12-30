# infodisplay
![](/assets/sample.jpg)
_My display, using a Raspberry Pi Zero W and Waveshare [6" e-paper hat](https://www.waveshare.com/wiki/6inch_e-Paper_HAT)._

Modular information display framework aimed at e-ink devices.

Built using Python 3.7 and [pillow](https://pillow.readthedocs.io/en/stable/). Works out of the box with [IT8951](https://github.com/GregDMeyer/IT8951)-powered e-paper displays.

## Setting up

- When using an e-paper display with IT8951 controller, install GregDMeyer's [IT8951](https://github.com/GregDMeyer/IT8951) library following the instructions there.
- Clone this repository and `cd` to its folder.
- Install the basic required packages using `pip`:
```bash
pip3 install -r requirements.txt
```
- Install the optional packages:
- (If you plan to use the google calendar integration, or a widget with plots)
```bash
pip3 install -r optional-requirements.txt
```
_Note for Raspberry Pi users: you [may have to](https://numpy.org/devdocs/user/troubleshooting-importerror.html#raspberry-pi) install numpy and matplotlib from the raspbian package manager._
- Copy the example config file:
```bash
cp config.ini.example config.ini
```
- Make your changes to `config.ini` using your favourite editor.

You should now be able to run the info display using something like `python3 run.py`.

### FontAwesome icons
The class in [fontawesome.py](helpers/fontawesome.py) lets you use [FontAwesome](https://fontawesome.com/) icons. These are used in the Calendar widget by default. 

To see the icons, download a set of FontAwesome svg's (e.g. from [here](https://fontawesome.com/v5.15/how-to-use/on-the-desktop/setup/getting-started)) and unzip the `regular`, `solid`, and `brands` folders into the `fa/` folder:
```bash
wget https://use.fontawesome.com/releases/v5.15.4/fontawesome-free-5.15.4-desktop.zip
unzip fontawesome-free-5.15.4-desktop.zip
mv fontawesome-free-5.15.4-desktop/svgs/* fa/
```

### Running as a service
A sample systemd unit file is provided in `infodisplay.service`.
This is set up so the service only starts after an NTP time sync is established. Raspberry Pi's don't have a hardware RTC, so system time can be wildly inaccurate until they get the network time.

- Edit `infodisplay.service` to reflect where you cloned the repository to, and what user it should run as.  _(default: `/home/pi/infodisplay` and `pi`)_
- Enable the systemd `time-sync.target`:
```bash
sudo systemctl enable systemd-time-wait-sync
```
- Copy your unit file:
```bash
sudo cp infodisplay.service /etc/systemd/system/
```
- Reload systemd:
```bash
sudo systemctl daemon-reload
```
- Enable autostart of the service:
```bash
sudo systemctl enable infodisplay.service
```
- Finally, start the service:
```bash
sudo systemctl start infodisplay.service
```

### Google Calendar integration
To get events from your Google Calendar you need a Google Cloud Platform project, OAuth credentials and finally a token.
Follow the 'Prerequisites' section of [this tutorial](https://developers.google.com/calendar/api/quickstart/python) and you should have a `credentials.json` file at the end.

The following needs to be done **on your desktop computer**, as a dialog will pop up for authorization:
- Clone this repo.
- Install the optional requirements using ```pip3 install -r optional-requirements.txt```.
- Copy your `credentials.json` to the `util` folder.
- `cd` to the `util` folder.
- Run ```python3 get-google-calendars.py```.

This script should give you the ID's of the calendars synced to your account. Pick the ones you want and add them to the `config.ini`.
There should now also be a `token.json` file in the directory, copy this to your main infodisplay folder.

## Structure

Have a look through the example [config file](config.ini.example). This has one `main` section with global configuration parameters, all other sections are specific to widgets.

The display is divided into a grid, where each widget is given a canvas spanning one or more grid cells. The [scheduler](scheduler.py) calls each widget to update their canvas, pastes updated widgets onto the global canvas, and triggers a display update at the right time.

The most basic example of a widget is given in [Dummy.py](widgets/Dummy.py). Widgets are automatically loaded if their name exists as a section in your `config.ini`. These sections should have names matching files in the `widgets/` folder with corresponding widget classes that go by the same name (e.g. there is a 'Dummy' section in `config.ini` and `widgets/Dummy.py` has a class named `Dummy`).

Looking to add support for your own type of (e-ink) display? You should only have to modify [display.py](display.py). Keep in mind that the default canvas is of [image mode](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#modes) `L`, or 8-bit greyscale. You will have to modify this to suit your display.

### Notes
In due time this information should be moved to the wiki section and expanded.
