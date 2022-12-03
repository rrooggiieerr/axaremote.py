"""
Implements the AXA Remote class for controlling AXA Remote window openers.

Created on 12 Nov 2022

@author: Rogier van Staveren
"""
import logging
import time
from os import linesep

import serial

logger = logging.getLogger(__name__)


class AXARemote:
    """
    AXA Remote class for controlling AXA Remote window openers.
    """

    # Status codes as given by the AXA Remote
    RAW_STATUS_OK = 200
    RAW_STATUS_UNLOCKED = 210
    RAW_STATUS_STRONG_LOCKED = 211
    RAW_STATUS_WEAK_LOCKED = 212  # I have seen this state only once
    RAW_STATUS_DEVICE = 260
    RAW_STATUS_VERSION = 261
    RAW_STATUS_COMMAND_NOT_IMPLEMENTED = 502

    # To give better feedback some extra statuses are created
    STATUS_DISCONNECTED = -1
    STATUS_STOPPED = 0
    STATUS_LOCKED = 1
    STATUS_UNLOCKING = 2
    STATUS_OPENING = 3
    STATUS_OPEN = 4
    STATUS_CLOSING = 5
    STATUS_LOCKING = 6

    STATUSES = {
        STATUS_STOPPED: "Stopped",
        STATUS_LOCKED: "Locked",
        STATUS_UNLOCKING: "Unlocking",
        STATUS_OPENING: "Opening",
        STATUS_OPEN: "Open",
        STATUS_CLOSING: "Closing",
        STATUS_LOCKING: "Locking",
    }

    _connection = None
    _busy = False

    device = None
    version = None

    # Time in seconds to close, lock, unlock and open the AXA Remote
    _TIME_UNLOCK = 10
    _TIME_OPEN = 20
    _TIME_CLOSE = _TIME_OPEN
    _TIME_LOCK = _TIME_UNLOCK

    _raw_status = RAW_STATUS_STRONG_LOCKED
    _status = STATUS_DISCONNECTED
    _position = 0.0  # 0.0 is closed, 100.0 is fully open
    _timestamp = None

    def __init__(self, serial_port: str):
        """
        Initialises the AXARemote object.
        """
        assert serial_port is not None

        self._serial_port = serial_port

    def set_position(self, position: float) -> None:
        """
        Sets the initial position of the window opener, just like in the constructor.

        Mainly introduced to restore the window opener state in Home Assistant.

        Not to be used to move the window opener to a position
        """
        assert 0.0 <= position <= 100.0

        self._position = position

        if self._position == 0.0:
            self._status = self.STATUS_LOCKED
        elif self._position == 100.0:
            self._status = self.STATUS_OPEN
        else:
            self._status = self.STATUS_STOPPED

    def _connect(self) -> bool:
        if self._connection is None:
            connection = serial.Serial(
                port=self._serial_port,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=1,
            )

            # Open the connection
            if not connection.is_open:
                connection.open()

            self._connection = connection
        elif not self._connection.is_open:
            # Try to repair the connection
            self._connection.open()

        if not self._connection.is_open:
            return False

        return True

    def connect(self) -> bool:
        """
        Connect to the window opener.
        """
        if not self._connect():
            return False

        response = self._send_command("DEVICE")
        if response is None:
            return False

        response = self._split_response(response)
        if response[0] == self.RAW_STATUS_DEVICE:
            self.device = response[1]

        response = self._send_command("VERSION")
        response = self._split_response(response)
        if response[0] == self.RAW_STATUS_VERSION:
            self.version = response[1]

        raw_status = self.raw_status()
        if raw_status[0] == self.RAW_STATUS_STRONG_LOCKED:
            self._status = self.STATUS_LOCKED
            self._position = 0.0
        elif raw_status[0] == self.RAW_STATUS_WEAK_LOCKED:
            # Currently handling this state as if it's Strong Locked
            self._status = self.STATUS_LOCKED
            self._position = 0.0
        else:
            self._status = self.STATUS_OPEN
            self._position = 100.0

        return True

    def disconnect(self) -> bool:
        """
        Disconnect from the window opener.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

        return True

    def _send_command(self, command: str) -> str | None:
        """
        Send a command to the AXA Remote
        """

        if self._connect() is False:
            logger.error("Connection not available")
            return None

        while self._busy is True:
            logger.info("to busy for %s", command)
            time.sleep(0.1)
        self._busy = True

        response = None

        try:
            self._connection.reset_input_buffer()
            self._connection.reset_output_buffer()

            command = command.upper()
            logger.debug("Command: '%s'", command)
            self._connection.write(b"\r\n")
            self._connection.readline()
            self._connection.write(f"{command}\r\n".encode("ascii"))
            self._connection.flush()

            while True:

                response = self._connection.readlines()
                response = [s.decode() for s in response]
                response = [s.strip() for s in response]

                if len(response) == 0:
                    # empty line
                    logger.error("Empty response, is your cable right?")
                    response = None
                    break

                if response[0] == command:
                    # command echo
                    logger.debug("Command successfully send")
                    response.pop(0)
                else:
                    logger.error("No command echo received")
                    logger.error("Response: %s", response)
                    response = None
                    break

                if len(response) == 1:
                    response = response[0]
                else:
                    response = linesep.join(response)

                if response == "":
                    response = None

                logger.debug("Response: %s", response)
                break
        except serial.SerialException as e:
            logger.exception(
                "Problem communicating with %s, reason: %s", self._serial_port, e
            )
            response = None
        except UnicodeDecodeError as e:
            logger.warning(
                "Error during response decode, invalid response: %s, reason: %s",
                response.decode(errors="replace"),
                e,
            )
            response = None
        except Exception as ex:
            logger.exception("Unexpected exception: %s", ex)
            response = None
        finally:
            self._busy = False

        return response

    def _split_response(self, response):
        if response is not None:
            result = response.split(maxsplit=1)
            if len(result) == 2:
                result[0] = int(result[0])
                return result

        return (None, response)

    def _update(self) -> None:
        """
        Calculates the position of the window opener based on the direction
        the window opener is moving.
        """
        if self._status in [
            self.STATUS_DISCONNECTED,
            self.STATUS_LOCKED,
            self.STATUS_STOPPED,
            self.STATUS_OPEN,
        ]:
            # Nothing to calculate here.
            return

        time_passed = time.time() - self._timestamp
        if self._status == self.STATUS_UNLOCKING:
            if time_passed < self._TIME_UNLOCK:
                self._position = (time_passed / self._TIME_UNLOCK) * 100.0
            else:
                self._status = self.STATUS_OPENING
        if self._status == self.STATUS_OPENING:
            self._position = (
                (time_passed - self._TIME_UNLOCK) / self._TIME_OPEN
            ) * 100.0
            if time_passed > (self._TIME_UNLOCK + self._TIME_OPEN):
                self._status = self.STATUS_OPEN
                self._position = 100.0

        if self._status == self.STATUS_CLOSING:
            if time_passed < self._TIME_CLOSE:
                self._position = 100 - ((time_passed / self._TIME_CLOSE) * 100.0)
            else:
                self._status = self.STATUS_LOCKING
        if self._status == self.STATUS_LOCKING:
            self._position = 100 - (
                ((time_passed - self._TIME_CLOSE) / self._TIME_LOCK) * 100.0
            )
            if time_passed > (self._TIME_CLOSE + self._TIME_LOCK):
                self._status = self.STATUS_LOCKED
                self._position = 0.0

    def open(self) -> bool:
        """
        Open the window.
        """
        response = self._send_command("OPEN")
        response = self._split_response(response)

        if response[0] == self.RAW_STATUS_OK:
            if self._status == self.STATUS_LOCKED:
                self._timestamp = time.time()
                self._status = self.STATUS_UNLOCKING
            elif self._status == self.STATUS_STOPPED:
                self._status = self.STATUS_OPENING
            return True

        return False

    def stop(self) -> bool:
        """
        Stop the window.
        """
        # self._timestamp = time.time()
        response = self._send_command("STOP")
        response = self._split_response(response)

        if response[0] == self.RAW_STATUS_OK:
            return True

        return False

    def close(self) -> bool:
        """
        Close the window.
        """
        response = self._send_command("CLOSE")
        response = self._split_response(response)

        if response[0] == self.RAW_STATUS_OK:
            if self._status == self.STATUS_OPEN:
                self._timestamp = time.time()
                self._status = self.STATUS_CLOSING
            elif self._status == self.STATUS_STOPPED:
                self._status = self.STATUS_CLOSING

            return True

        return False

    def raw_status(self):
        """
        Returns the status as given by the AXA Remote
        """
        response = self._send_command("STATUS")
        response = self._split_response(response)

        return response

    def sync_status(self):
        """
        Synchronises the raw state with the presumed state.
        """
        if self._status == self.STATUS_DISCONNECTED and not self.connect():
            # Device is still offline
            return

        raw_state = self.raw_status()
        if raw_state[0] is None:
            # Device is offline
            self._status = self.STATUS_DISCONNECTED
            return

        if (
            raw_state[0] == self.RAW_STATUS_STRONG_LOCKED
            and self._status != self.STATUS_LOCKED
        ):
            logger.info("Raw state and presumed state not in sync, syncronising")
            self._status = self.STATUS_LOCKED
            self._position = 0.0
        elif (
            raw_state[0] == self.RAW_STATUS_UNLOCKED
            and self._status == self.STATUS_LOCKED
        ):
            logger.info("Raw state and presumed state not in sync, syncronising")
            self._status = self.STATUS_OPEN
            self._position = 100.0

    def status(self) -> int:
        """
        Returns the current status of the window opener.
        """
        self._update()

        return self._status

    def position(self) -> float:
        """
        Returns the current position of the window opener where 0.0 is totally
        up and 100.0 is fully down.
        """
        self._update()

        return self._position
