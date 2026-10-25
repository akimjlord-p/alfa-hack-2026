"""Versioned, deterministic interview plan for business financing.

The model may extract facts from free text, but this module owns question order,
answer choices, branch rules, completion and financing insights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VERSION = 4


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    facts: dict[str, Any]
    input_required: bool = False


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    why: str
    choices: tuple[Choice, ...]
    field: str | None = None
    stage: str = "Диагностика"
    input_hint: str = "Можно выбрать вариант или ответить своими словами"


def c(id: str, label: str, *, input_required: bool = False, **facts: Any) -> Choice:
    return Choice(id, label, facts, input_required)


QUESTIONS: dict[str, Question] = {
    "industry": Question("industry", "В какой сфере работает бизнес?", "Отрасль определяет сезонность и доступные способы финансирования.", (
        c("agriculture", "Сельское хозяйство", industry="agriculture"),
        c("trade", "Торговля", industry="trade"),
        c("production", "Производство", industry="production"),
        c("services", "Услуги", industry="services"),
        c("marketplace", "Маркетплейсы", industry="marketplace"),
        c("construction", "Строительство", industry="construction"),
    ), "industry", "Контекст"),
    "purpose": Question("purpose", "На что именно нужны деньги?", "Цель помогает отделить оборотные расходы от инвестиций и временного разрыва.", (
        c("seeds", "Семена, удобрения, сезонные работы", purpose="seasonal"),
        c("inventory", "Товар, сырьё, запасы", purpose="working_capital"),
        c("gap", "Не хватает до ближайшей оплаты", purpose="cash_gap"),
        c("equipment", "Оборудование или техника", purpose="equipment"),
        c("contract", "Исполнение контракта", purpose="commercial_contract"),
        c("gov_contract", "Исполнение госконтракта", purpose="government_contract"),
        c("property", "Коммерческая недвижимость", purpose="commercial_property"),
        c("construction", "Строительство или модернизация", purpose="construction"),
        c("marketplace", "Закупки для маркетплейса", purpose="marketplace"),
        c("refinance", "Погасить дорогой кредит", purpose="refinance"),
        c("other", "Другая цель — опишу словами", input_required=True),
    ), "purpose", "Задача"),
    "agri_calendar": Question("agri_calendar", "Когда закупаете материалы и когда получите деньги от урожая?", "Сопоставим выдачу и возврат с сезонным циклом.", (
        c("spring_autumn", "Закупка весной → выручка осенью", cashflow_cycle="seasonal"),
        c("summer_winter", "Закупка летом → выручка зимой", cashflow_cycle="seasonal"),
        c("year_round", "Закупки и продажи круглый год", cashflow_cycle="regular"),
        c("agri_other", "Другой график — опишу", input_required=True),
    ), "cashflow_cycle", "Денежный цикл"),
    "marketplace_cycle": Question("marketplace_cycle", "Когда маркетплейс перечисляет деньги после продажи?", "Период ожидания выплат показывает длину кассового разрыва.", (
        c("weekly", "До недели", inflow_months=1, cashflow_cycle="short"),
        c("monthly", "До месяца", inflow_months=1, cashflow_cycle="short"),
        c("long", "Больше месяца", inflow_months=2, cashflow_cycle="medium"),
        c("unknown", "Не знаю точно", cashflow_cycle="unknown"),
    ), "cashflow_cycle", "Денежный цикл"),
    "contract_terms": Question("contract_terms", "Есть подписанный контракт и дата оплаты заказчиком?", "Права по контракту могут открыть отдельное финансирование.", (
        c("signed", "Да, контракт подписан", has_contract=True),
        c("tender", "Есть победа в закупке", has_contract=True, purpose="government_contract"),
        c("negotiation", "Договор ещё согласуется", has_contract=False),
        c("no", "Нет контракта", has_contract=False),
    ), "has_contract", "Денежный цикл"),
    "asset_status": Question("asset_status", "Объект уже выбран и продавец готов принять оплату?", "Это определяет, нужен ли разовый кредит сейчас или лимит с выборкой позже.", (
        c("ready", "Объект выбран, оплата скоро", asset_status="ready"),
        c("search", "Пока ищем объект", asset_status="search"),
        c("staged", "Оплата по этапам", asset_status="staged", funding_pattern="tranches"),
        c("unknown", "Пока не решили", asset_status="unknown"),
    ), "asset_status", "Структура сделки"),
    "urgency": Question("urgency", "Через сколько дней нужен первый платёж?", "Срочность влияет на выбор инструмента и реалистичность оформления.", (
        c("today", "Сегодня–завтра", urgency_days=1),
        c("week", "В течение недели", urgency_days=7),
        c("month", "В течение месяца", urgency_days=30),
        c("later", "Позже месяца", urgency_days=60),
    ), "urgency_days", "Сроки"),
    "gap_source": Question("gap_source", "Что именно закроет разрыв и насколько это подтверждено?", "Ожидаемый платёж покупателя и надежда на будущие продажи — разные риски и разные продукты.", (
        c("invoice", "Есть отгрузка и счёт к оплате", repayment_source="confirmed_receivable"),
        c("contract", "Есть контракт, но ещё не отгрузили", repayment_source="contract"),
        c("sales", "Будущие продажи, сумма не гарантирована", repayment_source="future_sales"),
        c("unknown", "Пока не знаю", repayment_source="unknown"),
    ), "repayment_source", "Денежный цикл"),
    "spending_pattern": Question("spending_pattern", "Вся сумма нужна одновременно?", "При расходах по этапам можно сравнить кредитную линию с разовым кредитом.", (
        c("once", "Да, вся сумма сразу", funding_pattern="once"),
        c("two_three", "Нет, 2–3 закупки", funding_pattern="tranches"),
        c("monthly", "Нет, расходы каждый месяц", funding_pattern="revolving"),
        c("unclear", "Пока неизвестно", funding_pattern="unknown"),
    ), "funding_pattern", "Структура расходов"),
    "first_tranche": Question("first_tranche", "Какая часть бюджета нужна в первый месяц?", "Так оценим начальную выборку и возможную экономию на процентах.", (
        c("quarter", "Около четверти", first_tranche_share=0.25),
        c("half", "Около половины", first_tranche_share=0.5),
        c("three_quarters", "Около 75%", first_tranche_share=0.75),
        c("unknown", "Пока не знаю", first_tranche_share=None),
    ), "first_tranche_share", "Структура расходов"),
    "supplier_deferral": Question("supplier_deferral", "Поставщик готов отложить часть оплаты?", "Отсрочка может уменьшить необходимый кредитный лимит.", (
        c("yes", "Да, есть отсрочка", supplier_deferral=True),
        c("maybe", "Можно договориться", supplier_deferral="possible"),
        c("no", "Нет, только предоплата", supplier_deferral=False),
        c("not_applicable", "Поставщика нет", supplier_deferral=False),
    ), "supplier_deferral", "Оптимизация"),
    "amount": Question("amount", "Какой общий бюджет задачи?", "Сопоставим потребность с лимитами конкретных продуктов.", (
        c("one_m", "Около 1 млн ₽", amount=1_000_000),
        c("three_m", "Около 3 млн ₽", amount=3_000_000),
        c("ten_m", "Около 10 млн ₽", amount=10_000_000),
        c("custom", "Укажу точную сумму", input_required=True),
    ), "amount", "Параметры", "Например: 4 500 000 ₽"),
    "inflow": Question("inflow", "Через сколько месяцев расходы начнут возвращаться выручкой?", "Срок возврата должен соответствовать денежному циклу.", (
        c("one", "До месяца", inflow_months=1),
        c("three", "Через 2–3 месяца", inflow_months=3),
        c("six", "Через 4–6 месяцев", inflow_months=6),
        c("twelve", "Через 7–12 месяцев", inflow_months=12),
        c("later", "Позже года", inflow_months=24),
    ), "inflow_months", "Денежный цикл"),
    "business_age": Question("business_age", "Сколько времени работает бизнес?", "У банков бывают минимальные сроки деятельности заёмщика.", (
        c("new", "Меньше 6 месяцев", business_age_months=3),
        c("young", "6–12 месяцев", business_age_months=9),
        c("established", "1–3 года", business_age_months=24),
        c("mature", "Больше 3 лет", business_age_months=48),
    ), "business_age_months", "Профиль"),
    "legal_form": Question("legal_form", "Как зарегистрирован бизнес?", "От этого зависят требования к заёмщику и поручительству.", (
        c("ip", "ИП", legal_form="ip"),
        c("ooo", "ООО", legal_form="ooo"),
        c("other", "Другая форма", legal_form="other"),
    ), "legal_form", "Профиль"),
    "revenue": Question("revenue", "Какова средняя месячная выручка бизнеса?", "Она помогает оценить нагрузку относительно будущего займа.", (
        c("up_to_m", "До 1 млн ₽", revenue_monthly=500_000),
        c("one_to_five", "1–5 млн ₽", revenue_monthly=3_000_000),
        c("five_to_twenty", "5–20 млн ₽", revenue_monthly=10_000_000),
        c("more", "Больше 20 млн ₽", revenue_monthly=25_000_000),
        c("unknown", "Не знаю / новый бизнес", revenue_monthly=0),
    ), "revenue_monthly", "Профиль"),
    "cash_surplus": Question("cash_surplus", "Сколько остаётся в месяц после расходов и платежей по действующим кредитам?", "По свободному денежному потоку можно осторожно оценить посильность нового платежа; выручки для этого недостаточно.", (
        c("under_100k", "Меньше 100 тыс. ₽", free_cashflow_floor=0),
        c("100_300k", "100–300 тыс. ₽", free_cashflow_floor=100_000),
        c("300_1000k", "300 тыс. – 1 млн ₽", free_cashflow_floor=300_000),
        c("over_1000k", "Больше 1 млн ₽", free_cashflow_floor=1_000_000),
        c("unknown", "Не могу оценить", free_cashflow_floor=0),
    ), "free_cashflow_floor", "Профиль"),
    "collateral": Question("collateral", "Что можно предоставить в обеспечение?", "Обеспечение влияет на доступный лимит и структуру сделки.", (
        c("none", "Без залога", collateral="none"),
        c("property", "Имеющаяся недвижимость/техника", collateral="property"),
        c("purchased", "Приобретаемый актив", collateral="purchased_property"),
        c("goods", "Товары в обороте", collateral="goods"),
        c("rights", "Права по контракту", collateral="contract_rights"),
        c("guarantee", "Поручительство / гарантия", collateral="guarantee"),
    ), "collateral", "Профиль"),
    "debt": Question("debt", "Есть действующие кредиты или просрочки?", "Текущая нагрузка важна для реалистичного подбора.", (
        c("none", "Нет кредитов и просрочек", existing_debt=False, has_overdue=False),
        c("current", "Есть кредит, плачу вовремя", existing_debt=True, has_overdue=False),
        c("overdue", "Есть действующая просрочка", existing_debt=True, has_overdue=True),
        c("unsure", "Не уверен", existing_debt="unknown"),
    ), "existing_debt", "Профиль"),
}

# The purpose question is the same for every borrower, but its suggested answers
# follow the industry already selected. Free text still accepts any valid purpose.
PURPOSE_CHOICES_BY_INDUSTRY: dict[str, tuple[str, ...]] = {
    "agriculture": ("seeds", "inventory", "equipment", "gap", "contract", "gov_contract", "property", "refinance", "other"),
    "trade": ("inventory", "gap", "marketplace", "equipment", "property", "refinance", "other"),
    "production": ("inventory", "equipment", "gap", "contract", "gov_contract", "construction", "property", "refinance", "other"),
    "services": ("gap", "contract", "gov_contract", "equipment", "property", "refinance", "other"),
    "marketplace": ("marketplace", "inventory", "gap", "equipment", "refinance", "other"),
    "construction": ("construction", "contract", "gov_contract", "gap", "equipment", "property", "inventory", "refinance", "other"),
}


def choices_for_question(q: Question, profile: dict[str, Any] | None = None) -> tuple[Choice, ...]:
    if q.id != "purpose" or not profile:
        return q.choices
    ids = PURPOSE_CHOICES_BY_INDUSTRY.get(profile.get("industry"))
    if not ids:
        return q.choices
    by_id = {choice.id: choice for choice in q.choices}
    return tuple(by_id[id] for id in ids)

FIELD_LIMITS = {
    "amount": (100_000, 500_000_000), "inflow_months": (1, 240),
    "business_age_months": (0, 600), "revenue_monthly": (0, 1_000_000_000),
    "first_tranche_share": (0.01, 1.0), "urgency_days": (1, 365),
    "free_cashflow_floor": (0, 1_000_000_000),
}
ENUMS = {
    "industry": {"agriculture", "trade", "production", "services", "marketplace", "construction", "other"},
    "purpose": {"working_capital", "cash_gap", "seasonal", "investment", "equipment", "transport", "commercial_property", "construction", "marketplace", "commercial_contract", "government_contract", "refinance", "any_business", "opening_business", "franchise", "business_acquisition", "export", "import"},
    "funding_pattern": {"once", "tranches", "revolving", "unknown"},
    "collateral": {"none", "property", "purchased_property", "goods", "contract_rights", "guarantee"},
    "cashflow_cycle": {"seasonal", "regular", "short", "medium", "unknown"},
    "asset_status": {"ready", "search", "staged", "unknown"},
    "repayment_source": {"confirmed_receivable", "contract", "future_sales", "unknown"},
}
BOOLEAN_FIELDS = {"has_contract", "has_overdue"}
ALLOWED_FIELDS = set(FIELD_LIMITS) | set(ENUMS) | BOOLEAN_FIELDS | {"supplier_deferral", "existing_debt", "need_description", "cashflow_details", "legal_form"}


def validate_patch(raw: dict[str, Any]) -> dict[str, Any]:
    """Discard untrusted model fields and out-of-range values."""
    result = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        if key not in ALLOWED_FIELDS or value is None:
            continue
        if key in FIELD_LIMITS:
            low, high = FIELD_LIMITS[key]
            try:
                number = float(value)
            except (ValueError, TypeError):
                continue
            if low <= number <= high:
                result[key] = int(number) if key != "first_tranche_share" else number
        elif key in ENUMS and isinstance(value, str) and value in ENUMS[key]:
            result[key] = value
        elif key in BOOLEAN_FIELDS and isinstance(value, bool):
            result[key] = value
        elif key in {"supplier_deferral", "existing_debt"} and isinstance(value, (bool, str)) and value in (True, False, "possible", "unknown"):
            result[key] = value
        elif key in {"need_description", "cashflow_details"} and isinstance(value, str):
            result[key] = value[:500]
        elif key == "legal_form" and value in {"ip", "ooo", "other"}:
            result[key] = value
    return result


def question_order(profile: dict[str, Any]) -> list[str]:
    industry = profile.get("industry")
    purpose = profile.get("purpose")
    order = ["industry", "purpose"]
    if industry == "agriculture":
        order.append("agri_calendar")
    if industry == "marketplace":
        order.append("marketplace_cycle")
    if purpose in {"commercial_contract", "government_contract"}:
        order.append("contract_terms")
    if purpose in {"equipment", "transport", "commercial_property", "investment", "construction"}:
        order.append("asset_status")
    if purpose == "cash_gap":
        order += ["urgency", "gap_source"]
    order += ["spending_pattern"]
    if profile.get("funding_pattern") in {"tranches", "revolving"}:
        order.append("first_tranche")
    if purpose in {"seasonal", "working_capital", "equipment", "transport", "marketplace"}:
        order.append("supplier_deferral")
    order += ["amount", "inflow", "business_age", "legal_form", "revenue", "cash_surplus", "collateral", "debt"]
    return order


def next_question(profile: dict[str, Any], answered: list[str]) -> Question | None:
    for id in question_order(profile):
        q = QUESTIONS[id]
        if id not in answered and (not q.field or q.field not in profile):
            return q
    return None


def progress(profile: dict[str, Any], answered: list[str]) -> dict[str, Any]:
    order = question_order(profile)
    complete = sum(qid in answered or (QUESTIONS[qid].field in profile if QUESTIONS[qid].field else False) for qid in order)
    return {"answered": complete, "total": len(order), "percent": round(100 * complete / len(order))}


def question_payload(q: Question, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": q.id, "reply": q.title, "why": q.why, "stage": q.stage,
            "quick_replies": [{"id": x.id, "label": x.label, "input_required": x.input_required}
                              for x in choices_for_question(q, profile)], "input_hint": q.input_hint}


def enrich_free_text_answer(question: Question, answer: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Keep a custom agricultural schedule even when the AI cannot classify it."""
    if question.id == "agri_calendar":
        return {**patch, "cashflow_cycle": patch.get("cashflow_cycle", "unknown"),
                "cashflow_details": answer[:500]}
    return patch


def insights(profile: dict[str, Any]) -> list[str]:
    notes = []
    if profile.get("funding_pattern") in {"tranches", "revolving"}:
        share = profile.get("first_tranche_share")
        if share and profile.get("amount"):
            first = round(profile["amount"] * share)
            notes.append(f"На первый этап ориентировочно нужно {first:,.0f} ₽ из общего бюджета. Сравним выборку траншами с выдачей всей суммы сразу.".replace(",", " "))
        else:
            notes.append("Расходы идут этапами: стоит сравнить кредитную линию с разовой выдачей.")
    if profile.get("supplier_deferral") in {True, "possible"}:
        notes.append("Отсрочка поставщика может уменьшить нужный лимит и стоимость финансирования.")
    if profile.get("purpose") == "cash_gap" and profile.get("inflow_months", 99) <= 3:
        notes.append("Разрыв короткий: проверьте овердрафт и возобновляемую линию.")
    if profile.get("industry") == "agriculture" and profile.get("cashflow_cycle") == "seasonal":
        notes.append("График возврата стоит увязать с продажей урожая.")
    if profile.get("has_contract") is True:
        notes.append("Контракт может быть основанием для специализированного финансирования.")
    if profile.get("asset_status") == "search":
        notes.append("Объект ещё не выбран: ранняя выдача всей суммы может создать лишние проценты.")
    if profile.get("purpose") == "cash_gap" and profile.get("urgency_days", 365) <= 1:
        notes.append("При платеже сегодня стоит проверить отсрочку поставщика и доступный лимит на счёте: новый кредит может не успеть оформиться.")
    if profile.get("repayment_source") == "confirmed_receivable":
        notes.append("Подтверждённая дебиторка: помимо кредита проверьте факторинг как альтернативу.")
    return notes[:3]
