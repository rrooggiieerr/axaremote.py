"""
Implements the AXA Remote class for controlling AXA Remote window openers.

Created on 12 Nov 2022

@author: Rogier van Staveren
"""

import logging
import time
from abc import ABC
from enum import Enum
from typing import Final

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
        return f"Invalid response for command '{self.command}'. response: {repr(self.response)}"


class TooBusyError(AXARemoteError):
    """
    Too busy error.

    If the connection is to busy with processing other commands.
    """

    def __str__(self):
        return f"Too busy to send '{self.command}'"


class AXARawStatus(Enum):
    """
    Status codes as returned by the AXA Remote
    """

    OK: Final = 200
    UNLOCKED: Final = 210
    STRONG_LOCKED: Final = 211
    WEAK_LOCKED: Final = 212
    DEVICE: Final = 260
    VERSION: Final = 261
    COMMAND_NOT_IMPLEMENTED: Final = 502

    def __str__(self):
        return {
            self.OK: "OK",
            self.UNLOCKED: "UnLocked",
            self.STRONG_LOCKED: "Strong Locked",
            self.WEAK_LOCKED: "Weak Locked",
            self.DEVICE: "Device",
            self.VERSION: "Firmware",
            self.COMMAND_NOT_IMPLEMENTED: "Command not implemented",
        }[self]


class AXAStatus(Enum):
    """
    To give better feedback some extra statuses are created
    """

    STOPPED: Final = 0
    LOCKED: Final = 1
    UNLOCKING: Final = 2
    OPENING: Final = 3
    OPEN: Final = 4
    CLOSING: Final = 5
    LOCKING: Final = 6

    def __str__(self):
        return {
            self.STOPPED: "Stopped",
            self.LOCKED: "Locked",
            self.UNLOCKING: "Unlocking",
            self.OPENING: "Opening",
            self.OPEN: "Open",
            self.CLOSING: "Closing",
            self.LOCKING: "Locking",
        }[self]


class AXARemote(ABC):
    """
    AXARemote basse class for interfacing with AXA Remote window openers.
    """

    connection: AXAConnection = None
    connected: bool = False
    busy: bool = False

    device: str = None
    version: str = None
    unique_id: str = None

    # Time in seconds to close, lock, unlock and open the AXA Remote
    _time_unlock: float = 5
    _time_open: float = 42
    _time_close: float = _time_open
    _time_lock: float = 16

    _raw_status: AXARawStatus = AXARawStatus.STRONG_LOCKED
    _status: AXAStatus = None
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

    def _is_initialised(self) -> bool:
        if self.version is None:
            return False
        return True

    def restore_position(self, position: float) -> None:
        """
        Restores the position of the window opener, mainly introduced to restore the window opener
        state in Home Assistant.

        Not to be used to move the window opener to a position.
        """
        assert 0.0 <= position <= 100.0

        self._position = position

        if self._position == 0.0:
            self._status = AXAStatus.LOCKED
        elif self._position == 100.0:
            self._status = AXAStatus.OPEN
        else:
            self._status = AXAStatus.STOPPED

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
        # pylint: disable=too-many-return-statements
        """
        Connect to the window opener.
        """
        if not self._connect():
            return False

        if self._is_initialised():
            return True

        try:
            response = self._send_command("DEVICE")
            response = self._split_response(response)
            if response[0] != AXARawStatus.DEVICE:
                return False
            self.device = response[1]

            response = self._send_command("VERSION")
            response = self._split_response(response)
            if response[0] != AXARawStatus.VERSION:
                return False
            self.version = response[1].split(maxsplit=1)[1]

            raw_status = self.raw_status()[0]
            if raw_status == AXARawStatus.STRONG_LOCKED:
                self._status = AXAStatus.LOCKED
                self._position = 0.0
            elif raw_status == AXARawStatus.WEAK_LOCKED:
                # Currently handling this state as if it's Strong Locked
                self._status = AXAStatus.LOCKED
                self._position = 0.0
            elif raw_status == AXARawStatus.UNLOCKED:
                self._status = AXAStatus.OPEN
                self._position = 100.0
            else:
                return False

            return True
        except AXAConnectionError as ex:
            logger.error(
                "Problem communicating with %s, reason: %s", self.connection, ex
            )
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
        Send a command to the AXA Remote.
        """
        if not self._connect():
            logger.error("Device is offline")
            self.connected = False
            return None

        start_time = time.time()
        while self.busy is True:
            if time.time() - start_time > _BUSY_TIMEOUT:
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
                    if not self._is_initialised():
                        logger.error(
                            "More than 5 empty responses, is your cable right?"
                        )
                    self.connection.write(b"\r\n")
                    self.connection.reset()
                    raise EmptyResponseError(command)

                response = self.connection.readline()
                response = response.decode(errors="ignore").strip(" \n\r")
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
                try:
                    if result[0].isdigit():
                        result[0] = AXARawStatus(int(result[0]))
                except ValueError as ex:
                    logger.warning(ex)
                return result

        return (None, response)

    def _update(self) -> None:
        """
        Calculates the position of the window opener based on the direction the window opener is
        moving.
        """
        if self._status in [
            AXAStatus.LOCKED,
            AXAStatus.STOPPED,
            AXAStatus.OPEN,
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
        if self._status == AXAStatus.UNLOCKING:
            if time_passed < self._time_unlock:
                self._position = (time_passed / self._time_unlock) * 100.0
            else:
                self._status = AXAStatus.OPENING
        if self._status == AXAStatus.OPENING:
            self._position = (
                (time_passed - self._time_unlock) / self._time_open
            ) * 100.0
            if time_passed > (self._time_unlock + self._time_open):
                self._status = AXAStatus.OPEN
                self._position = 100.0

        if self._status == AXAStatus.CLOSING:
            if time_passed < self._time_close:
                self._position = 100 - ((time_passed / self._time_close) * 100.0)
            else:
                self._status = AXAStatus.LOCKING
                self._target_position = None
        if self._status == AXAStatus.LOCKING:
            self._position = 100 - (
                ((time_passed - self._time_close) / self._time_lock) * 100.0
            )
            if time_passed > (self._time_close + self._time_lock):
                self._status = AXAStatus.LOCKED
                self._position = 0.0

        logger.debug("%s: %5.1f %%", self._status, self._position)

        if self._target_position is not None:
            try:
                if (
                    self._status == AXAStatus.OPENING
                    and self._position > self._target_position
                ) or (
                    self._status == AXAStatus.CLOSING
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

        if response[0] == AXARawStatus.OK:
            if self._status == AXAStatus.LOCKED:
                self._timestamp = time.time()
                self._status = AXAStatus.UNLOCKING
            elif self._status == AXAStatus.STOPPED:
                self._timestamp = time.time() - (
                    self._time_unlock + (self._time_open * (self._position / 100))
                )
                self._status = AXAStatus.OPENING
            return True

        return False

    def open(self) -> bool:
        """
        Opens the window opener.
        """
        self._target_position = 100.0
        return self._open()

    def _stop(self) -> bool:
        """
        Stop the window.
        """
        if self._status == AXAStatus.LOCKING:
            return True

        response = self._send_command("STOP")
        response = self._split_response(response)

        if response[0] == AXARawStatus.OK:
            if self._status in [AXAStatus.OPENING, AXAStatus.CLOSING]:
                self._status = AXAStatus.STOPPED

            self._target_position = None

            return True

        return False

    def stop(self) -> bool:
        """
        Stops the window opening.
        """
        self._target_position = self._position
        return self._stop()

    def _close(self) -> bool:
        """
        Close the window.
        """
        response = self._send_command("CLOSE")
        response = self._split_response(response)

        if response[0] == AXARawStatus.OK:
            if self._status == AXAStatus.OPEN:
                self._timestamp = time.time()
                self._status = AXAStatus.CLOSING
            elif self._status == AXAStatus.STOPPED:
                self._timestamp = time.time() - (
                    self._time_close * ((100 - self._position) / 100)
                )
                self._status = AXAStatus.CLOSING

            return True

        return False

    def close(self) -> bool:
        """
        Closes the window opener.
        """
        self._target_position = 0.0
        return self._close()

    def set_position(self, target_position: float) -> None:
        """
        Initiates the window opener to move to a given position.

        sync_status() needs to be called regularly to calculate the current position and stop the
        move once the given position is reaced.
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

    def set_close_time(self, close_time: float):
        """
        Sets the time needed to close the window from fully open to locked.

        This time is used to calculate the unlock, open and lock times.
        """
        assert close_time is not None
        assert close_time > 0

        self._time_unlock = 0
        self._time_open = 0
        self._time_close = close_time
        self._time_lock = 0

    def raw_status(self) -> AXARawStatus:
        """
        Returns the status as given by the AXA Remote.
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
            logger.debug("Presumed state: %s", self._status)
            if raw_state is None:
                return self.status()

            if self._target_position is None:
                if (
                    self._status == AXAStatus.LOCKED
                    and raw_state == AXARawStatus.UNLOCKED
                ):
                    logger.info(
                        "Raw state and presumed state not in sync, synchronising"
                    )
                    self._timestamp = time.time() - self._time_unlock
                    self._status = AXAStatus.OPENING
                    self._position = 0.0
                elif self._status == AXAStatus.OPEN and raw_state in [
                    AXARawStatus.STRONG_LOCKED,
                    AXARawStatus.WEAK_LOCKED,
                ]:
                    logger.info(
                        "Raw state and presumed state not in sync, synchronising"
                    )
                    self._timestamp = time.time() - self._time_close
                    self._status = AXAStatus.LOCKING
                    self._position = 0.0
                self._target_position = None
            else:
                # ToDo
                if raw_state in [
                    AXARawStatus.STRONG_LOCKED,
                    AXARawStatus.WEAK_LOCKED,
                ] and self._status in [AXAStatus.UNLOCKING, AXAStatus.LOCKING]:
                    self._position = 0.0
                elif (
                    raw_state in [AXARawStatus.STRONG_LOCKED, AXARawStatus.WEAK_LOCKED]
                    and self._status == AXAStatus.CLOSING
                ):
                    self._timestamp = time.time() - self._time_close
                    self._status = AXAStatus.LOCKING
                    self._position = 0.0
                    self._target_position = None
                elif (
                    raw_state == AXARawStatus.UNLOCKED
                    and self._status == AXAStatus.UNLOCKING
                ):
                    self._status = AXAStatus.OPENING
                    self._position = 0.0
                elif raw_state in [
                    AXARawStatus.STRONG_LOCKED,
                    AXARawStatus.WEAK_LOCKED,
                ] and self._status not in [
                    AXAStatus.LOCKED,
                    AXAStatus.UNLOCKING,
                    AXAStatus.CLOSING,
                    AXAStatus.LOCKING,
                ]:
                    logger.info(
                        "Raw state and presumed state not in sync, synchronising"
                    )
                    self._status = AXAStatus.LOCKED
                    self._position = 0.0
                elif raw_state == AXARawStatus.UNLOCKED and self._status in [
                    AXAStatus.LOCKED,
                ]:
                    logger.info(
                        "Raw state and presumed state not in sync, synchronising"
                    )
                    self._status = AXAStatus.OPEN
                    self._position = 100.0
        except (InvallidResponseError, EmptyResponseError) as ex:
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
        Returns the current position of the window opener where 0.0 is totally closed and 100.0 is
        fully open.
        """
        return self._position

    def calibrate(self):
        """
        Calibrates the AXA Remote window opener open time
        """
        # if self.open() and time.sleep(60) and self.close():
        if self.close():
            start = time.time()
            while True:
                try:
                    raw_state = self.raw_status()[0]
                    if raw_state in [
                        AXARawStatus.STRONG_LOCKED,
                        AXARawStatus.WEAK_LOCKED,
                    ]:
                        self._time_open = time.time() - start
                        logger.info("Open time is %.1f seconds", self._time_open)
                        return self._time_open
                    logger.debug("%.1f", time.time() - start)
                    if time.time() - start > 120:
                        logger.error("%.1f", time.time() - start)
                        break
                except AXARemoteError as ex:
                    logger.warning(ex)

        logger.error("Failed to calibrate")
        return None


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
