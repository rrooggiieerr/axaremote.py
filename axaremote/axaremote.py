"""
Implements the AXA Remote class for controlling AXA Remote window openers.

Created on 12 Nov 2022

@author: Rogier van Staveren
"""

import logging
import time
from abc import ABC

import serial

from axaremote.axaconnection import (
    AXAConnection,
    AXAConnectionError,
    AXASerialConnection,
    AXATelnetConnection,
)

logger = logging.getLogger(__name__)

_BUSY_TIMEOUT = 1


class AXARemoteError(Exception):
    """Generic AXA Remote error."""

    def __init__(self, command=None):
        self.command = command


class EmptyResponseError(AXARemoteError):
    """
    Empty response error.

    If the response is empty.
    """

    def __str__(self):
        return f"Empty response for command '{self.command}'"


class InvallidResponseError(AXARemoteError):
    """
    Invalid response error.

    If the response format does not match the expected format.
    """

    def __init__(self, command=None, response=None):
        super().__init__(command)
        self.response = response

    def __str__(self):
        return (
            f"Invalid response for command '{self.command}'. response: {self.response}"
        )


class TooBusyError(AXARemoteError):
    """
    Too busy error.

    If the serial connection is to busy with processing other commands.
    """

    def __str__(self):
        return f"Too busy to send '{self.command}'"


class AXARemote(ABC):
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
        STATUS_DISCONNECTED: "Disconnected",
        STATUS_STOPPED: "Stopped",
        STATUS_LOCKED: "Locked",
        STATUS_UNLOCKING: "Unlocking",
        STATUS_OPENING: "Opening",
        STATUS_OPEN: "Open",
        STATUS_CLOSING: "Closing",
        STATUS_LOCKING: "Locking",
    }

    _connection = None
    _busy: bool = False
    _init: bool = True

    device: str = None
    version: str = None
    unique_id: str = None

    # Time in seconds to close, lock, unlock and open the AXA Remote
    _TIME_UNLOCK = 5
    _TIME_OPEN = 42
    _TIME_CLOSE = _TIME_OPEN
    _TIME_LOCK = 16

    _raw_status: int = RAW_STATUS_STRONG_LOCKED
    _status: int = STATUS_DISCONNECTED
    _position: float = 0.0  # 0.0 is closed, 100.0 is fully open
    _timestamp: float = None

    def __init__(
        self,
        connection: AXAConnection,
    ):
        """
        Initialises the AXARemote object.
        """
        assert connection is not None

        self._connection = connection

    def restore_position(self, position: float) -> None:
        """
        Restores the position of the window opener, mainly introduced to restore
        the window opener state in Home Assistant.

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
        if self._connection and not self._connection.is_open:
            logger.info("Connecting to %s", self._connection)
            try:
                self._connection.open()
                self._connection.write(b"\r\n")
                self._connection.reset()
            except AXAConnectionError as ex:
                logger.error(
                    "Problem communicating with %s, reason: %s", self._connection, ex
                )
                return False

        if self._connection and self._connection.is_open:
            return True

        return False

    def connect(self) -> bool:
        """
        Connect to the window opener.
        """
        if not self._connect():
            return False

        if not self._init:
            return True

        try:
            response = self._send_command("DEVICE")
            if response is None:
                return False

            response = self._split_response(response)
            if response[0] != self.RAW_STATUS_DEVICE:
                return False
            self.device = response[1]

            response = self._send_command("VERSION")
            if response is None:
                return False

            response = self._split_response(response)
            if response[0] != self.RAW_STATUS_VERSION:
                return False
            self.version = response[1].split(maxsplit=1)[1]

            self._init = False

            raw_status = self.raw_status()[0]
            if raw_status == self.RAW_STATUS_STRONG_LOCKED:
                self._status = self.STATUS_LOCKED
                self._position = 0.0
            elif raw_status == self.RAW_STATUS_WEAK_LOCKED:
                # Currently handling this state as if it's Strong Locked
                self._status = self.STATUS_LOCKED
                self._position = 0.0
            else:
                self._status = self.STATUS_OPEN
                self._position = 100.0

            return True
        except AXAConnectionError as ex:
            logger.error(
                "Problem communicating with %s, reason: %s", self._connection, ex
            )
            return False
        except AXARemoteError as ex:
            logger.error(ex)
            return False

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

        if not self._connect():
            logger.error("Connection not available")
            return None

        start_time = time.time()
        while self._busy is True:
            if time.time() - start_time > _BUSY_TIMEOUT:
                logger.error("Too busy for %s", command)
                raise TooBusyError(command)
            logger.debug("Busy")
            time.sleep(0.05)
        self._busy = True

        try:
            self._connection.reset()

            command = command.upper()
            logger.debug("Command: '%s'", command)
            # self._connection.write(b"\r\n")
            # self._connection.reset()
            self._connection.write(f"{command}\r\n".encode("ascii"))
            self._connection.flush()

            empty_line_count = 0
            echo_received = None
            while True:
                if empty_line_count > 5:
                    if self._init:
                        logger.error(
                            "More than 5 empty responses, is your cable right?"
                        )
                    else:
                        logger.error("More than 5 empty responses")
                    raise EmptyResponseError(command)

                response = self._connection.readline()
                response = response.decode().strip(" \n\r")
                if response == "":
                    # Sometimes we first receive an empty line
                    logger.debug("Empty line")
                    empty_line_count += 1
                    time.sleep(0.05)
                    continue

                if not echo_received and response == command:
                    # Command echo
                    logger.debug("Command successfully sent")
                    echo_received = True
                    continue

                if not echo_received:
                    logger.error(
                        "No command echo received, response: %s", repr(response)
                    )
                    raise InvallidResponseError(command, response)

                logger.debug("Response: %s", repr(response))
                return response
        except UnicodeDecodeError as ex:
            logger.warning(
                "Error during response decode, invalid response: %s, reason: %s",
                repr(response),
                ex,
            )
            raise InvallidResponseError(command, response) from ex
        except AXAConnectionError as ex:
            logger.error(
                "Problem communicating with %s, reason: %s", self._connection, ex
            )
            return None
        finally:
            self._busy = False

    def _split_response(self, response: str):
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
                self._timestamp = time.time() - (
                    self._TIME_UNLOCK + (self._TIME_OPEN * (self._position / 100))
                )
                self._status = self.STATUS_OPENING
            return True

        return False

    def stop(self) -> bool:
        """
        Stop the window.
        """
        if self._status == self.STATUS_LOCKING:
            return True

        response = self._send_command("STOP")
        response = self._split_response(response)

        if response[0] == self.RAW_STATUS_OK:
            if self._status in [self.STATUS_OPENING, self.STATUS_CLOSING]:
                self._status = self.STATUS_STOPPED
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
                self._timestamp = time.time() - (
                    self._TIME_CLOSE * ((100 - self._position) / 100)
                )
                self._status = self.STATUS_CLOSING

            return True

        return False

    def raw_status(self) -> int:
        """
        Returns the status as given by the AXA Remote
        """
        response = self._send_command("STATUS")
        response = self._split_response(response)

        return response

    def sync_status(self) -> None:
        """
        Synchronises the raw state with the presumed state.
        """
        if self._status == self.STATUS_DISCONNECTED and not self.connect():
            logger.debug("Device is still offline")
            return

        try:
            raw_state = self.raw_status()[0]
            logger.debug("Raw state: %s", raw_state)
            logger.debug("Presumed state: %s", self.STATUSES[self._status])
            if raw_state is None:
                # Device is offline
                self._status = self.STATUS_DISCONNECTED
                return

            if raw_state in [
                self.RAW_STATUS_STRONG_LOCKED,
                self.RAW_STATUS_WEAK_LOCKED,
            ] and self._status in [self.STATUS_UNLOCKING, self.STATUS_LOCKING]:
                self._position = 0.0
            elif (
                raw_state
                in [self.RAW_STATUS_STRONG_LOCKED, self.RAW_STATUS_WEAK_LOCKED]
                and self._status == self.STATUS_CLOSING
            ):
                self._status = self.STATUS_LOCKING
                self._position = 0.0
            elif (
                raw_state == self.RAW_STATUS_UNLOCKED
                and self._status == self.STATUS_UNLOCKING
            ):
                self._status = self.STATUS_OPENING
                self._position = 0.0
            elif (
                raw_state == self.RAW_STATUS_UNLOCKED
                and self._status == self.STATUS_LOCKED
            ):
                logger.info("Raw state and presumed state not in sync, syncronising")
                self._timestamp = time.time() - self._TIME_UNLOCK
                self._status = self.STATUS_OPENING
                self._position = 0.0
            elif (
                raw_state
                in [self.RAW_STATUS_STRONG_LOCKED, self.RAW_STATUS_WEAK_LOCKED]
                and self._status == self.STATUS_OPEN
            ):
                logger.info("Raw state and presumed state not in sync, syncronising")
                self._timestamp = time.time() - self._TIME_CLOSE
                self._status = self.STATUS_LOCKING
                self._position = 0.0
            elif raw_state in [
                self.RAW_STATUS_STRONG_LOCKED,
                self.RAW_STATUS_WEAK_LOCKED,
            ] and self._status not in [
                self.STATUS_LOCKED,
                self.STATUS_UNLOCKING,
                self.STATUS_CLOSING,
                self.STATUS_LOCKING,
            ]:
                logger.info("Raw state and presumed state not in sync, syncronising")
                self._status = self.STATUS_LOCKED
                self._position = 0.0
            elif raw_state == self.RAW_STATUS_UNLOCKED and self._status in [
                self.STATUS_LOCKED,
            ]:
                logger.info("Raw state and presumed state not in sync, syncronising")
                self._status = self.STATUS_OPEN
                self._position = 100.0
        except AXARemoteError as ex:
            logger.error(ex)
        except AXAConnectionError as ex:
            logger.error(
                "Problem communicating with %s, reason: %s", self._connection, ex
            )

    def status(self) -> int:
        """
        Returns the current status of the window opener.
        """
        self._update()

        return self._status

    def position(self) -> float:
        """
        Returns the current position of the window opener where 0.0 is totally
        closed and 100.0 is fully open.
        """
        self._update()

        return self._position


class AXARemoteSerial(AXARemote):
    """
    AXA Remote class for controlling AXA Remote window openers over a serial connection.
    """

    def __init__(self, serial_port: str) -> None:
        """
        Initializes the AXARemote object.
        """
        assert serial_port is not None

        self.unique_id = serial_port

        connection = AXASerialConnection(serial_port)

        super().__init__(connection)

    def _send_command(self, command: str) -> str | None:
        response = None

        try:
            response = super()._send_command(command)
        except serial.SerialException as ex:
            logger.exception(
                "Problem communicating with %s, reason: %s", self._connection, ex
            )
            response = None

        return response


class AXARemoteTelnet(AXARemote):
    """
    AXA Remote class for controlling AXA Remote window openers over a Telnet connection.
    """

    def __init__(self, host: str, port: int) -> None:
        """
        Initializes the AXARemote object.
        """
        assert host is not None
        assert port is not None

        self.unique_id = f"{host}:{port}"

        connection = AXATelnetConnection(host, port)

        super().__init__(connection)
