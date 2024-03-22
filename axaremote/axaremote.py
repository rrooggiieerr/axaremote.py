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
            f"Invalid response for command '{self.command}'. response: {repr(self.response)}"
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

    connection = None
    connected = False
    busy: bool = False

    device: str = None
    version: str = None
    unique_id: str = None

    # Time in seconds to close, lock, unlock and open the AXA Remote
    _TIME_UNLOCK = 5
    _TIME_OPEN = 42
    _TIME_CLOSE = _TIME_OPEN
    _TIME_LOCK = 16

    _init: bool = True
    _raw_status: int = RAW_STATUS_STRONG_LOCKED
    _status: int = None
    _position: float = 0.0  # 0.0 is closed, 100.0 is fully open
    _target_position: float = None
    _timestamp: float = None

    def __init__(
        self,
        connection: AXAConnection,
    ):
        """
        Initialises the AXARemote object.
        """
        assert connection is not None

        self.connection = connection

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
        if self.connection and not self.connection.is_open:
            logger.info("Connecting to %s", self.connection)
            try:
                self.connection.open()
                self.connection.write(b"\r\n")
                self.connection.reset()
            except AXAConnectionError as ex:
                logger.error(
                    "Problem communicating with %s, reason: %s", self.connection, ex
                )
                return False

        if self.connection and self.connection.is_open:
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
                "Problem communicating with %s, reason: %s", self.connection, ex
            )
            return False
        except AXARemoteError as ex:
            logger.error(ex)
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from the window opener.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None

        return True

    def _send_command(self, command: str) -> str | None:
        """
        Send a command to the AXA Remote
        """

        if not self._connect():
            logger.error("Device is offline")
            self.connected = False
            return None

        start_time = time.time()
        while self.busy is True:
            if time.time() - start_time > _BUSY_TIMEOUT:
                logger.error("Too busy for %s", command)
                raise TooBusyError(command)
            logger.debug("Busy")
            time.sleep(0.05)
        self.busy = True

        try:
            command = command.upper()
            logger.debug("Command: '%s'", command)
            self.connection.write(f"{command}\r\n".encode("ascii"))
            self.connection.flush()

            empty_line_count = 0
            echo_received = None
            while True:
                if empty_line_count > 5:
                    if self._init:
                        logger.error(
                            "More than 5 empty responses, is your cable right?"
                        )
                    self.connection.write(b"\r\n")
                    self.connection.reset()
                    raise EmptyResponseError(command)

                response = self.connection.readline()
                response = response.decode(errors='ignore').strip(" \n\r")
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
                    empty_line_count = 0
                    continue

                if not echo_received:
                    logger.warning(
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
                "Problem communicating with %s, reason: %s", self.connection, ex
            )
            return None
        finally:
            self.busy = False

    def _split_response(self, response: str):
        if response is not None:
            result = response.split(maxsplit=1)
            if len(result) == 2:
                if result[0].isdigit():
                    result[0] = int(result[0])
                return result

        return (None, response)

    def _update(self) -> None:
        """
        Calculates the position of the window opener based on the direction
        the window opener is moving.
        """
        if self._status in [
            self.STATUS_LOCKED,
            self.STATUS_STOPPED,
            self.STATUS_OPEN,
        ]:
            # Nothing to calculate here.
            if self._target_position is not None:
                try:
                    if self._position < self._target_position:
                        self._open()
                    elif self._position > self._target_position:
                        self._close()
                except AXARemoteError as ex:
                    logger.error(
                        "Problem communicating with %s, reason: %s", self.connection, ex
                    )
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
                self._target_position = None
        if self._status == self.STATUS_LOCKING:
            self._position = 100 - (
                ((time_passed - self._TIME_CLOSE) / self._TIME_LOCK) * 100.0
            )
            if time_passed > (self._TIME_CLOSE + self._TIME_LOCK):
                self._status = self.STATUS_LOCKED
                self._position = 0.0

        logger.debug("%s: %5.1f %%", self.STATUSES[self._status], self._position)

        if self._target_position is not None:
            try:
                if (
                    self._status == self.STATUS_OPENING
                    and self._position > self._target_position
                ) or (
                    self._status == self.STATUS_CLOSING
                    and self._position < self._target_position
                ):
                    self._stop()
            except AXARemoteError as ex:
                logger.error(
                    "Problem communicating with %s, reason: %s", self.connection, ex
                )

    def _open(self) -> bool:
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

    def open(self) -> bool:
        self._target_position = 100.0
        return self._open()

    def _stop(self) -> bool:
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

            self._target_position = None

            return True

        return False

    def stop(self) -> bool:
        self._target_position = self._position
        return self._stop()

    def _close(self) -> bool:
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

    def close(self) -> bool:
        self._target_position = 0.0
        return self._close()

    def set_position(self, target_position: float) -> None:
        """
        Initiates the window opener to move to a given position.

        sync_status() needs to be called regularly to calculate the current
        position and stop the move once the given position is reaced.
        """
        assert 0.0 <= target_position <= 100.0

        if int(target_position) == 0:
            self.close()
        elif int(target_position) == 100:
            self.open()
        elif int(self._position) == int(target_position):
            return
        elif self._position < target_position:
            self._target_position = target_position
            self._open()
        elif self._position > target_position:
            self._target_position = target_position
            self._close()

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
        if not self.connect():
            # Device is offline
            if self.connected:
                logger.debug("Device is offline")
            else:
                logger.debug("Device is still offline")
            self.connected = False
            return self.status()

        self.connected = True

        try:
            raw_state = self.raw_status()[0]
            logger.debug("Raw state: %s", raw_state)
            logger.debug("Presumed state: %s", self.STATUSES[self._status])
            if raw_state is None:
                return self.status()

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
                self._timestamp = time.time() - self._TIME_CLOSE
                self._status = self.STATUS_LOCKING
                self._position = 0.0
                self._target_position = None
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
                self._target_position = None
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
        except InvallidResponseError as ex:
            logger.warning(ex)
        except EmptyResponseError as ex:
            logger.warning(ex)
        except AXARemoteError as ex:
            logger.error(ex)
        except AXAConnectionError as ex:
            logger.error(
                "Problem communicating with %s, reason: %s", self.connection, ex
            )

        return self.status()

    def status(self) -> [int, float]:
        """
        Returns the current status of the window opener.
        """
        self._update()

        return [self._status, self._position]

    def position(self) -> float:
        """
        Returns the current position of the window opener where 0.0 is totally
        closed and 100.0 is fully open.
        """
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
