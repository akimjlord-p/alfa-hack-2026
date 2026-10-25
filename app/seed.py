from .database import (ApplicationEvent, Base, CreditApplication, CreditScenario, DemoAccount,
                       Source, WorkerJob, engine, SessionLocal)

ALFA="https://alfabank.ru/sme/profits/businesscredit/"
VTB="https://www.vtb.ru/malyj-biznes/kredity-i-garantii/"
VTB_EXPRESS="https://www.vtb.ru/malyj-biznes/kredity-i-garantii/express-online/kredit-dlya-malogo-biznesa/"
PSB="https://www.psbank.ru/business/loans/creditbusiness"
# bank, product, type, category, purpose, sum from/to, term from/to, rate from/to, collateral, age, leverage, time, source
OFFERS=[
("alfa-no-collateral","Альфа-Банк","Кредит одной суммой без залога","Оборотный кредит","liquidity",["working_capital","any_business","refinance"],300000,30000000,12,60,23.5,23.5,["none","guarantee"],9,24,"решение от 1 дня",ALFA),
("alfa-collateral","Альфа-Банк","Кредит одной суммой с залогом","Инвестиционный кредит","investment",["investment","equipment","transport","commercial_property","refinance"],500000,150000000,12,120,21.5,21.5,["property","purchased_property","guarantee"],9,36,"решение от 1 дня",ALFA),
("alfa-line","Альфа-Банк","Возобновляемая кредитная линия","Оборотный кредит","liquidity",["working_capital","cash_gap","seasonal"],300000,30000000,1,18,14.0,23.5,["none","goods","guarantee"],9,24,"индивидуально",ALFA),
("vtb-express","ВТБ","Экспресс-кредит для малого бизнеса","Экспресс-кредит","fast",["any_business","working_capital","cash_gap"],100000,30000000,1,36,25.5,25.5,["none"],0,12,"решение за 5 минут",VTB_EXPRESS),
("vtb-overdraft","ВТБ","Овердрафт","Овердрафт","liquidity",["cash_gap","working_capital"],100000,10000000,1,36,20.0,36.0,["none","guarantee"],6,8,"индивидуально",VTB),
("vtb-working","ВТБ","Пополнение оборотных средств","Оборотный кредит","liquidity",["working_capital","seasonal","industry"],500000,500000000,1,36,17.0,30.0,["none","goods","property","guarantee"],12,24,"индивидуально",VTB),
("vtb-capex","ВТБ","Финансирование капитальных затрат","Инвестиционный кредит","investment",["investment","equipment","transport","construction","industry"],1000000,500000000,12,144,14.0,25.0,["property","purchased_property","goods","guarantee"],12,36,"индивидуально",VTB),
("vtb-marketplace","ВТБ","Кредит для продавцов на маркетплейсах","Кредит для маркетплейсов","special",["marketplace"],100000,30000000,3,36,18.0,32.0,["none","goods","guarantee"],6,18,"индивидуально",VTB),
("vtb-gov","ВТБ","Кредит на Госзаказ","Контрактное финансирование","contract",["government_contract"],5000000,50000000,3,36,15.0,26.0,["contract_rights","guarantee"],12,24,"индивидуально",VTB),
("vtb-property","ВТБ","Кредит под залог приобретаемой недвижимости","Бизнес-ипотека","investment",["commercial_property"],1000000,500000000,12,144,14.0,24.0,["purchased_property"],12,36,"индивидуально",VTB),
("psb-business","ПСБ","Кредит-Бизнес","Кредит на развитие","investment",["working_capital","investment","equipment","transport","commercial_property","any_business"],10000000,500000000,12,180,16.0,30.0,["property","guarantee"],24,36,"5–10 рабочих дней",PSB),
("psb-contract","ПСБ","Контрактная логика","Контрактное финансирование","contract",["commercial_contract","government_contract"],500000,150000000,3,36,16.0,28.0,["contract_rights"],24,24,"5–10 рабочих дней",PSB)]

def bootstrap():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(CreditScenario).count():
            for x in OFFERS:
                db.add(CreditScenario(id=x[0],lender=x[1],offer_name=x[2],title=x[3],category=x[4],purposes=x[5],min_amount=x[6],max_amount=x[7],min_term=x[8],max_term=x[9],rate_from=x[10],rate_to=x[11],collateral=x[12],min_age_months=x[13],max_debt_to_revenue=x[14],processing_days=x[15],source_url=x[16],data_status="unverified",description=f"{x[2]} — публично описанный продукт {x[1]} (условия требуют проверки)."))
        # Previous demo worker marked seeded offers verified without checking terms.
        seed_ids={x[0] for x in OFFERS}
        for item in db.query(CreditScenario).filter(CreditScenario.id.in_(seed_ids)).all():
            if item.data_status == "verified": item.data_status="unverified"
        if not db.query(Source).count():
            db.add_all([Source(id="alfa",name="Альфа-Банк / бизнес-кредиты",url=ALFA,kind="official_page"),Source(id="vtb",name="ВТБ / кредиты для бизнеса",url=VTB,kind="official_page"),Source(id="psb",name="ПСБ / Кредит-Бизнес",url=PSB,kind="official_page")])
        if not db.query(DemoAccount).count():
            db.add_all([
                DemoAccount(id="demo-entrepreneur", username="entrepreneur_demo", password="entrepreneur-2026",
                            display_name="Ирина Власова · предприниматель", role="entrepreneur", token="demo-entrepreneur-token"),
                DemoAccount(id="demo-reviewer", username="reviewer_demo", password="reviewer-2026",
                            display_name="Алексей Морозов · кредитный эксперт", role="reviewer", token="demo-reviewer-token"),
            ])
        if not db.query(CreditApplication).count():
            demo_profile={"purpose":"cash_gap","amount":1_000_000,"inflow_months":2,"business_age_months":24,
                          "legal_form":"ip","revenue_monthly":3_000_000,"free_cashflow_floor":300_000,
                          "collateral":"none","has_overdue":False}
            approved=CreditApplication(id="demo-application-approved", offer_id="vtb-overdraft", applicant_name="Ирина Власова",
                company_name="ИП Власова", contact_email="irina@example.test", contact_phone="+7 900 000-00-01",
                requested_amount=1_000_000, profile=demo_profile, status="approved", decision="approved",
                reviewer_note="Демо-решение: предварительно одобрено. Финальные условия определяет кредитор.")
            clarification=CreditApplication(id="demo-application-info", offer_id="alfa-line", applicant_name="Максим Орлов",
                company_name="ООО «Север»", contact_email="maxim@example.test", contact_phone="+7 900 000-00-02",
                requested_amount=2_000_000, profile={**demo_profile,"has_overdue":True}, status="needs_info",
                reviewer_note="Уточните причину и статус действующей просрочки для демо-проверки.")
            db.add_all([approved, clarification])
            db.add_all([
                ApplicationEvent(application_id=approved.id,status="submitted",actor="Предприниматель",note="Демо-заявка создана."),
                ApplicationEvent(application_id=approved.id,status="under_review",actor="Автоматическая демо-проверка",note="Первичная проверка пройдена."),
                ApplicationEvent(application_id=approved.id,status="approved",actor="Алексей Морозов · кредитный эксперт",note=approved.reviewer_note),
                ApplicationEvent(application_id=clarification.id,status="submitted",actor="Предприниматель",note="Демо-заявка создана."),
                ApplicationEvent(application_id=clarification.id,status="needs_info",actor="Автоматическая демо-проверка",note=clarification.reviewer_note),
            ])
        if not db.query(WorkerJob).filter_by(status="queued").count(): db.add(WorkerJob(kind="refresh_sources",payload={}))
        db.commit()
