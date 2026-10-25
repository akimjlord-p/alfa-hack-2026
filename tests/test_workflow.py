import unittest

from app.workflow import can_transition, precheck


class WorkflowTests(unittest.TestCase):
    def test_clean_profile_goes_to_review(self):
        result = precheck({"legal_form": "ip", "has_overdue": False}, 1_000_000, 100_000, 2_000_000)
        self.assertEqual(result.status, "under_review")

    def test_overdue_requires_information(self):
        result = precheck({"legal_form": "ooo", "has_overdue": True}, 1_000_000, 100_000, 2_000_000)
        self.assertEqual(result.status, "needs_info")

    def test_amount_outside_offer_requires_information(self):
        result = precheck({"legal_form": "ip"}, 3_000_000, 100_000, 2_000_000)
        self.assertEqual(result.status, "needs_info")

    def test_final_decision_cannot_be_changed(self):
        self.assertTrue(can_transition("under_review", "approved"))
        self.assertTrue(can_transition("needs_info", "rejected"))
        self.assertFalse(can_transition("approved", "rejected"))
        self.assertFalse(can_transition("under_review", "submitted"))


if __name__ == "__main__":
    unittest.main()
