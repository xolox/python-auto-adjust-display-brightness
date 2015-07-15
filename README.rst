Automatically adjust Linux display brightness
=============================================

The ``auto-adjust-display-brightness`` program automatically adjusts the
brightness of Linux_ computer displays based on whether it's light or dark
outside. To get it working you create a configuration file defining your
physical location (this is how it figures out whether it's light or dark
outside) and how to manage the brightness of which displays (so it knows the
best way to control the brightness).

I'm a computer programmer and sometimes work through the evening and into the
night because it `enables deep concentration`_. During such evenings / nights a
recurring irritation was that I had to manually adjust the brightness of my
laptop screen and the external monitor attached to my laptop to avoid
unnecessary `eye strain`_. I'd been using xflux_ for years (it removes the blue
light from computer displays during the evening) but that doesn't dim the
backlight of my MacBook Air while I found this to be essential to avoid eye
strain.

.. contents::
   :local:

Installation
------------

The ``auto-adjust-display-brightness`` program is written in Python and is
available on PyPI_ which means installation should be as simple as::

  $ pip install auto-adjust-display-brightness

There's actually a multitude of ways to install Python packages (e.g. the `per
user site-packages directory`_, `virtual environments`_ or just installing
system wide) and I have no intention of getting into that discussion here, so
if this intimidates you then read up on your options before returning to these
instructions ;-).

Getting started
---------------

The ``auto-adjust-display-brightness`` program requires a configuration file
that defines your physical location (this is how it figures out whether it's
light or dark outside) and how to manage the brightness of which displays (so
it knows the best way to control the brightness). As an example here's the
configuration file that I'm using at the moment:

.. code-block:: ini

   # My physical location. I determined these values using Google Maps.
   [location]
   latitude = 53.240534499999995
   longitude = 6.614897599999949
   elevation = -2

   # The laptop screen of my MacBook Air. This controls the physical backlight
   # which is the best way to reduce the brightness (it also reduces power
   # consumption :-).
   [display:MacBook Air]
   min-brightness = 7
   max-brightness = 70
   sys-directory = /sys/class/backlight/acpi_video0

   # My external monitor connected via a display port to DVI adapter. I haven't
   # found any way to configure the physical backlight of this monitor so I'm
   # resorting to a software only modification here (better than nothing).
   [display:ASUS monitor]
   min-brightness = 30
   max-brightness = 60
   output-name = HDMI1

The configuration file is loaded from the following locations:

- ``~/.auto-adjust-display-brightness.ini``
- ``/etc/auto-adjust-display-brightness.ini``

The structure of the configuration file is as follows:

- The ``[location]`` section has three items, all of which are required
  (``latitude``, ``longitude`` and ``elevation``). Some hints on how to find
  the correct values:
  
  - You can find your latitude and longitude on `Google Maps`_.

  - Finding your elevation is a bit trickier: Google Maps has the required
    information but doesn't expose it. Fortunately there are `a dozen online
    tools`_ that make it easy to find your elevation.

- Each ``[display:...]`` section defines a computer display whose brightness
  should be controlled by the program:
  
  - The label after the ``display:`` tag is the name of the display (it's used
    in logging output but not otherwise significant, although it should of
    course be unique).

  - Displays may have a configured minimum brightness (``min-brightness``) and
    maximum brightness (``max-brightness``). These items default to 0% and 100%
    respectively (the values are percentages).

  - Currently two types of brightness control are supported:

    1. The physical brightness of the backlight of laptop screens. This uses
       the Linux sysfs_ virtual file system's `/sys/class/backlight`_ interface
       to control backlight brightness. The only required item is
       ``sys-directory`` which is expected to contain the absolute pathname of
       the directory that controls the backlight brightness of your laptop
       screen (you'll have to figure this out for yourself).

    2. The software brightness of any display using xrandr_ to apply a software
       only modification of display brightness. The main advantage of this
       approach is that it will (should) always work. The disadvantage is that
       it won't dim the back light of the screen. In other words, if you can
       get the other type of brightness control to work for your display it's
       likely preferable.

Running from cron
-----------------

To actually have your display brightness adjusted without manually running any
commands you can run ``auto-adjust-display-brightness`` from a cron schedule.
Here's what I'm currently using::

   # /etc/cron.d/auto-adjust-display-brightness:
   # Crontab entries for automatic adjustment of display brightness.

   DISPLAY=:0
   HOME=/home/peter
   VIRTUAL_ENV=/home/peter/.virtualenvs/auto-adjust-display-brightness

   @reboot root $VIRTUAL_ENV/bin/auto-adjust-display-brightness 1>/dev/null 2>&1
   * * * * * root $VIRTUAL_ENV/bin/auto-adjust-display-brightness 1>/dev/null 2>&1

Some notes about this crontab:

- The ``@reboot`` line is responsible for running the program straight after
  boot to avoid the display brightness starting in the wrong state and being
  decreased or increased gradually in the minutes after I've booted my laptop.
  When the program detects that it's being run less than 60 seconds after the
  system has booted it changes the brightness at once instead of gradually.

- The commands are run as ``root`` so that the program has the privileges
  required to write to ``/sys/class/backlight/acpi_video0`` (to control the
  physical backlight of my MacBook Air).

- The ``DISPLAY`` variable enables ``xrandr`` to work even though it's not
  being run from within my GUI environment.

- The ``HOME`` variable enables ``auto-adjust-display-brightness`` to find my
  configuration file without having to move it to
  ``/etc/auto-adjust-display-brightness.ini``. This enables me to track the
  configuration file in my private dotfiles git repository :-).

Contact
-------

The latest version of ``auto-adjust-display-brightness`` is available on PyPI_
and GitHub_. For bug reports please create an issue on GitHub_. If you have
questions, suggestions, etc. feel free to send me an e-mail at
`peter@peterodding.com`_.

License
-------

This software is licensed under the `MIT license`_.

© 2015 Peter Odding.

.. External references:
.. _/sys/class/backlight: https://www.kernel.org/doc/Documentation/ABI/stable/sysfs-class-backlight
.. _a dozen online tools: http://www.google.com/search?q=google+maps+find+altitude
.. _enables deep concentration: http://swizec.com/blog/why-programmers-work-at-night/swizec/3198
.. _eye strain: http://en.wikipedia.org/wiki/Asthenopia
.. _GitHub: https://github.com/xolox/python-auto-adjust-display-brightness
.. _Google Maps: https://maps.google.com
.. _Linux: http://en.wikipedia.org/wiki/Linux
.. _MIT license: http://en.wikipedia.org/wiki/MIT_License
.. _per user site-packages directory: https://www.python.org/dev/peps/pep-0370/
.. _peter@peterodding.com: mailto:peter@peterodding.com
.. _PyPI: https://pypi.python.org/pypi/auto-adjust-display-brightness
.. _sysfs: http://en.wikipedia.org/wiki/Sysfs
.. _virtual environments: http://docs.python-guide.org/en/latest/dev/virtualenvs/
.. _xflux: https://justgetflux.com/linux.html
.. _xrandr: http://linux.die.net/man/1/xrandr
