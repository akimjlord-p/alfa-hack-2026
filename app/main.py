from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from .database import (ApplicationEvent, CreditApplication, DemoAccount, SessionLocal,
                       CreditScenario, MatchRun, IntakeSession, IntakeMessage, WorkerJob)
from .seed import bootstrap
from .ai import extract, strategy_preferences, close_client
from .questionnaire import VERSION, QUESTIONS, choices_for_question, next_question, question_payload, progress, validate_patch, insights, enrich_free_text_answer
from .matching import evaluate
from .workflow import FINAL_STATUSES, REVIEWER_TARGETS, STATUS_META, can_transition

app=FastAPI(title="akimai",version="1.0")

class Profile(BaseModel):
    amount:int=Field(ge=100000,le=500000000)
    term:int=Field(ge=1,le=240)
    purpose:str
    legal_form:str
    business_age_months:int=Field(ge=0,le=600)
    revenue_monthly:int=Field(ge=0)
    collateral:str
    has_overdue:bool=False

def db_session():
    db=SessionLocal()
    try: yield db
    finally: db.close()


class DemoLogin(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=3, max_length=120)


class ApplicationCreate(BaseModel):
    offer_id: str = Field(min_length=2, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)
    applicant_name: str = Field(min_length=2, max_length=140)
    company_name: str = Field(min_length=2, max_length=180)
    contact_email: EmailStr
    contact_phone: str = Field(min_length=6, max_length=40)
    requested_amount: int = Field(ge=100_000, le=500_000_000)


class ApplicationInfo(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class ApplicationTransition(BaseModel):
    status: str
    note: str = Field(min_length=3, max_length=1000)

@app.on_event("startup")
def startup(): bootstrap()

@app.on_event("shutdown")
def shutdown(): close_client()

@app.get("/api/health")
def health(): return {"status":"ok"}

@app.get("/api/scenarios")
def scenarios(db:Session=Depends(db_session)):
    return [{"id":x.id,"title":x.title,"description":x.description,"rate_from":x.rate_from,"rate_to":x.rate_to} for x in db.query(CreditScenario).all()]


def _application_payload(item: CreditApplication, db: Session) -> dict:
    offer = db.get(CreditScenario, item.offer_id)
    events = db.query(ApplicationEvent).filter_by(application_id=item.id).order_by(ApplicationEvent.id).all()
    title, status_description = STATUS_META.get(item.status, (item.status, ""))
    return {
        "id": item.id,
        "status": item.status,
        "status_title": title,
        "status_description": status_description,
        "decision": item.decision,
        "reviewer_note": item.reviewer_note,
        "applicant_name": item.applicant_name,
        "company_name": item.company_name,
        "requested_amount": item.requested_amount,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "offer": None if offer is None else {"id": offer.id, "lender": offer.lender, "name": offer.offer_name, "title": offer.title},
        "events": [{"status": event.status, "status_title": STATUS_META.get(event.status, (event.status, ""))[0],
                    "actor": event.actor, "note": event.note, "created_at": event.created_at.isoformat()} for event in events],
    }


def _reviewer(authorization: str | None, demo_token: str | None, db: Session) -> DemoAccount:
    # The public preview is behind nginx Basic Auth, which owns the standard
    # Authorization header. Keep a separate header for the in-app demo role so
    # the reviewer cabinet can work on the published IP as well as locally.
    token = (demo_token or authorization or "").removeprefix("Bearer ").strip()
    account = db.query(DemoAccount).filter_by(token=token, role="reviewer").first()
    if account is None:
        raise HTTPException(status_code=401, detail="Нужна авторизация сотрудника демо-кабинета")
    return account


@app.post("/api/demo/login")
def demo_login(payload: DemoLogin, db: Session = Depends(db_session)):
    account = db.query(DemoAccount).filter_by(username=payload.username, password=payload.password).first()
    if account is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль демо-аккаунта")
    return {"token": account.token, "role": account.role, "display_name": account.display_name}


@app.get("/api/demo/accounts")
def demo_accounts(db: Session = Depends(db_session)):
    return [{"username": account.username, "display_name": account.display_name, "role": account.role}
            for account in db.query(DemoAccount).order_by(DemoAccount.role, DemoAccount.username).all()]


@app.post("/api/applications", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(db_session)):
    offer = db.get(CreditScenario, payload.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Предложение не найдено")
    profile: dict = {}
    if payload.session_id:
        session = db.get(IntakeSession, payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Сессия анкеты не найдена")
        profile = {key: value for key, value in (session.profile or {}).items() if not key.startswith("_")}
    item = CreditApplication(
        id=uuid4().hex, offer_id=offer.id, session_id=payload.session_id,
        applicant_name=payload.applicant_name.strip(), company_name=payload.company_name.strip(),
        contact_email=str(payload.contact_email), contact_phone=payload.contact_phone.strip(),
        requested_amount=payload.requested_amount, profile=profile, status="submitted",
    )
    db.add(item)
    db.add(ApplicationEvent(application_id=item.id, status="submitted", actor="Предприниматель",
                            note="Заявка создана в демо-кабинете и поставлена в очередь первичной проверки."))
    db.add(WorkerJob(kind="precheck_application", payload={"application_id": item.id}))
    db.commit()
    db.refresh(item)
    return _application_payload(item, db)


@app.get("/api/applications/{application_id}")
def get_application(application_id: str, db: Session = Depends(db_session)):
    item = db.get(CreditApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return _application_payload(item, db)


@app.post("/api/applications/{application_id}/provide-info")
def provide_application_info(application_id: str, payload: ApplicationInfo, db: Session = Depends(db_session)):
    item = db.get(CreditApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if item.status != "needs_info":
        raise HTTPException(status_code=409, detail="Уточнение можно отправить только для заявки со статусом «Нужны уточнения»")
    item.status = "submitted"
    item.decision = None
    item.reviewer_note = None
    db.add(ApplicationEvent(application_id=item.id, status="submitted", actor="Предприниматель",
                            note=f"Предприниматель добавил уточнение: {payload.note.strip()}"))
    db.add(WorkerJob(kind="precheck_application", payload={"application_id": item.id}))
    db.commit()
    return _application_payload(item, db)


@app.get("/api/reviewer/applications")
def reviewer_applications(authorization: str | None = Header(default=None),
                          demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
                          db: Session = Depends(db_session)):
    _reviewer(authorization, demo_token, db)
    items = db.query(CreditApplication).order_by(CreditApplication.updated_at.desc()).all()
    return {"applications": [_application_payload(item, db) for item in items]}


@app.post("/api/reviewer/applications/{application_id}/transition")
def reviewer_transition(application_id: str, payload: ApplicationTransition,
                        authorization: str | None = Header(default=None),
                        demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
                        db: Session = Depends(db_session)):
    reviewer = _reviewer(authorization, demo_token, db)
    item = db.get(CreditApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if payload.status not in REVIEWER_TARGETS or not can_transition(item.status, payload.status):
        raise HTTPException(status_code=409, detail="Этот переход статуса недоступен")
    item.status = payload.status
    item.reviewer_note = payload.note.strip()
    item.decision = payload.status if payload.status in FINAL_STATUSES else None
    db.add(ApplicationEvent(application_id=item.id, status=item.status, actor=reviewer.display_name,
                            note=item.reviewer_note))
    db.commit()
    return _application_payload(item, db)

@app.get("/api/questionnaire")
def questionnaire_map():
    return {"version":VERSION,"questions":[question_payload(q) for q in QUESTIONS.values()]}

def to_card(x:CreditScenario,p:Profile,context:dict|None=None,ai_preferences:set[str]|None=None):
    fit=evaluate(x,p,context,ai_preferences)
    if fit is None:return None
    score=fit["score"]
    level="высокое соответствие" if score>=85 else "среднее соответствие" if score>=70 else "требует проверки"
    warnings=list(fit["warnings"])
    if p.has_overdue:warnings.append("Действующая просрочка требует отдельного решения кредитора; рейтинг не означает доступность продукта.")
    return {"id":x.id,"lender":x.lender,"offer_name":x.offer_name,"title":x.title,"category":x.category,"description":x.description,"score":score,"level":level,"breakdown":fit["breakdown"],"reasons":fit["reasons"],"warnings":warnings,"instrument":fit["instrument"],"estimated_monthly_payment":fit["estimated_monthly_payment"],"amount":{"from":x.min_amount,"to":x.max_amount},"term":{"from":x.min_term,"to":x.max_term},"rate":{"from":x.rate_from,"to":x.rate_to},"collateral":x.collateral,"processing_days":x.processing_days,"source_url":x.source_url,"freshness":x.data_status}

def build_feed(db:Session,profile:Profile,context:dict|None=None,ai_preferences:set[str]|None=None):
    candidates=[to_card(x,profile,context,ai_preferences) for x in db.query(CreditScenario).all()]
    return sorted((x for x in candidates if x is not None),key=lambda x:(-x["score"],x["id"]))

@app.post("/api/match")
def match(profile:Profile,db:Session=Depends(db_session)):
    candidates=build_feed(db,profile)
    db.add(MatchRun(profile=profile.model_dump(),result_count=len(candidates))); db.commit()
    return {"feed":candidates,"explanation":"Сначала проверяются цель, сумма и обеспечение; затем начисляются баллы за инструмент, денежный цикл, профиль, оценку платежа и сроки. Это не вероятность одобрения.","data_status":"Условия каталога требуют подтверждения у банка; карточка показывает ориентир, а не оферту."}

class UserTurn(BaseModel):
    text:str=Field(default="",max_length=3000)
    choice_id:str|None=None



def history_for(db:Session,session_id:str):
    return [{"role":m.role,"content":m.content} for m in db.query(IntakeMessage).filter_by(session_id=session_id).order_by(IntakeMessage.id).all()]

def make_profile(raw:dict):
    required={"amount","purpose","inflow_months","business_age_months","legal_form","revenue_monthly","collateral"}
    if not required.issubset(raw): return None
    try:
        term=max(3,min(240,int(raw["inflow_months"])*2))
        return Profile(amount=int(raw["amount"]),term=term,purpose=raw["purpose"],legal_form=raw.get("legal_form","ip"),business_age_months=int(raw["business_age_months"]),revenue_monthly=int(raw["revenue_monthly"]),collateral=raw["collateral"],has_overdue=bool(raw.get("has_overdue",False)))
    except (ValueError,TypeError,KeyError): return None

def turn_payload(item:IntakeSession, q=None, mode="demo", feed=None, ranking_mode="rules_only"):
    profile=item.profile or {}
    answered=profile.get("_answered",[])
    if q is None:q=next_question(profile,answered)
    base=question_payload(q,profile) if q else {"id":None,"reply":"Профиль собран. Ниже — предложения по вашим параметрам.","why":"","stage":"Результат","quick_replies":[],"input_hint":""}
    return {"question":base,"reply":base["reply"],"quick_replies":base["quick_replies"],"progress":progress(profile,answered),"insights":insights(profile),"profile":{k:v for k,v in profile.items() if not k.startswith("_")},"ready":q is None and make_profile(profile) is not None,"mode":mode,"ranking_mode":ranking_mode,"feed":feed,"version":VERSION}

@app.post("/api/intake/start")
def intake_start(db:Session=Depends(db_session)):
    item=IntakeSession(id=uuid4().hex,profile={"_answered":[]},state="active",provider="yandex")
    db.add(item)
    opening=turn_payload(item,mode="intro")
    db.add(IntakeMessage(session_id=item.id,role="assistant",content=opening["reply"],metadata_json={"question_id":opening["question"]["id"],"version":VERSION}));db.commit()
    return {"session_id":item.id,**opening}

@app.post("/api/intake/{session_id}/message")
def intake_message(session_id:str,turn:UserTurn,db:Session=Depends(db_session)):
    item=db.get(IntakeSession,session_id)
    if not item: raise HTTPException(status_code=404,detail="Сессия не найдена")
    raw=item.profile or {}
    answered=list(raw.get("_answered",[]))
    current=next_question(raw,answered)
    if current is None:
        profile=make_profile(raw)
        if profile:
            ai_preferences,ranking_mode=strategy_preferences(raw)
            return turn_payload(item,mode="completed",feed=build_feed(db,profile,raw,ai_preferences),ranking_mode=ranking_mode)
        return turn_payload(item,mode="completed",feed=[])
    if turn.choice_id:
        selected=next((x for x in choices_for_question(current,raw) if x.id==turn.choice_id),None)
        if selected is None: raise HTTPException(status_code=422,detail="Вариант не относится к текущему вопросу")
        if selected.input_required:
            return {**turn_payload(item,mode="input_requested"),"hint":"Опишите ответ в поле ниже и нажмите «Отправить»."}
        patch=validate_patch(selected.facts)
        answer=selected.label
        mode="choice"
        if not patch and selected.id not in {"unknown", "custom"}:
            return {**turn_payload(item,mode=mode),"hint":"Опишите ответ своими словами в поле ниже."}
    else:
        answer=turn.text.strip()
        if len(answer)<2: raise HTTPException(status_code=422,detail="Напишите ответ или выберите вариант")
        patch,mode=extract(answer,current,{k:v for k,v in raw.items() if not k.startswith("_")})
        patch=enrich_free_text_answer(current,answer,patch)
    if not patch and turn.choice_id != "unknown":
        return {**turn_payload(item,mode=mode),"hint":"Не удалось определить ответ. Уточните его или выберите вариант."}
    updated={**raw,**patch}
    # A free answer may contain several facts. Still mark the active question only
    # if its own field was extracted, so the interview never silently skips it.
    if current.field in patch or (current.id=="debt" and ("existing_debt" in patch or "has_overdue" in patch)) or turn.choice_id=="unknown":
        answered.append(current.id)
    updated["_answered"]=answered
    item.profile=updated
    db.add(IntakeMessage(session_id=session_id,role="user",content=answer,metadata_json={"question_id":current.id,"choice_id":turn.choice_id,"facts":patch,"version":VERSION}))
    next_q=next_question(updated,answered)
    feed=None
    ranking_mode="rules_only"
    if next_q is None:
        profile=make_profile(updated)
        if profile is not None:
            item.state="ready"
            ai_preferences,ranking_mode=strategy_preferences(updated)
            feed=build_feed(db,profile,updated,ai_preferences)
    result=turn_payload(item,q=next_q,mode=mode,feed=feed,ranking_mode=ranking_mode)
    db.add(IntakeMessage(session_id=session_id,role="assistant",content=result["reply"],metadata_json={"question_id":result["question"]["id"],"version":VERSION}));db.commit()
    return result

DIST=Path(__file__).parents[1]/"dist"
@app.get("/")
def index(): return FileResponse(DIST/"index.html")
