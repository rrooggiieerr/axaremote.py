"""
Implements the connection types for connecting to AXA Remote window openers.

Created on 24 Aug 2023

@author: Rogier van Staveren
"""
import telnetlib
from abc import ABC, abstractmethod

import serial


class AXAConnection(ABC):
    """
    Abstract class on which the different connection types are build.
    """

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

    def open(self) -> bool:
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

    def close(self) -> bool:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

        return True

    def reset(self) -> bool:
        self._connection.reset_input_buffer()
        self._connection.reset_output_buffer()

        return True

    def readline(self) -> str:
        return self._connection.readline()

    def readlines(self) -> str:
        return self._connection.readlines()

    def write(self, data: str) -> bool:
        self._connection.write(data)

        return True

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

    def open(self) -> bool:
        if self._connection is None:
            connection = telnetlib.Telnet(self._host, self._port, 1)
            self._connection = connection

        return True

    def close(self) -> bool:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

        return True

    def reset(self) -> bool:
        self.readlines()

        return True

    def readline(self) -> str:
        return self._connection.read_until(b"\r\n", 1)

    def write(self, data: str) -> bool:
        self._connection.write(data)

        return True
