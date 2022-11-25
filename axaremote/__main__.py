"""
Created on 23 Nov 2022

@author: Rogier van Staveren
"""
import argparse
import logging
import sys
import time

from serial.serialutil import SerialException

from axaremote.axaremote import AXARemote

_LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    # Read command line arguments
    argparser = argparse.ArgumentParser()
    argparser.add_argument("port")
    argparser.add_argument("action", choices=["status", "open", "close", "stop"])
    argparser.add_argument("--wait", dest="wait", action="store_true")
    argparser.add_argument("--debug", dest="debugLogging", action="store_true")

    args = argparser.parse_args()

    if args.debugLogging:
        logging.basicConfig(
            format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG
        )
    else:
        logging.basicConfig(format="%(message)s", level=logging.INFO)

    axa = AXARemote(args.port)
    connected = False
    try:
        connected = axa.connect()
    except SerialException as e:
        _LOGGER.error(e)

    if not connected:
        _LOGGER.error("Failed to connect to AXA Remote")
        sys.exit(1)

    if args.action == "status":
        _LOGGER.info(axa.device)
        _LOGGER.info(axa.version)
        status = axa.raw_status()
        _LOGGER.info(status[1])
    elif args.action == "open":
        if axa.open():
            _LOGGER.info("AXA Remote is opening")
            if args.wait:
                while True:
                    status = axa.status()
                    position = axa.position()
                    if not args.debugLogging:
                        print(f"{axa.STATUSES[status]:9}: {position:5.1f} %", end="\r")
                    else:
                        _LOGGER.info("%s: %5.1f %%", axa.STATUSES[status], position)
                    if status == axa.STATUS_OPEN:
                        if not args.debugLogging:
                            print()
                        break
                    time.sleep(0.1)
    elif args.action == "close":
        if axa.close():
            _LOGGER.info("AXA Remote is closing")
            if args.wait:
                while True:
                    status = axa.status()
                    position = axa.position()
                    if not args.debugLogging:
                        print(f"{axa.STATUSES[status]:9}: {position:5.1f} %", end="\r")
                    else:
                        _LOGGER.info("%s: %5.1f %%", axa.STATUSES[status], position)
                    if status == axa.STATUS_LOCKED:
                        if not args.debugLogging:
                            print()
                        break
                    time.sleep(0.1)
    elif args.action == "stop":
        if axa.stop():
            _LOGGER.info("AXA Remote stopped")

    axa.disconnect()
    sys.exit(0)
