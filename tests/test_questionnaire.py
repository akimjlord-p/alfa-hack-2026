import unittest

from app.questionnaire import QUESTIONS, PURPOSE_CHOICES_BY_INDUSTRY, choices_for_question, enrich_free_text_answer, insights, next_question, progress, question_payload, validate_patch


class QuestionnaireTests(unittest.TestCase):
    def test_farm_branch_and_tranches(self):
        profile = {"industry": "agriculture", "purpose": "seasonal", "funding_pattern": "tranches"}
        self.assertEqual(next_question(profile, ["industry", "purpose"]).id, "agri_calendar")
        self.assertEqual(next_question(profile, ["industry", "purpose", "agri_calendar", "spending_pattern"]).id, "first_tranche")

    def test_contract_branch(self):
        profile = {"industry": "construction", "purpose": "government_contract"}
        self.assertEqual(next_question(profile, ["industry", "purpose"]).id, "contract_terms")

    def test_other_industry_skips_irrelevant_questions(self):
        profile = {"industry": "services", "purpose": "cash_gap"}
        self.assertEqual(next_question(profile, ["industry", "purpose"]).id, "urgency")
        self.assertEqual(next_question(profile, ["industry", "purpose", "urgency"]).id, "gap_source")

    def test_calendar_does_not_invent_repayment_month(self):
        self.assertNotIn("inflow_months", QUESTIONS["agri_calendar"].choices[0].facts)

    def test_write_in_choice_keeps_current_question_open(self):
        question = QUESTIONS["agri_calendar"]
        choice = next(item for item in question.choices if item.id == "agri_other")
        self.assertTrue(choice.input_required)
        self.assertEqual(choice.facts, {})
        self.assertTrue(next(item for item in question_payload(question)["quick_replies"]
                             if item["id"] == "agri_other")["input_required"])

    def test_purpose_suggestions_follow_industry(self):
        question = QUESTIONS["purpose"]
        construction = [choice.id for choice in choices_for_question(question, {"industry": "construction"})]
        agriculture = [choice.id for choice in choices_for_question(question, {"industry": "agriculture"})]
        self.assertEqual(construction[0], "construction")
        self.assertNotIn("seeds", construction)
        self.assertNotIn("marketplace", construction)
        self.assertEqual(agriculture[0], "seeds")
        self.assertIn("other", construction)
        self.assertEqual([x["id"] for x in question_payload(question, {"industry": "construction"})["quick_replies"]], construction)

    def test_every_industry_has_valid_contextual_purposes(self):
        all_ids = {choice.id for choice in QUESTIONS["purpose"].choices}
        for industry, ids in PURPOSE_CHOICES_BY_INDUSTRY.items():
            with self.subTest(industry=industry):
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(set(ids).issubset(all_ids))
                self.assertEqual(ids[-1], "other")
                if industry != "agriculture":
                    self.assertNotIn("seeds", ids)

    def test_custom_agricultural_schedule_is_saved_without_guessing(self):
        answer = "Покупаю семена в марте, продаю урожай частями"
        result = enrich_free_text_answer(QUESTIONS["agri_calendar"], answer, {})
        self.assertEqual(result, {"cashflow_cycle": "unknown", "cashflow_details": answer})
        self.assertEqual(next_question({"industry": "agriculture", "purpose": "seasonal", **result},
                                       ["industry", "purpose", "agri_calendar"]).id, "spending_pattern")

    def test_untrusted_facts_rejected(self):
        patch = validate_patch({"amount": -1, "purpose": "invented", "collateral": "none", "rate": 1,
                                "revenue_monthly": 2_000_000})
        self.assertEqual(patch, {"collateral": "none", "revenue_monthly": 2_000_000})

    def test_insight_uses_first_tranche(self):
        notes = insights({"amount": 4_000_000, "funding_pattern": "tranches",
                          "first_tranche_share": 0.25, "supplier_deferral": True})
        self.assertIn("1 000 000 ₽", notes[0])
        self.assertEqual(len(notes), 2)

    def test_progress_never_claims_finished_early(self):
        state = progress({"industry": "agriculture"}, ["industry"])
        self.assertLess(state["percent"], 100)


if __name__ == "__main__":
    unittest.main()
