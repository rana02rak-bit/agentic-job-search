import unittest

from app.services.scoring import ScoreComponents, clamp_score


class TestScoreComponents(unittest.TestCase):
    def test_total_matches_five_dimensions(self) -> None:
        score = ScoreComponents(funding=9, hiring=8, ai=9, location=10, role_match=10)
        self.assertEqual(score.total, 46)

    def test_out_of_range_score_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ScoreComponents(funding=11, hiring=8, ai=9, location=10, role_match=10)

    def test_clamp_score(self) -> None:
        self.assertEqual(clamp_score(-2), 0)
        self.assertEqual(clamp_score(7), 7)
        self.assertEqual(clamp_score(15), 10)


if __name__ == "__main__":
    unittest.main()

