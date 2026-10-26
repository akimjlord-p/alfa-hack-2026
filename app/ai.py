"""Extract evidence-backed facts from free text; questionnaire owns the flow."""
from __future__ import annotations

import json
import logging
import os
import re

from openai import OpenAI, OpenAIError, APIStatusError

from .questionnaire import Question, validate_patch

LOGGER = logging.getLogger(__name__)

MODEL = os.getenv("YANDEX_MODEL", "aliceai-llm-flash")
KEY = os.getenv("YANDEX_API_KEY", "")
FOLDER = os.getenv("YANDEX_FOLDER_ID", "")
BASE_URL = "https://ai.api.cloud.yandex.net/v1"


def _make_client(key: str, folder: str):
    if not key or not folder:
        return None
    return OpenAI(api_key=key, base_url=BASE_URL, project=folder,
                  max_retries=2, timeout=20.0)


CLIENT = _make_client(KEY, FOLDER)


def close_client() -> None:
    if CLIENT is not None:
        CLIENT.close()


def _chat_json(system: str, user: dict, max_tokens: int, *, timeout: float | None = None) -> dict:
    """Officially documented OpenAI SDK client for Yandex AI Studio."""
    if CLIENT is None:
        raise RuntimeError("Yandex AI Studio is not configured")
    client = CLIENT.with_options(timeout=timeout, max_retries=0) if timeout is not None else CLIENT
    response = client.chat.completions.create(
        model=f"gpt://{FOLDER}/{MODEL}",
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return json.loads(response.choices[0].message.content or "{}")

SYSTEM = """You extract facts from a Russian business financing interview. Return JSON only.
Read the user's LAST message in the context of the current question and known profile.
Return {"facts": {allowed fields only}, "evidence": {field: exact short quote from LAST user message}}.
Never guess a number, legal form, collateral or credit history. Ranges are not exact numbers: do not turn them into precise values unless a selected choice already has a defined value. Do not repeat old facts unless the last message explicitly corrects them.
Valid fields: industry, purpose, amount, inflow_months, business_age_months, revenue_monthly, free_cashflow_floor, first_tranche_share, funding_pattern, cashflow_cycle, collateral, has_contract, has_overdue, supplier_deferral, existing_debt, legal_form, asset_status, urgency_days, repayment_source, need_description.
Purpose options: working_capital, cash_gap, seasonal, investment, equipment, transport, commercial_property, construction, marketplace, commercial_contract, government_contract, refinance, any_business, opening_business, franchise, business_acquisition, export, import.
Industry options: agriculture, trade, production, services, marketplace, construction, other.
Funding pattern options: once, tranches, revolving, unknown.
Collateral options: none, property, purchased_property, goods, contract_rights, guarantee.
Respond with facts={} when uncertain. The app, not you, selects the next question."""


def local_extract(text: str, question: Question) -> dict:
    """Conservative fallback for exact amounts and a few explicit intent phrases."""
    # Keep the deterministic fallback useful even when the AI provider is
    # unavailable. Normalising `ё` also makes Russian free-text answers less
    # sensitive to the keyboard the user has chosen.
    lower = text.casefold().replace("ё", "е")
    facts = {}
    if question.id == "industry":
        for term, industry in [("ферм", "agriculture"), ("сельск", "agriculture"),
                               ("магазин", "trade"), ("торгов", "trade"),
                               ("производ", "production"), ("завод", "production"),
                               ("маркетплейс", "marketplace"), ("стро", "construction"),
                               ("услуг", "services")]:
            if term in lower:
                facts["industry"] = industry
                break
    if question.id == "spending_pattern":
        if any(x in lower for x in ("частями", "этап", "транш")):
            facts["funding_pattern"] = "tranches"
        elif any(x in lower for x in ("сразу", "одним платеж")):
            facts["funding_pattern"] = "once"
        elif any(x in lower for x in ("ежемесяч", "каждый месяц")):
            facts["funding_pattern"] = "revolving"
    if question.id == "legal_form":
        if re.search(r"\bип\b", lower): facts["legal_form"] = "ip"
        elif re.search(r"\bооо\b", lower): facts["legal_form"] = "ooo"
    if question.id == "asset_status":
        if any(x in lower for x in ("не выбран", "не нашли", "не нашел", "не нашла", "ищем", "ищу объект", "нет объекта", "объекта нет")):
            facts["asset_status"] = "search"
        elif any(x in lower for x in ("этап", "частями", "несколько платеж", "рассроч")):
            facts["asset_status"] = "staged"
        elif any(x in lower for x in ("выбран", "нашел", "нашли", "есть объект", "объект есть", "готов принять оплат", "можно оплат")):
            facts["asset_status"] = "ready"
    if question.id == "urgency":
        if "сегодня" in lower or "завтра" in lower: facts["urgency_days"] = 1
        elif "недел" in lower: facts["urgency_days"] = 7
        elif "месяц" in lower: facts["urgency_days"] = 30
    if question.id == "gap_source":
        if "счёт" in lower or "отгруз" in lower: facts["repayment_source"] = "confirmed_receivable"
        elif "контракт" in lower: facts["repayment_source"] = "contract"
        elif "продаж" in lower: facts["repayment_source"] = "future_sales"
    if question.id == "supplier_deferral":
        if "нет" in lower or "предоплат" in lower or "без отсроч" in lower or "не дадут отсроч" in lower:
            facts["supplier_deferral"] = False
        elif "да" in lower or "отсроч" in lower:
            facts["supplier_deferral"] = True
    if question.id == "collateral":
        for term, collateral in [("без залог", "none"), ("недвиж", "property"),
                                 ("товар", "goods"), ("контракт", "contract_rights"),
                                 ("поруч", "guarantee")]:
            if term in lower:
                facts["collateral"] = collateral
                break
    if question.id == "debt":
        if "просроч" in lower:
            facts.update(existing_debt=True, has_overdue=True)
        elif "нет" in lower:
            facts.update(existing_debt=False, has_overdue=False)
        elif "кредит" in lower:
            facts.update(existing_debt=True, has_overdue=False)
    if question.id in {"amount", "revenue"}:
        match = re.search(r"(?<!\d)(\d[\d\s]{0,12})(?:\s*(млн|тыс|₽|руб))?", lower)
        if match:
            value = int(re.sub(r"\s", "", match.group(1)))
            unit = match.group(2)
            if unit == "млн": value *= 1_000_000
            elif unit == "тыс": value *= 1_000
            key = "amount" if question.id == "amount" else "revenue_monthly"
            facts[key] = value
    if question.id == "business_age":
        match = re.search(r"(\d{1,2})\s*(месяц|мес|год|лет|года)", lower)
        if match:
            value = int(match.group(1))
            facts["business_age_months"] = value * 12 if match.group(2) in {"год", "лет", "года"} else value
    if question.id == "cash_surplus":
        match = re.search(r"(?<!\d)(\d[\d\s]{0,12})(?:\s*(млн|тыс|₽|руб))?", lower)
        if match:
            value = int(re.sub(r"\s", "", match.group(1)))
            if match.group(2) == "млн": value *= 1_000_000
            elif match.group(2) == "тыс": value *= 1_000
            facts["free_cashflow_floor"] = value
    if question.id == "inflow":
        match = re.search(r"(\d{1,3})\s*(месяц|мес|год|лет|года)", lower)
        if match:
            value = int(match.group(1))
            facts["inflow_months"] = value * 12 if match.group(2) in {"год", "лет", "года"} else value
    if question.id == "purpose":
        terms = [
            ("франшиз", "franchise"), ("готовый бизнес", "business_acquisition"),
            ("открыть бизнес", "opening_business"), ("запуск бизнеса", "opening_business"),
            ("экспорт", "export"), ("импорт", "import"),
            ("госконтракт", "government_contract"), ("семен", "seasonal"),
            ("удобрен", "seasonal"), ("маркетплейс", "marketplace"),
            ("кассов", "cash_gap"), ("оборудован", "equipment"),
            ("спецтехник", "transport"), ("транспорт", "transport"),
            ("техник", "transport"), ("недвижим", "commercial_property"),
            ("строительств", "construction"),
            ("контракт", "commercial_contract"), ("рефинанс", "refinance"),
            ("закуп", "working_capital"), ("сырь", "working_capital"),
        ]
        for term, purpose in terms:
            if term in lower:
                facts["purpose"] = purpose
                break
    return validate_patch(facts)


def extract(text: str, question: Question, profile: dict) -> tuple[dict, str]:
    if not KEY or not FOLDER:
        return local_extract(text, question), "demo"
    prompt = {"question_id": question.id, "question": question.title,
              "known_profile": profile, "last_user_message": text}
    try:
        parsed = _chat_json(SYSTEM, prompt, 450)
        evidence = parsed.get("evidence", {})
        facts = validate_patch(parsed.get("facts", {}))
        # The model must cite words actually present in this answer for each fact.
        facts = {key: value for key, value in facts.items()
                 if isinstance(evidence.get(key), str) and evidence[key].strip().lower() in text.lower()}
        # Keep deterministic phrases as a safety net even when Yandex returns
        # an empty or overly cautious answer. The model remains authoritative
        # for fields it extracted with evidence; the fallback only fills gaps.
        facts = {**local_extract(text, question), **facts}
        return facts, "ai"
    except (OpenAIError, RuntimeError, KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        LOGGER.warning("Yandex fact extraction unavailable: %s", type(error).__name__)
        return local_extract(text, question), "demo"


def strategy_preferences(profile: dict) -> tuple[set[str], str]:
    """A single bounded AI signal for ranking; no offers, rates or raw chat are sent."""
    if not KEY or not FOLDER:
        return set(), "rules_only"
    allowed = {
        "credit_line": {"funding_pattern", "purpose"},
        "overdraft": {"purpose", "inflow_months"},
        "contract_financing": {"purpose", "has_contract"},
        "asset_financing": {"purpose", "asset_status"},
        "term_loan": {"purpose", "funding_pattern"},
    }
    safe_fields = {"industry", "purpose", "amount", "inflow_months", "funding_pattern",
                   "first_tranche_share", "supplier_deferral", "has_contract", "asset_status",
                   "repayment_source", "urgency_days", "business_age_months", "free_cashflow_floor"}
    safe_profile = {key: profile[key] for key in safe_fields if key in profile}
    system = """Return JSON only: {"preferences":[{"instrument":"credit_line","evidence_fields":["funding_pattern"]}]}.
Choose at most two financing instruments from credit_line, overdraft, contract_financing, asset_financing, term_loan.
Use only supplied profile fields as evidence. Do not infer approval, rates, product availability or any missing fact.
An instrument is a preference, not an eligibility decision. Return an empty list if insufficient context."""
    try:
        # Ranking must not hold the final questionnaire response for SDK retries.
        parsed = _chat_json(system, safe_profile, 200, timeout=8.0)
        selected = set()
        for item in parsed.get("preferences", [])[:2]:
            if not isinstance(item, dict):
                continue
            kind, fields = item.get("instrument"), item.get("evidence_fields", [])
            if kind in allowed and isinstance(fields, list) and fields and all(
                field in safe_profile and field in allowed[kind] for field in fields
            ):
                selected.add(kind)
        return selected, "ai" if selected else "rules_only"
    except APIStatusError as error:
        return set(), "provider_unavailable" if error.status_code in {401, 402, 403, 429} else "rules_only"
    except OpenAIError as error:
        LOGGER.warning("Yandex strategy unavailable: %s", type(error).__name__)
        return set(), "provider_unavailable"
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return set(), "rules_only"
