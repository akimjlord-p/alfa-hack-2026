"""Explainable, bounded ranking. Scores are suitability points, never approval odds."""
from __future__ import annotations

import math
import re


def instrument(offer) -> str:
    name = f"{offer.offer_name} {offer.title}".lower()
    if "овердрафт" in name:
        return "overdraft"
    if "линия" in name:
        return "credit_line"
    if "контракт" in name or "госзаказ" in name:
        return "contract_financing"
    if any(word in name for word in ("ипотек", "залог приобретаем", "капитальн", "инвестицион")):
        return "asset_financing"
    return "term_loan"


def preferred_instruments(context: dict) -> set[str]:
    purpose = context.get("purpose")
    result = set()
    if context.get("funding_pattern") in {"tranches", "revolving"} or purpose == "seasonal":
        result.add("credit_line")
    if purpose == "cash_gap" and context.get("inflow_months", 99) <= 3:
        result.update({"overdraft", "credit_line"})
    if purpose in {"commercial_contract", "government_contract"} and context.get("has_contract"):
        result.add("contract_financing")
    if purpose in {"equipment", "transport", "commercial_property", "construction", "investment"}:
        result.add("asset_financing")
    if not result:
        result.add("term_loan")
    return result


def estimated_payment(amount: int, months: int, annual_rate: float = 0.35) -> int:
    """Stress-test annuity, not a bank quote. Fixed 35% prevents stale rates driving rank."""
    months = max(1, months)
    monthly_rate = annual_rate / 12
    factor = (1 + monthly_rate) ** months
    return math.ceil(amount * monthly_rate * factor / (factor - 1))


def processing_days(label: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:рабочих\s*)?(дн|минут)", label.lower())
    if not match:
        return None
    days = int(match.group(1))
    return 1 if match.group(2) == "минут" else days


def evaluate(offer, profile, context: dict | None = None, ai_preferences: set[str] | None = None) -> dict | None:
    context = context or {}
    if profile.purpose not in offer.purposes:
        return None
    # These are catalogue compatibility gates, not an approval decision.
    if not offer.min_amount <= profile.amount <= offer.max_amount:
        return None
    if profile.collateral not in offer.collateral:
        return None

    kind = instrument(offer)
    preferred = preferred_instruments({**context, "purpose": profile.purpose})
    breakdown = {}
    reasons = ["цель, сумма и обеспечение совпадают с условиями каталога"]
    warnings = []

    breakdown["instrument"] = 22 + (13 if kind in preferred else 0)
    if kind in preferred:
        reasons.append("формат финансирования соответствует графику расходов")

    term_ok = offer.min_term <= profile.term <= offer.max_term
    breakdown["cashflow"] = 12 if term_ok else 0
    if term_ok:
        reasons.append("расчётный срок попадает в диапазон продукта")
    else:
        warnings.append("Расчётный срок вне указанного диапазона: проверьте возможный график возврата.")
    if kind == "overdraft" and profile.purpose == "cash_gap" and context.get("inflow_months", 99) <= 3:
        breakdown["cashflow"] += 8
    elif kind == "contract_financing" and context.get("has_contract") is True:
        breakdown["cashflow"] += 8
    elif kind == "credit_line" and context.get("funding_pattern") in {"tranches", "revolving"}:
        breakdown["cashflow"] += 8
    elif kind == "asset_financing" and context.get("asset_status") in {"ready", "staged"}:
        breakdown["cashflow"] += 8

    breakdown["catalogue_fit"] = 16 + (4 if profile.business_age_months >= offer.min_age_months else 0)
    if profile.business_age_months < offer.min_age_months:
        warnings.append(f"По каталогу нужен бизнес от {offer.min_age_months} месяцев; возраст в анкете указан приблизительно.")

    surplus = context.get("free_cashflow_floor", 0)
    if isinstance(surplus, (int, float)) and surplus > 0:
        payment = estimated_payment(profile.amount, profile.term)
        ratio = payment / surplus
        breakdown["payment_capacity"] = 15 if ratio <= .7 else 10 if ratio <= 1 else 0
        if ratio > .7:
            warnings.append("Оценочный платёж может быть высоким относительно нижней границы свободного денежного потока.")
    else:
        payment = None
        breakdown["payment_capacity"] = 5
        warnings.append("Свободный денежный поток не уточнён; посильность платежа не подтверждена.")

    urgent = context.get("urgency_days")
    duration = processing_days(offer.processing_days)
    breakdown["speed"] = 5 if urgent and duration is not None and duration <= urgent else 0 if urgent and duration is not None else 3
    if urgent and duration is None:
        warnings.append("Срок рассмотрения не подтверждён; срочную выдачу нельзя обещать.")
    elif urgent and duration is not None and duration > urgent:
        warnings.append("Заявленный срок рассмотрения может не уложиться в дату первого платежа.")

    ai_bonus = 5 if ai_preferences and kind in ai_preferences and kind in preferred else 0
    breakdown["ai_context"] = ai_bonus
    score = sum(breakdown.values())
    return {"score": score, "breakdown": breakdown, "reasons": reasons[:3], "warnings": warnings,
            "instrument": kind, "estimated_monthly_payment": payment}
