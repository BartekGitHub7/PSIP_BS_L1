"""Testy kolorowania wskaznika przejezdnosci H3 (-1..+1)."""
import unittest

from main import NO_DATA_COLOR, passability_color


class PassabilityColorTests(unittest.TestCase):
    def test_endpoints_and_zero(self):
        self.assertEqual(passability_color(-1), "#d73027")
        self.assertEqual(passability_color(0), "#ffffff")
        self.assertEqual(passability_color(1), "#1a9850")

    def test_midpoints_are_distinct(self):
        self.assertNotEqual(passability_color(-0.4), passability_color(0.4))
        self.assertNotEqual(passability_color(0.4), passability_color(0))
        self.assertNotEqual(passability_color(0.4), passability_color(1))

    def test_equal_value_steps_have_equal_rgb_channel_steps(self):
        # Equal divisions in each half of the ramp (before #fff and after #fff).
        left=[tuple(bytes.fromhex(passability_color(v)[1:])[i] for i in range(3))
              for v in (-1,-0.5,0)]
        right=[tuple(bytes.fromhex(passability_color(v)[1:])[i] for i in range(3))
               for v in (0,0.5,1)]
        for colors in (left,right):
            for c in range(3):
                self.assertLessEqual(abs((colors[1][c]-colors[0][c])
                                     -(colors[2][c]-colors[1][c])),1)

    def test_nodata_and_outside_range(self):
        for value in (None,float("nan"),float("inf"),-1.01,1.01,"x"):
            with self.subTest(value=value):
                self.assertEqual(passability_color(value),NO_DATA_COLOR)


if __name__=="__main__":
    unittest.main()
