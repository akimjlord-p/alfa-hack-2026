import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import ai
from app.questionnaire import QUESTIONS


class YandexAITests(unittest.TestCase):
    @patch.object(ai, "CLIENT")
    @patch.object(ai, "FOLDER", "test-folder")
    @patch.object(ai, "KEY", "test-key")
    def test_request_uses_yandex_model_and_json_format(self, client):
        client.chat.completions.create.return_value.choices = [
            SimpleNamespace(message=SimpleNamespace(content='{"facts":{},"evidence":{}}'))]
        result = ai._chat_json("Return JSON", {"question": "test"}, 100)
        self.assertEqual(result, {"facts": {}, "evidence": {}})
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], f"gpt://test-folder/{ai.MODEL}")
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["max_tokens"], 100)

    @patch.object(ai, "OpenAI")
    def test_sdk_client_has_project_retries_and_timeout(self, factory):
        ai._make_client("test-key", "test-folder")
        factory.assert_called_once_with(api_key="test-key", base_url=ai.BASE_URL,
                                        project="test-folder", max_retries=2, timeout=20.0)

    @patch.object(ai, "_chat_json")
    @patch.object(ai, "FOLDER", "test-folder")
    @patch.object(ai, "KEY", "test-key")
    def test_extract_requires_quote_from_current_answer(self, chat):
        chat.return_value = {"facts": {"industry": "agriculture", "amount": 9_000_000},
                             "evidence": {"industry": "ферма", "amount": "9 млн"}}
        facts, mode = ai.extract("У меня ферма", QUESTIONS["industry"], {})
        self.assertEqual(facts, {"industry": "agriculture"})
        self.assertEqual(mode, "ai")

    @patch.object(ai, "_chat_json")
    @patch.object(ai, "FOLDER", "test-folder")
    @patch.object(ai, "KEY", "test-key")
    def test_extract_keeps_safe_local_phrase_when_ai_is_uncertain(self, chat):
        chat.return_value = {"facts": {}, "evidence": {}}
        facts, mode = ai.extract("Нашел объект, продавец готов принять оплату",
                                 QUESTIONS["asset_status"], {})
        self.assertEqual(facts, {"asset_status": "ready"})
        self.assertEqual(mode, "ai")

    @patch.object(ai, "_chat_json")
    @patch.object(ai, "FOLDER", "test-folder")
    @patch.object(ai, "KEY", "test-key")
    def test_strategy_rejects_unrelated_evidence(self, chat):
        chat.return_value = {"preferences": [{"instrument": "credit_line", "evidence_fields": ["collateral"]}]}
        selected, mode = ai.strategy_preferences({"purpose": "seasonal", "collateral": "none"})
        self.assertEqual(selected, set())
        self.assertEqual(mode, "rules_only")


if __name__ == "__main__":
    unittest.main()
