# Python library to controll AXA Remote window openers.
Python library to controll AXA Remote window openers over the serial
interface.

## Hardware
If you power the AXA Remote using batteries you can connect the Serial 3.3 or
5 Volts to position 1 or 6 of the RJ25 connector, ground to position 2 or 5 of
the RJ25 connector and RX/TX to position 3 or 4. 
 
If you power the AXA Remote with the aditional external power adapter you can
use a LIN-bus controller to act as a level converter.

## Protocol
This are the protocol details:\
19200 baud 8N2\
Device command : \r\nDEVICE\r\n\
Version command: \r\nVERSION\r\n\
Status command : \r\nSTATUS\r\n\
Open command   : \r\nOPEN\r\n\
Stop command   : \r\nSTOP\r\n\
Close command  : \r\nCLOSE\r\n

## Installation
You can install the Python AXA Remote library using the Python package manager
PIP:\
`pip3 install axaremote`

## axaremote CLI
You can use the Python AXA Remote library directly from the command line to
open, stop or close your window using the follwoing syntax:

Status of the window: `python3 -m axaremote <serial port> status`\
Open the window: `python3 -m axaremote <serial port> open`\
Stop the window: `python3 -m axaremote <serial port> stop`\
Close the window: `python3 -m axaremote <serial port> close`

If you add the argument `--wait` to the open or close command the process will
wait till the window is open/close and show the progress.