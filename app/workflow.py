"""Deterministic demo workflow for a credit application. Not a bank decision engine."""
from __future__ import annotations

from dataclasses import dataclass

STATUS_META = {
    "submitted": ("Отправлена", "Заявка принята и ожидает первичной проверки."),
    "under_review": ("На рассмотрении", "Первичная проверка завершена; заявку смотрит сотрудник."),
    "needs_info": ("Нужны уточнения", "Для продолжения нужны дополнительные сведения от предпринимателя."),
    "approved": ("Предварительно одобрена", "Демо-решение: условия и окончательное решение определяет кредитор."),
    "rejected": ("Не одобрена", "Демо-решение не является решением банка."),
}
FINAL_STATUSES = {"approved", "rejected"}
REVIEWER_TARGETS = {"under_review", "needs_info", "approved", "rejected"}


@dataclass(frozen=True)
class PrecheckResult:
    status: str
    note: str


def precheck(profile: dict, requested_amount: int, min_amount: int, max_amount: int) -> PrecheckResult:
    """A transparent local precheck, intentionally not an underwriting decision."""
    if not min_amount <= requested_amount <= max_amount:
        return PrecheckResult("needs_info", "Сумма заявки требует уточнения: она выходит за вилку выбранного предложения.")
    if profile.get("has_overdue") is True:
        return PrecheckResult("needs_info", "Указана действующая просрочка: сотруднику нужны дополнительные пояснения.")
    if profile.get("legal_form") not in {"ip", "ooo", "other"}:
        return PrecheckResult("needs_info", "Нужно уточнить форму регистрации бизнеса.")
    return PrecheckResult("under_review", "Первичная проверка по демоправилам пройдена; заявка передана сотруднику.")


def can_transition(current: str, target: str) -> bool:
    if target not in REVIEWER_TARGETS or current in FINAL_STATUSES:
        return False
    return current != target
