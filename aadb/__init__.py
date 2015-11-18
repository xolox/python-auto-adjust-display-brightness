# Automatically adjust the display brightness of Linux displays.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 18, 2015
# URL: https://github.com/xolox/python-auto-adjust-display-brightness

"""
Usage: auto-adjust-display-brightness [OPTIONS]

Automatically adjust the display brightness of Linux displays.

If the system booted less than five minutes ago the display brightness is
adjusted in a single step. After five minutes of uptime the brightness is
adjusted in steps of 10% (unless --force is given).

Supports back light brightness control using the Linux `/sys/class/backlight'
interface as well as fall back to software brightness control using `xrandr'.

Supported options:

  -f, --force

    Adjust the display brightness in one step regardless of uptime.

  -v, --verbose

    Make more noise (increase logging verbosity).

  -q, --quiet

    Make less noise (decrease logging verbosity).

  -h, --help

    Show this message and exit.
"""

# Standard library modules.
import ConfigParser
import datetime
import errno
import functools
import getopt
import logging
import os
import re
import sys
import time

# External dependencies.
import coloredlogs
import ephem
from executor import execute
from humanfriendly import compact, concatenate
from humanfriendly.terminal import usage, warning

# Semi-standard module versioning.
__version__ = '1.1'

# Initialize a logger for this module.
logger = logging.getLogger(__name__)
execute = functools.partial(execute, logger=logger)

# The locations of known configuration files.
CONFIG_FILES = [
    '/etc/auto-adjust-display-brightness.ini',
    '~/.auto-adjust-display-brightness.ini',
]


def main():
    """Command line interface for the ``auto-adjust-display-brightness`` program."""
    # Initialize logging to the terminal.
    coloredlogs.install()
    # Parse the command line arguments.
    step_brightness = None
    try:
        options, arguments = getopt.getopt(sys.argv[1:], 'fvqh', [
            'force', 'verbose', 'quiet', 'help'
        ])
        for option, value in options:
            if option in ('-f', '--force'):
                step_brightness = False
            elif option in ('-v', '--verbose'):
                coloredlogs.increase_verbosity()
            elif option in ('-q', '--quiet'):
                coloredlogs.decrease_verbosity()
            elif option in ('-h', '--help'):
                usage(__doc__)
                return
            else:
                assert False, "Unhandled option!"
    except Exception as e:
        warning("Failed to parse command line arguments! (%s)", e)
        sys.exit(1)
    # Load the configuration file(s).
    try:
        config = load_config()
    except ConfigurationError as e:
        warning("%s", e)
        sys.exit(1)
    # Determine whether to change the brightness at once or gradually.
    if step_brightness is None:
        if find_system_uptime() < 60 * 5:
            logger.info("Changing brightness at once (system has just booted).")
            step_brightness = False
        else:
            logger.info("Changing brightness gradually (system has been running for a while).")
            step_brightness = True
    else:
        logger.info("Changing brightness at once (-f or --force was given).")
    # Change the brightness of the configured display(s).
    if is_it_dark_outside(latitude=float(config['location']['latitude']),
                          longitude=float(config['location']['longitude']),
                          elevation=float(config['location']['elevation'])):
        for controller in config['controllers']:
            controller.decrease_brightness(10 if step_brightness else 100)
    else:
        for controller in config['controllers']:
            controller.increase_brightness(10 if step_brightness else 100)


def load_config():
    """
    Load settings from the given configuration file.

    :param pathname: The pathname of the configuration file (a string).
    :returns: A dictionary with the configured location and display
              brightness controllers.
    :raises: :py:exc:`ConfigurationError` when the parsing or validation of the
             configuration file fails.
    """
    parser = ConfigParser.ConfigParser()
    config = {'location': {}, 'controllers': []}
    loaded_files = parser.read(map(os.path.expanduser, CONFIG_FILES))
    if not loaded_files:
        msg = "No configuration files loaded! Please review the documentation on how to get started!"
        raise ConfigurationError(msg)
    logger.debug("Loading configuration file(s): %s", concatenate(loaded_files))
    for section in parser.sections():
        options = dict(parser.items(section))
        if section == 'location':
            config['location'].update(options)
        else:
            tag, _, friendly_name = section.partition(':')
            if tag != 'display':
                msg = "Unsupported section %r in configuration file!"
                raise ConfigurationError(msg % section)
            if 'output-name' in options:
                config['controllers'].append(SoftwareBrightnessController(
                    friendly_name=friendly_name,
                    minimum_percentage=int(options['min-brightness']),
                    maximum_percentage=int(options['max-brightness']),
                    output_name=options['output-name'],
                ))
            elif 'sys-directory' in options:
                config['controllers'].append(BacklightBrightnessController(
                    friendly_name=friendly_name,
                    minimum_percentage=int(options['min-brightness']),
                    maximum_percentage=int(options['max-brightness']),
                    sys_directory=options['sys-directory'],
                ))
            else:
                msg = "Don't know how to control brightness of %r display defined in configuration file!"
                raise ConfigurationError(msg % friendly_name)
    # Make sure the configuration file defines the essential settings.
    expected_location_keys = ('latitude', 'longitude', 'elevation')
    if not all(k in config['location'] for k in expected_location_keys):
        msg = "You need to define the %s options in the [location] section of the configuration file!"
        raise ConfigurationError(msg % concatenate(map(repr, expected_location_keys)))
    if not config['controllers']:
        msg = "You need to define one or more displays in the configuration file!"
        raise ConfigurationError(msg)
    return config


def find_system_uptime():
    """
    Find the uptime of the system by parsing ``/proc/uptime``.

    :returns: The number of seconds the system has been running (a floating
              point number).
    """
    with open('/proc/uptime') as handle:
        tokens = handle.read().split()
        return float(tokens[0])


def is_it_dark_outside(latitude, longitude, elevation):
    """
    Check whether it is dark outside (using `PyEphem <http://rhodesmill.org/pyephem/>`_).

    :param latitude: The latitude of the current location (a floating point
                     number).
    :param longitude: The longitude of the current location (a floating point
                      number).
    :param elevation: The elevation of the current location in meters (an
                      integer number).
    :returns: ``True`` during the night, ``False`` during the day.
    """
    # Two notes about the following tricky date/time manipulation:
    #
    #  1. PyEphem works exclusively with UTC date/time objects as mentioned in
    #     its documentation: "Dates always use Universal Time, never your local
    #     time zone." [1]
    #
    #  2. We want to find the sunrise and sunset of today so we have to convert
    #     the current date/time to noon on the same day, this involves a
    #     combination of UTC and local time... This may seem confusing at
    #     first, but we want to respect daylight saving time despite PyEphem
    #     using UTC! [2]
    #
    # [1] http://rhodesmill.org/pyephem/quick.html#dates
    # [2] http://en.wikipedia.org/wiki/Daylight_saving_time
    time_in_utc = datetime.datetime.utcnow()
    logger.debug("Current time: %s", format_utc_as_local(time_in_utc))
    # Convert the current UTC date/time to noon based on the local time.
    local_time = datetime.datetime.now()
    if local_time.hour >= 12:
        noon_in_utc = time_in_utc - datetime.timedelta(hours=local_time.hour - 12,
                                                       minutes=local_time.minute,
                                                       seconds=local_time.second)
    else:
        noon_in_utc = time_in_utc + datetime.timedelta(hours=12 - local_time.hour,
                                                       minutes=local_time.minute,
                                                       seconds=local_time.second)
    logger.debug("Noon today: %s", format_utc_as_local(noon_in_utc))
    # Use PyEphem to calculate sunrise and sunset (in UTC).
    observer = ephem.Observer()
    observer.date = noon_in_utc.strftime("%Y-%m-%d %H:%M:%S")
    observer.lat = str(latitude)
    observer.lon = str(longitude)
    observer.elev = elevation
    # Find the sunrise and sunset today (whether in the past or future).
    sunrise = observer.previous_rising(ephem.Sun()).datetime()
    logger.debug("Sunrise today: %s", format_utc_as_local(sunrise))
    sunset = observer.next_setting(ephem.Sun()).datetime()
    logger.debug("Sunset today: %s", format_utc_as_local(sunset))
    if sunrise < time_in_utc < sunset:
        logger.info("Based on your location it should be light outside right now.")
        return False
    else:
        logger.info("Based on your location it should be dark outside right now.")
        return True


def format_utc_as_local(utc):
    """
    Shortcut to format a UTC date time as a user friendly local date time string.

    :param utc: A :py:class:`datetime.datetime` object in UTC.
    :returns: A human readable date time string in the current system's local
              timezone.
    """
    return utc_to_local(utc).strftime("%Y-%m-%d %H:%M:%S")


def utc_to_local(utc):
    """
    Convert a date time in UTC to the current system's local timezone.

    :param utc: A :py:class:`datetime.datetime` object in UTC.
    :returns: A :py:class:`datetime.datetime` object in the local timezone.

    Regrettably the Python standard library doesn't offer a function that does
    this. The implementation of :py:func:`utc_to_local()` was based on the
    StackOverflow thread `Convert UTC datetime string to local datetime
    <http://stackoverflow.com/a/19238551/788200>`_.
    """
    epoch = time.mktime(utc.timetuple())
    offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
    return utc + offset


class BrightnessController(object):

    """
    Abstract base class for generic computer display brightness control logic.

    Classes that inherit from :py:class:`BrightnessController` are expected to
    implement the following methods:

    - :py:func:`get_current_brightness()`
    - :py:func:`get_maximum_brightness()`
    - :py:func:`change_brightness()`
    - :py:func:`round_brightness()`
    """

    def __init__(self, friendly_name, minimum_percentage=0, maximum_percentage=100):
        """
        Construct a brightness controller.

        :param friendly_name: A user friendly name (description) of the display
                              whose brightness is being controlled (a string).
        :param minimum_percentage: The brightness of the display is not allowed
                                   to be set lower than this percentage (a
                                   number between 0 and 100).
        :param maximum_percentage: The brightness of the display is not allowed
                                   to be set higher than this percentage (a
                                   number between 0 and 100).
        """
        self.friendly_name = friendly_name
        self.minimum_percentage = minimum_percentage
        self.maximum_percentage = maximum_percentage

    def __str__(self):
        """
        Render a user friendly representation of the display brightness controller.

        :returns: The user friendly name (description) of the display.
        """
        return self.friendly_name

    def increase_brightness(self, step_size=10):
        """
        Increase the brightness of the display by the given percentage.

        :param step_size: The percentage to increase the brightness with (a
                          number).
        :returns: ``True`` when the brightness was changed, ``False`` if it
                  wasn't (this happens when the percentage and rounding don't
                  result in a different brightness value).
        """
        # Get the raw value of the current brightness.
        current_brightness = self.get_current_brightness()
        # Calculate the old and new brightness percentage.
        old_percentage = self.brightness_to_percentage(current_brightness)
        new_percentage = old_percentage + step_size
        # Normalize the new percentage & convert it to a raw value.
        new_percentage, new_brightness = self.normalize_brightness(new_percentage)
        # Only set the new brightness if our calculation resulted in a
        # different brightness value (there's no point in calling xrandr or
        # invoking kernel mechanisms when nothing will change).
        if new_brightness != current_brightness:
            logger.debug("Increasing brightness of %s by %i%% (to %i%%) ..",
                         self.friendly_name, step_size, new_percentage)
            self.change_brightness(new_brightness)
            return True
        else:
            logger.info("Brightness of %s is already high enough.", self.friendly_name)
            return False

    def decrease_brightness(self, step_size=10):
        """
        Decrease the brightness of the display by the given percentage.

        :param step_size: The percentage to decrease the brightness with (a
                          number).
        :returns: ``True`` when the brightness was changed, ``False`` if it
                  wasn't (this happens when the percentage and rounding don't
                  result in a different brightness value).
        """
        # Get the raw value of the current brightness.
        current_brightness = self.get_current_brightness()
        # Calculate the old and new brightness percentage.
        old_percentage = self.brightness_to_percentage(current_brightness)
        new_percentage = old_percentage - step_size
        # Normalize the new percentage & convert it to a raw value.
        new_percentage, new_brightness = self.normalize_brightness(new_percentage)
        # Only set the new brightness if our calculation resulted in a
        # different brightness value (there's no point in calling xrandr or
        # invoking kernel mechanisms when nothing will change).
        if new_brightness != current_brightness:
            logger.info("Decreasing brightness of %s by %i%% (to %i%%) ..",
                        self.friendly_name, step_size, new_percentage)
            self.change_brightness(new_brightness)
            return True
        else:
            logger.info("Brightness of %s is already low enough.", self.friendly_name)
            return False

    def brightness_to_percentage(self, brightness):
        """
        Convert a raw brightness value to a percentage.

        :param value: The raw brightness value (a number).
        :returns: The brightness percentage (a number between 0 and 100).
        """
        return brightness / (self.get_maximum_brightness() / 100.0)

    def percentage_to_brightness(self, percentage):
        """
        Convert a brightness percentage to a raw value.

        :param value: The brightness percentage (a number).
        :returns: The raw brightness value (a number).
        """
        return percentage * (self.get_maximum_brightness() / 100.0)

    def normalize_brightness(self, percentage):
        """
        Normalize the given brightness percentage and convert it to a raw brightness value.

        :param percentage: The brightness percentage (a number between 0 and 100).
        :returns: The raw brightness value (a number).
        """
        percentage = max(percentage, self.minimum_percentage)
        percentage = min(percentage, self.maximum_percentage)
        raw_value = self.percentage_to_brightness(percentage)
        raw_value = self.round_brightness(raw_value)
        return percentage, raw_value

    def get_current_brightness(self):
        """
        Get the current brightness of the display (as a raw value).

        This method should be implemented by subclasses of
        :py:class:`BrightnessController`.

        :returns: An integer or floating point number representing the current
                  brightness.
        """
        raise NotImplementedError()

    def get_maximum_brightness(self):
        """
        Get the maximum brightness of the display (as a raw value).

        This method should be implemented by subclasses of
        :py:class:`BrightnessController`.

        :returns: An integer or floating point number representing the maximum
                  brightness.
        """
        raise NotImplementedError()

    def change_brightness(self, raw_brightness):
        """
        Change the brightness of the display.

        This method should be implemented by subclasses of
        :py:class:`BrightnessController`.

        :param raw_brightness: An integer or floating point number representing
                               the brightness to be configured.
        """
        raise NotImplementedError()

    def round_brightness(self, raw_brightness):
        """
        Round the given brightness (a raw value) to an acceptable value.

        This method should be implemented by subclasses of
        :py:class:`BrightnessController`.

        :param raw_brightness: An integer or floating point number representing
                               the brightness to be configured.
        :returns: An integer or floating point number rounded to an acceptable
                  value.
        """
        raise NotImplementedError()


class SoftwareBrightnessController(BrightnessController):

    """
    Display brightness controller that uses xrandr_ to control display brightness.

    This brightness controller uses the ``xrandr`` program to implement a
    software only modification of display brightness. The main advantage of
    this approach is that it will (should) always work. The disadvantage is
    that it won't dim the back light of the screen. In other words, if you can
    get :py:class:`BacklightBrightnessController` to work for your display it's
    likely preferable to :py:class:`SoftwareBrightnessController`.

    .. _xrandr: http://linux.die.net/man/1/xrandr
    """

    def __init__(self, **kw):
        """
        Construct a software brightness controller.

        Takes the same arguments as :py:func:`BrightnessController.__init__()`.
        Additionally takes the following arguments:

        :param output_name: The name that ``xrandr`` uses to refer to the
                            display (a string). This name can be obtained by
                            running the command ``xrandr --query``.
        """
        self.output_name = kw.pop('output_name')
        super(SoftwareBrightnessController, self).__init__(**kw)

    def get_current_brightness(self):
        """
        Get the current brightness of the display (as a raw value).

        This method uses the ``xrandr --query --verbose`` command to determine
        the current brightness of the display.

        :returns: A floating point number representing the current
                  brightness.
        """
        current_output = None
        listing = execute('xrandr', '--query', '--verbose', capture=True)
        for line in listing.splitlines():
            # Check for a line that introduces a new output, something like:
            # eDP1 connected 1440x900+0+0 (0x49) normal (...) 30mm x 179mm
            output_match = re.match(r'^(\w+)\s+connected\s+', line, re.IGNORECASE)
            if output_match:
                current_output = output_match.group(1)
                continue
            if current_output and current_output.lower() == self.output_name.lower():
                # Check for a line with the current brightness of an output,
                # something like `Brightness: 0.50' (with a <Tab> in front).
                brightness_match = re.match(r'^\s*Brightness:\s+(\d+(\.\d+)?)', line, re.IGNORECASE)
                if brightness_match:
                    return float(brightness_match.group(1))
        msg = "Failed to determine brightness of output %r in 'xrandr' output!"
        raise Exception(msg % self.output_name)

    def get_maximum_brightness(self):
        """
        Get the maximum brightness of the display (as a raw value).

        This method returns the hard coded number 1.0. Technically ``xrandr``
        accepts values above 1.0 but you most likely don't want to try that out
        because your display's colors will become over-saturated.

        :returns: A floating point number representing the maximum
                  brightness.
        """
        return 1.0

    def round_brightness(self, raw_brightness):
        """
        Round the given brightness (a raw value) to an acceptable value.

        :param raw_brightness: A floating point number representing the
                               brightness to be configured.
        :returns: A floating point number rounded to an acceptable value.
        """
        return round(float(raw_brightness), 2)

    def change_brightness(self, raw_brightness):
        """
        Change the brightness of the display.

        This method uses the ``xrandr --output ... --brightness X.Y`` command
        to change the brightness of the display.

        :param raw_brightness: A floating point number between 0.00 and 1.00
                               representing the brightness to be configured.
        """
        logger.debug("Setting brightness of %s to %s (raw value) ..", self.friendly_name, raw_brightness)
        execute('xrandr', '--output', self.output_name, '--brightness', '%.2f' % float(raw_brightness))


class BacklightBrightnessController(BrightnessController):

    """
    Display brightness controller that uses `/sys/class/backlight`_ to control backlight brightness.

    This brightness controller uses the Linux sysfs_ virtual file system to
    control the back light of laptop screens. It has only been tested on my
    MacBook Air however the ``/sys/class/backlight`` interface appears to be
    very simple which makes me suspect that this implementation is likely to
    work for quite a few laptops / back lights.

    .. _/sys/class/backlight: https://www.kernel.org/doc/Documentation/ABI/stable/sysfs-class-backlight
    .. _sysfs: http://en.wikipedia.org/wiki/Sysfs
    """

    def __init__(self, **kw):
        """
        Construct a back light brightness controller.

        Takes the same arguments as :py:func:`BrightnessController.__init__()`.
        Additionally takes the following arguments:

        :param sys_directory: The pathname of the ``/sys/class/backlight``
                              subdirectory to be used (a string).
        """
        self.sys_directory = kw.pop('sys_directory')
        self.max_brightness = None
        super(BacklightBrightnessController, self).__init__(**kw)

    def get_current_brightness(self):
        """
        Get the current brightness of the display (as a raw value).

        This method reads the actual brightness from
        ``/sys/class/backlight/<name>/actual_brightness``.

        :returns: An integer number representing the current brightness.
        """
        filename = os.path.join(self.sys_directory, 'actual_brightness')
        logger.debug("Reading %s ..", filename)
        with open(filename) as handle:
            return int(handle.read())

    def get_maximum_brightness(self):
        """
        Get the maximum brightness of the display (as a raw value).

        This method reads the maximum brightness from
        ``/sys/class/backlight/<name>/max_brightness``.

        :returns: An integer number representing the maximum brightness.
        """
        if self.max_brightness is None:
            filename = os.path.join(self.sys_directory, 'max_brightness')
            logger.debug("Reading %s ..", filename)
            with open(filename) as handle:
                self.max_brightness = int(handle.read())
        return self.max_brightness

    def round_brightness(self, raw_brightness):
        """
        Round the given brightness (a raw value) to an acceptable value.

        :param raw_brightness: A floating point number representing the
                               brightness to be configured.
        :returns: An integer number.
        """
        return int(raw_brightness)

    def change_brightness(self, raw_brightness):
        """
        Change the brightness of the display.

        This method writes the brightness to
        ``/sys/class/backlight/<name>/brightness``.

        :param raw_brightness: A number representing the brightness to be
                               configured.
        """
        logger.debug("Setting brightness of %s to %s (raw value) ..", self.friendly_name, raw_brightness)
        try:
            filename = os.path.join(self.sys_directory, 'brightness')
            logger.debug("Writing %s ..", filename)
            with open(filename, 'w') as handle:
                handle.write(str(int(raw_brightness)))
        except IOError as e:
            if e.errno == errno.EACCES:
                # Give a user friendly explanation.
                raise IOError(e.errno, compact("""
                    To control backlight brightness you need super user privileges!
                    (consider using `sudo' to run the program?)
                """))
            # Don't swallow errors we don't know what to do with.
            raise


class ConfigurationError(Exception):

    """Raised by :py:func:`load_config()` when a known configuration issue is detected."""
