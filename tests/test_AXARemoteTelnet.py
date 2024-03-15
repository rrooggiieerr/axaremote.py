"""
Created on 12 Nov 2022

@author: Rogier van Staveren
"""
import logging
import time
import unittest

from axaremote import AXARemote, AXARemoteTelnet

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG
)

host = "kitchen-window.local"
port = 23


class Test(unittest.TestCase):
    _axa = None

    def setUp(self):
        self._axa = AXARemoteTelnet(host, port)
        self._axa.connect()
        status = self._axa.status()
        if status != AXARemote.STATUS_LOCKED:
            logger.info("Resetting AXA Remote to Locked Position")
            self._axa.close()
            time.sleep(AXARemote._TIME_CLOSE + AXARemote._TIME_LOCK)
            self._axa.sync_status()
            self._axa.stop()

    def tearDown(self):
        if self._axa is not None:
            self._axa.sync_status()
            status = self._axa.status()
            if status != AXARemote.STATUS_LOCKED:
                logger.info("Resetting AXA Remote to Locked Position")
                self._axa.close()
                time.sleep(AXARemote._TIME_CLOSE + AXARemote._TIME_LOCK)
                self._axa.disconnect()
                self._axa = None

    def testConnect(self):
        response = self._axa.connect()
        self.assertTrue(response)
        self.assertIsNotNone(self._axa.connection)
        self.assertIsNotNone(self._axa.device)
        self.assertIsNotNone(self._axa.version)

    def testDisconnect(self):
        response = self._axa.disconnect()
        self.assertTrue(response)
        self.assertIsNone(self._axa.connection)

    def testOpen(self):
        response = self._axa.open()
        self.assertTrue(response)
        self._axa.stop()

    def testUnlocking(self):
        self._axa.open()
        time.sleep(AXARemote._TIME_UNLOCK / 2)
        status = self._axa.status()
        self.assertIs(AXARemote.STATUS_UNLOCKING, status)
        self._axa.stop()

    def testStop(self):
        self._axa.open()
        time.sleep(AXARemote._TIME_UNLOCK + (AXARemote._TIME_OPEN / 2))
        response = self._axa.stop()
        self.assertTrue(response)

    def testClose(self):
        self._axa.open()
        time.sleep(AXARemote._TIME_UNLOCK + AXARemote._TIME_OPEN + 1)
        response = self._axa.close()
        self.assertTrue(response)

    def testClosing(self):
        self._axa.open()
        time.sleep(AXARemote._TIME_UNLOCK + AXARemote._TIME_OPEN + 1)
        self._axa.close()
        time.sleep(AXARemote._TIME_CLOSE / 2)
        status = self._axa.status()
        self.assertIs(AXARemote.STATUS_CLOSING, status)
        position = self._axa.position()
        self.assertAlmostEqual(50.0, position, delta=1)

    def testLocking(self):
        self._axa.open()
        time.sleep(AXARemote._TIME_UNLOCK + AXARemote._TIME_OPEN + 1)
        self._axa.close()
        time.sleep(AXARemote._TIME_CLOSE + (AXARemote._TIME_LOCK / 2))
        status = self._axa.status()
        self.assertIs(AXARemote.STATUS_LOCKING, status)

    def testUpdateUnlocking(self):
        self._axa._status = AXARemote.STATUS_UNLOCKING
        self._axa._position = 0
        self._axa._timestamp = time.time()
        time.sleep(self._axa._TIME_UNLOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_UNLOCKING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_UNLOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_UNLOCKING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_UNLOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_UNLOCKING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_UNLOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_OPENING, self._axa._status)
        self.assertAlmostEqual(0.0, self._axa._position, delta=1)

    def testUpdateOpening(self):
        self._axa._status = AXARemote.STATUS_OPENING
        self._axa._position = 0
        self._axa._timestamp = time.time() - self._axa._TIME_UNLOCK
        time.sleep(self._axa._TIME_OPEN / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_OPENING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_OPEN / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_OPENING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_OPEN / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_OPENING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_OPEN / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_OPEN, self._axa._status)
        self.assertEqual(100.0, self._axa._position)

    def testUpdateClosing(self):
        self._axa._status = AXARemote.STATUS_CLOSING
        self._axa._position = 100
        self._axa._timestamp = time.time()
        time.sleep(self._axa._TIME_CLOSE / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_CLOSING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_CLOSE / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_CLOSING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_CLOSE / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_CLOSING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_CLOSE / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_LOCKING, self._axa._status)
        self.assertAlmostEqual(100.0, self._axa._position, delta=1)

    def testUpdateLocking(self):
        self._axa._status = AXARemote.STATUS_LOCKING
        self._axa._position = 100
        self._axa._timestamp = time.time() - self._axa._TIME_CLOSE
        time.sleep(self._axa._TIME_LOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_LOCKING, self._axa._status)
        self.assertAlmostEqual(75.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_LOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_LOCKING, self._axa._status)
        self.assertAlmostEqual(50.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_LOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_LOCKING, self._axa._status)
        self.assertAlmostEqual(25.0, self._axa._position, delta=1)
        time.sleep(self._axa._TIME_LOCK / 4)
        self._axa._update()
        self.assertIs(AXARemote.STATUS_LOCKED, self._axa._status)
        self.assertEqual(0.0, self._axa._position)


if __name__ == "__main__":
    unittest.main()
