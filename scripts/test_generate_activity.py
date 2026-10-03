import unittest
from datetime import date, timedelta
import xml.etree.ElementTree as ET

from generate_activity import calendar_days, render


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 9, 3)
        self.end = self.start + timedelta(days=29)
        self.entries = [
            {"date": (self.start + timedelta(days=i)).isoformat(), "contributionCount": 0}
            for i in range(30)
        ]

    def payload(self):
        return {"data": {"user": {"contributionsCollection": {"contributionCalendar": {
            "weeks": [{"contributionDays": self.entries}],
        }}}}}

    def test_quiet_month_renders_valid_svg_in_both_themes(self):
        days = calendar_days(self.payload(), self.start, self.end)
        for theme in ("light", "dark"):
            root = ET.fromstring(render(days, theme))
            dots = root.findall(".//{http://www.w3.org/2000/svg}circle")
            self.assertEqual(len(dots), 30)
            self.assertTrue(all(float(dot.attrib["cy"]) == 192 for dot in dots))

    def test_unordered_dates_and_large_spike_stay_in_plot(self):
        self.entries[5]["contributionCount"] = 10001
        self.entries.reverse()
        days = calendar_days(self.payload(), self.start, self.end)
        self.assertEqual(days[0][0], self.start)
        root = ET.fromstring(render(days, "light"))
        for dot in root.findall(".//{http://www.w3.org/2000/svg}circle"):
            self.assertTrue(76 <= float(dot.attrib["cy"]) <= 192)

    def test_missing_day_is_not_silently_zero_filled(self):
        self.entries.pop()
        with self.assertRaises(ValueError):
            calendar_days(self.payload(), self.start, self.end)

    def test_partial_graphql_error_is_rejected(self):
        payload = self.payload()
        payload["errors"] = [{"message": "rate limited"}]
        with self.assertRaises(ValueError):
            calendar_days(payload, self.start, self.end)

    def test_outside_dates_are_excluded(self):
        self.entries.append({"date": "2026-10-03", "contributionCount": 999})
        days = calendar_days(self.payload(), self.start, self.end)
        self.assertEqual(len(days), 30)
        self.assertEqual(sum(count for _, count in days), 0)


if __name__ == "__main__":
    unittest.main()
