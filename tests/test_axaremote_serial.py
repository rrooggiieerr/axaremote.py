# pylint: disable=protected-access
# pylint: disable=R0801
"""
Created on 12 Nov 2022

@author: Rogier van Staveren
"""

import json
import logging
import time
import unittest

from axaremote import AXARemote, AXARemoteSerial, AXAStatus

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG
)

_SETTINGS_JSON = "settings.json"

_LOGGER = logging.getLogger(__name__)


class Test(unittest.TestCase):
    """
    Unit Test for testing an AXA Remote window opener over a serial connection
    """

    _serial_port: str = None
    _close_time: float = None

    _axa = None

    def setUp(self):
        """
        Set up the Unit Test.
        """
        with open(_SETTINGS_JSON, encoding="utf8") as settings_file:
            settings = json.load(settings_file)
            _LOGGER.debug("Json settings: %s", settings)
            self._serial_port = settings.get("serial_port")
            self._close_time = settings.get("close_time")

        self._axa = AXARemoteSerial(self._serial_port)
        if self._close_time is not None:
            self._axa.set_close_time(self._close_time)
        self._axa.connect()
        status = self._axa.status()
        if status != AXAStatus.LOCKED:
            logger.info("Resetting AXA Remote to Locked Position")
            self._axa.close()
            time.sleep(AXARemote._time_close + AXARemote._time_lock)
            self._axa.sync_status()
            self._axa.stop()

    def tearDown(self):
        """
        Tear down the Unit Test.
        """
        if self._axa is not None:
            self._axa.sync_status()
            status = self._axa.status()
            if status != AXAStatus.LOCKED:
                logger.info("Resetting AXA Remote to Locked Position")
                self._axa.close()
                time.sleep(AXARemote._time_close + AXARemote._time_lock)
                self._axa.disconnect()
                self._axa = None

    def test_connect(self):
        """
        Test connection to the AXA Remote window opener.
        """
        response = self._axa.connect()
        self.assertTrue(response)
        self.assertIsNotNone(self._axa.connection)
        self.assertIsNotNone(self._axa.device)
        self.assertIsNotNone(self._axa.version)

    def test_disconnect(self):
        """
        Test disconnecting from the AXA Remote window opener.
        """
        response = self._axa.disconnect()
        self.assertTrue(response)
        self.assertIsNone(self._axa.connection)

    def test_open(self):
        """
        Test opening the AXA Remote window opener.
        """
        response = self._axa.open()
        self.assertTrue(response)
        self._axa.stop()

    def test_unlocking(self):
        """
        Test unlocking the AXA Remote window opener.
        """
        self._axa.open()
        time.sleep(AXARemote._time_unlock / 2)
        status = self._axa.status()
        self.assertIs(AXAStatus.UNLOCKING, status)
        self._axa.stop()

    def test_stop(self):
        """
        Test stopping the AXA Remote window opener.
        """
        self._axa.open()
        time.sleep(AXARemote._time_unlock + (AXARemote._time_open / 2))
        response = self._axa.stop()
        self.assertTrue(response)

    def test_close(self):
        """
        Test closing the AXA Remote window opener.
        """
        self._axa.open()
        time.sleep(AXARemote._time_unlock + AXARemote._time_open + 1)
        response = self._axa.close()
        self.assertTrue(response)

    def test_closing(self):
        """
        Test closing status and position of AXA Remote window opener.
        """
        self._axa.open()
        time.sleep(AXARemote._time_unlock + AXARemote._time_open + 1)
        self._axa.close()
        time.sleep(AXARemote._time_close / 2)
        status = self._axa.status()
        self.assertIs(AXAStatus.CLOSING, status)
        position = self._axa.position()
        self.assertAlmostEqual(50.0, position, delta=1)

    def test_locking(self):
        """
        Test locking status of AXA Remote window opener.
        """
        self._axa.open()
        time.sleep(AXARemote._time_unlock + AXARemote._time_open + 1)
        self._axa.close()
        time.sleep(AXARemote._time_close + (AXARemote._time_lock / 2))
        status = self._axa.status()
        self.assertIs(AXAStatus.LOCKING, status)

    def test_update_unlocking(self):
        """
        Test if the the AXA Remote window opener updates on unlocking.
        """
        self._axa._status = AXAStatus.UNLOCKING
        self._axa._position = 0
        self._axa._timestamp = time.time()
        time.sleep(self._axa._time_unlock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.UNLOCKING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_unlock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.UNLOCKING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_unlock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.UNLOCKING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_unlock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.OPENING, self._axa._status)
        self.assertAlmostEqual(0.0, self._axa._position, delta=1)

    def test_update_opening(self):
        """
        Test if the the AXA Remote window opener updates on opening.
        """
        self._axa._status = AXAStatus.OPENING
        self._axa._position = 0
        self._axa._timestamp = time.time() - self._axa._time_unlock
        time.sleep(self._axa._time_open / 4)
        self._axa._update()
        self.assertIs(AXAStatus.OPENING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_open / 4)
        self._axa._update()
        self.assertIs(AXAStatus.OPENING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_open / 4)
        self._axa._update()
        self.assertIs(AXAStatus.OPENING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_open / 4)
        self._axa._update()
        self.assertIs(AXAStatus.OPEN, self._axa._status)
        self.assertEqual(100.0, self._axa._position)

    def test_update_closing(self):
        """
        Test if the the AXA Remote window opener updates on closing.
        """
        self._axa._status = AXAStatus.CLOSING
        self._axa._position = 100
        self._axa._timestamp = time.time()
        time.sleep(self._axa._time_close / 4)
        self._axa._update()
        self.assertIs(AXAStatus.CLOSING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_close / 4)
        self._axa._update()
        self.assertIs(AXAStatus.CLOSING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_close / 4)
        self._axa._update()
        self.assertIs(AXAStatus.CLOSING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_close / 4)
        self._axa._update()
        self.assertIs(AXAStatus.LOCKING, self._axa._status)
        self.assertAlmostEqual(100.0, self._axa._position, delta=1)

    def test_update_locking(self):
        """
        Test if the the AXA Remote window opener updates on locking.
        """
        self._axa._status = AXAStatus.LOCKING
        self._axa._position = 100
        self._axa._timestamp = time.time() - self._axa._time_close
        time.sleep(self._axa._time_lock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.LOCKING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_lock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.LOCKING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_lock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.LOCKING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._time_lock / 4)
        self._axa._update()
        self.assertIs(AXAStatus.LOCKED, self._axa._status)
        self.assertEqual(0.0, self._axa._position)


if __name__ == "__main__":
    unittest.main()
