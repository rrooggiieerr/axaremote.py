"""
Created on 23 Nov 2022

@author: Rogier van Staveren
"""

import argparse
import logging
import sys
import time

from axaremote import AXARemoteError, AXARemoteSerial, AXARemoteTelnet, AXAStatus

_LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    # Read command line arguments
    argparser = argparse.ArgumentParser()

    subparsers = argparser.add_subparsers()

    serial_parser = subparsers.add_parser("serial")
    serial_parser.add_argument("serial_port")

    telnet_parser = subparsers.add_parser("telnet")
    telnet_parser.add_argument("host")
    telnet_parser.add_argument("port", type=int)

    argparser.add_argument(
        "action", choices=["status", "open", "close", "stop", "calibrate"]
    )
    argparser.add_argument(
        "--close-time",
        nargs="?",
        const=1,
        type=float,
        dest="close_time",
        required=False,
    )
    argparser.add_argument("--wait", dest="wait", action="store_true")
    argparser.add_argument("--debug", dest="debugLogging", action="store_true")

    args = argparser.parse_args()

    if args.debugLogging:
        logging.basicConfig(
            format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG
        )
    else:
        logging.basicConfig(format="%(message)s", level=logging.INFO)

    if "serial_port" in args:
        axa = AXARemoteSerial(args.serial_port)
    elif "host" in args:
        axa = AXARemoteTelnet(args.host, args.port)

    if "close_time" in args:
        axa.set_close_time(args.close_time)

    try:
        if not axa.connect():
            _LOGGER.error("Failed to connect to AXA Remote")
            sys.exit(1)

        _LOGGER.info("Device   : %s", axa.device)
        _LOGGER.info("Version  : %s", axa.version)

        if args.action == "status":
            status = axa.raw_status()
            _LOGGER.info("Status   : %s", status[1])
        elif args.action == "open":
            axa.restore_position(0.0)
            if axa.open():
                _LOGGER.info("AXA Remote is opening")
                if args.wait:
                    while True:
                        [status, position] = axa.sync_status()
                        if not args.debugLogging:
                            print(f"{status:9}: {position:5.1f} %", end="\r")
                        else:
                            _LOGGER.info("%s: %5.1f %%", status, position)
                        if status == AXAStatus.OPEN:
                            if not args.debugLogging:
                                print()
                            break
                        time.sleep(0.1)
        elif args.action == "close":
            axa.restore_position(100.0)
            if axa.close():
                _LOGGER.info("AXA Remote is closing")
                if args.wait:
                    while True:
                        [status, position] = axa.sync_status()
                        if not args.debugLogging:
                            print(f"{status:9}: {position:5.1f} %", end="\r")
                        else:
                            _LOGGER.info("%s: %5.1f %%", status, position)
                        if status == AXAStatus.LOCKED:
                            if not args.debugLogging:
                                print()
                            break
                        time.sleep(0.1)
        elif args.action == "stop":
            if axa.stop():
                _LOGGER.info("AXA Remote stopped")
        elif args.action == "calibrate":
            _LOGGER.info("Calibrating AXA Remote")
            axa.calibrate()
    except AXARemoteError as e:
        _LOGGER.error(
            "Error communicating with AXA Remote on %s, reason: %s", axa.connection, e
        )
        sys.exit(1)
    except KeyboardInterrupt:
        # Handle keyboard interrupt
        pass
    finally:
        axa.disconnect()

    sys.exit(0)
