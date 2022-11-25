"""
Created on 12 Nov 2022

@author: Rogier van Staveren
"""
import logging
import time
import unittest

from axaremote.axaremote import AXARemote

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG
)

serial_port = "/dev/tty.usbserial-110"


class Test(unittest.TestCase):
    def testConnect(self):
        axa = AXARemote(serial_port)
        response = axa.connect()
        self.assertTrue(response)
        self.assertIsNotNone(axa._connection)
        self.assertIsNotNone(axa.device)
        self.assertIsNotNone(axa.version)

    def testDisconnect(self):
        axa = AXARemote(serial_port)
        axa.connect()
        response = axa.disconnect()
        self.assertTrue(response)
        self.assertIsNone(axa._connection)

    def testOpen(self):
        axa = AXARemote(serial_port)
        axa.connect()
        response = axa.open()
        self.assertTrue(response)
        axa.close()

    def testStop(self):
        axa = AXARemote(serial_port)
        axa.connect()
        axa.open()
        time.sleep(5)
        response = axa.stop()
        self.assertTrue(response)
        axa.close()

    def testClose(self):
        axa = AXARemote(serial_port)
        axa.connect()
        axa.open()
        time.sleep(5)
        response = axa.close()
        self.assertTrue(response)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
