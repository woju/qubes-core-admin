'''
Created on Dec 25, 2014

@author: user
'''
import unittest
import qubes.log

class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def test_ansi_text(self):
        result = qubes.log.ansi_text(text="Foobar")
        self.assertEqual(result, "Foobar", "Ansi failed to colorize")

    def test_ansi_text_colors(self):
        result = qubes.log.ansi_text(text="Foobar", **{'color': 'blue', 'inverse': True})
        self.assertEqual(result, "\x1b[7;34mFoobar\x1b[0m", "Ansi failed to colorize")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
