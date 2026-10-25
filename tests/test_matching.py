import unittest
from types import SimpleNamespace

from app.matching import evaluate, estimated_payment, preferred_instruments


def offer(**changes):
    data = dict(id="offer", offer_name="Возобновляемая кредитная линия", title="Оборотный кредит",
                purposes=["seasonal", "working_capital"], min_amount=300_000, max_amount=30_000_000,
                min_term=1, max_term=18, collateral=["none", "goods"], min_age_months=9,
                processing_days="индивидуально")
    return SimpleNamespace(**{**data, **changes})


def profile(**changes):
    data = dict(purpose="seasonal", amount=3_000_000, term=12, collateral="none",
                business_age_months=24)
    return SimpleNamespace(**{**data, **changes})


class MatchingTests(unittest.TestCase):
    def test_hard_gates_do_not_rank_incompatible_offer(self):
        self.assertIsNone(evaluate(offer(), profile(amount=50_000_000)))
        self.assertIsNone(evaluate(offer(), profile(collateral="property")))
        self.assertIsNone(evaluate(offer(), profile(purpose="export")))

    def test_staged_spending_prefers_credit_line(self):
        context = {"purpose": "seasonal", "funding_pattern": "tranches", "free_cashflow_floor": 1_000_000}
        line = evaluate(offer(), profile(), context)
        lump = evaluate(offer(offer_name="Кредит одной суммой"), profile(), context)
        self.assertGreater(line["score"], lump["score"])
        self.assertEqual(line["breakdown"]["instrument"], 35)

    def test_ai_cannot_override_rules_or_add_more_than_five(self):
        context = {"purpose": "seasonal", "funding_pattern": "tranches"}
        base = evaluate(offer(), profile(), context)
        enhanced = evaluate(offer(), profile(), context, {"credit_line"})
        irrelevant = evaluate(offer(), profile(), context, {"overdraft"})
        self.assertEqual(enhanced["score"] - base["score"], 5)
        self.assertEqual(irrelevant["score"], base["score"])
        self.assertLessEqual(enhanced["score"], 100)

    def test_missing_cashflow_is_not_invented(self):
        fit = evaluate(offer(), profile())
        self.assertIsNone(fit["estimated_monthly_payment"])
        self.assertTrue(any("не уточнён" in warning for warning in fit["warnings"]))

    def test_payment_stress_is_not_bank_offer(self):
        self.assertGreater(estimated_payment(3_000_000, 12), 250_000)
        fit = evaluate(offer(), profile(), {"free_cashflow_floor": 100_000})
        self.assertEqual(fit["breakdown"]["payment_capacity"], 0)
        self.assertTrue(fit["warnings"])

    def test_cash_gap_strategy(self):
        self.assertEqual(preferred_instruments({"purpose": "cash_gap", "inflow_months": 1}),
                         {"overdraft", "credit_line"})


if __name__ == "__main__":
    unittest.main()
