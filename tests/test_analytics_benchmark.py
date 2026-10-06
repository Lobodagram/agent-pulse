import unittest
from scripts.analytics_benchmark import evaluate

class GoldenCorpusTests(unittest.TestCase):
    def test_labeled_positive_and_negative_mechanics(self):
        r=evaluate()
        self.assertEqual(len(r['cases']),14)
        self.assertGreater(r['truePositiveKinds'],0)
        self.assertEqual(r['falsePositiveKinds'],0)
        self.assertEqual(r['falseNegativeKinds'],0)
        self.assertTrue(r['syntheticOnly']);self.assertFalse(r['realJournalTouched'])

if __name__=='__main__':unittest.main()
