# Python library to control AXA Remote window openers.

![Python][python-shield]
[![GitHub Release][releases-shield]][releases]
[![Licence][license-badge]][license]  
[![Github Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

## Introduction

Python library to control AXA Remote window openers over the serial interface or serial to network
bridges like [esp-link](https://github.com/jeelabs/esp-link).

## Features

## Hardware

If you power the AXA Remote using batteries you can connect the Serial 3.3 or 5 Volts to position 1
or 6 of the RJ25 connector, ground to position 2 or 5 of the RJ25 connector and RX/TX to position 3
or 4. 
 
If you power the AXA Remote with the additional external power supply you can use a LIN-bus
controller to act as a level converter.

## Protocol

This are the protocol details:  

19200 baud 8N2  
Device command: `\r\nDEVICE\r\n`  
Version command: `\r\nVERSION\r\n`  
Status command: `\r\nSTATUS\r\n`  
Open command: `\r\nOPEN\r\n`  
Stop command: `\r\nSTOP\r\n`  
Close command: `\r\nCLOSE\r\n`

## Installation

You can install the Python AXA Remote library using the Python package manager PIP:

`pip3 install axaremote`

## axaremote CLI

You can use the Python AXA Remote library directly from the command line to open, stop or close
your window using the following syntax:

Status of the window: `python3 -m axaremote serial <serial port> status`  
Open the window: `python3 -m axaremote serial <serial port> open`  
Stop the window: `python3 -m axaremote serial <serial port> stop`  
Close the window: `python3 -m axaremote serial <serial port> close`

Or if your projector is connected using a serial to network bridge:

Status of the window: `python3 -m axaremote telnet <host> <port> status`  
Open the window: `python3 -m axaremote telnet <host> <port> open`  
Stop the window: `python3 -m axaremote telnet <host> <port> stop`  
Close the window: `python3 -m axaremote telnet <host> <port> close`

If you add the argument `--wait` to the open or close command the process will wait till the window
is open/close and show the progress.

### Troubleshooting

You can add the `--debug` flag to any CLI command to get a more details on what's going on. Like so:

`python3 -m axaremote serial <serial port> status --debug`

## Support my work

Do you enjoy using this Python library? Then consider supporting my work using one of the following
platforms:

[![Github Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

---

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[releases]: https://github.com/rrooggiieerr/axaremote.py/releases
[releases-shield]: https://img.shields.io/github/v/release/rrooggiieerr/axaremote.py?style=for-the-badge
[license]: ./LICENSE
[license-badge]: https://img.shields.io/github/license/rrooggiieerr/axaremote.py?style=for-the-badge
[paypal]: https://paypal.me/seekingtheedge
[paypal-shield]: https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white
[buymecoffee]: https://www.buymeacoffee.com/rrooggiieerr
[buymecoffee-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[github]: https://github.com/sponsors/rrooggiieerr
[github-shield]: https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=ea4aaa
[patreon]: https://www.patreon.com/seekingtheedge/creators
[patreon-shield]: https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white
