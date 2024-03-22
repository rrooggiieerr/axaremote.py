"""
Implements the connection types for connecting to AXA Remote window openers.

Created on 24 Aug 2023

@author: Rogier van Staveren
"""

import logging
import telnetlib
from abc import ABC, abstractmethod

import serial

logger = logging.getLogger(__name__)

_SERIAL_TIMEOUT = 1.0
_TELNET_TIMEOUT = 1.0


class AXAConnectionError(Exception):
    """
    AXA Connection Error.

    When an error occurs while connecting to the BenQ Projector.
    """


class AXAConnection(ABC):
    """
    Abstract class on which the different connection types are build.
    """

    is_open: bool = False

    @abstractmethod
    def open(self) -> bool:
        """
        Opens the connection to the AXA Remote.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> bool:
        """
        Closes the connection to the AXA Remote.
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> bool:
        """
        Resets the input and output buffers of the connection.
        """
        raise NotImplementedError

    @abstractmethod
    def readline(self) -> str:
        """
        Reads a line from the connection.
        """
        raise NotImplementedError

    def readlines(self) -> list[bytes]:
        """
        Reads all lines from the connection.
        """
        lines = []

        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)

        return lines

    @abstractmethod
    def write(self, data: str) -> bool:
        """
        Output the given string over the connection.
        """
        raise NotImplementedError

    def flush(self) -> None:
        """
        Flush write buffers, if applicable.
        """


class AXASerialConnection(AXAConnection):
    """
    Class to handle the serial connection type.
    """

    _connection = None

    def __init__(self, serial_port: str):
        assert serial_port is not None

        self._serial_port = serial_port

    def __str__(self):
        return self._serial_port

    def open(self) -> bool:
        try:
            if self._connection is None:
                connection = serial.Serial(
                    port=self._serial_port,
                    baudrate=19200,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_TWO,
                    timeout=_SERIAL_TIMEOUT,
                )

                # Open the connection
                if not connection.is_open:
                    connection.open()

                self._connection = connection
            elif not self._connection.is_open:
                # Try to repair the connection
                self._connection.open()

            if self._connection.is_open:
                return True
        except serial.SerialException as ex:
            raise AXAConnectionError(str(ex)) from ex

        return False

    @property
    def is_open(self):
        if self._connection and self._connection.is_open:
            return True

        return False

    def close(self) -> bool:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

        return True

    def reset(self) -> bool:
        try:
            self._connection.reset_input_buffer()
            self._connection.reset_output_buffer()

            return True
        except serial.SerialException as ex:
            raise AXAConnectionError(str(ex)) from ex

    def readline(self) -> str:
        try:
            return self._connection.readline()
        except serial.SerialException as ex:
            raise AXAConnectionError(str(ex)) from ex

    def readlines(self) -> str:
        try:
            return self._connection.readlines()
        except serial.SerialException as ex:
            raise AXAConnectionError(str(ex)) from ex

    def write(self, data: str) -> bool:
        try:
            self._connection.write(data)

            return len(data)
        except serial.SerialException as ex:
            raise AXAConnectionError(str(ex)) from ex

    def flush(self) -> None:
        self._connection.flush()


class AXATelnetConnection(AXAConnection):
    """
    Class to handle the telnet connection type.
    """

    _connection = None

    def __init__(self, host: str, port: int):
        assert host is not None
        assert port is not None

        self._host = host
        self._port = port

    def __str__(self):
        return f"{self._host}:{self._port}"

    def open(self) -> bool:
        try:
            if self._connection is None:
                connection = telnetlib.Telnet(self._host, self._port, _TELNET_TIMEOUT)
                self._connection = connection

            return True
        except (OSError, TimeoutError) as ex:
            raise AXAConnectionError(str(ex)) from ex

    @property
    def is_open(self):
        if self._connection:
            return True

        return False

    def close(self) -> bool:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

        return True

    def reset(self) -> bool:
        try:
            self.readlines()

            return True
        except EOFError as ex:
            logger.error("Connection lost: %s", ex)
            self.close()
            raise AXAConnectionError(str(ex)) from ex

    def readline(self) -> str:
        try:
            return self._connection.read_until(b"\r", _TELNET_TIMEOUT)
        except EOFError as ex:
            logger.error("Connection lost: %s", ex)
            self.close()
            raise AXAConnectionError(str(ex)) from ex

    def write(self, data: str) -> int:
        try:
            self._connection.write(data)

            return len(data)
        except OSError as ex:
            logger.error("Connection lost: %s", ex)
            self.close()
            raise AXAConnectionError(str(ex)) from ex
