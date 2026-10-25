"""Queue worker. URL reachability does not verify financial product terms."""
import time
from datetime import datetime, timezone
import httpx
from .database import ApplicationEvent, CreditApplication, CreditScenario, SessionLocal, Source, WorkerJob
from .seed import bootstrap
from .workflow import precheck

def process_one():
    with SessionLocal() as db:
        # User-facing application checks take priority over slow source reachability checks.
        job=db.query(WorkerJob).filter_by(status="queued", kind="precheck_application").order_by(WorkerJob.id).first()
        if job is None:
            job=db.query(WorkerJob).filter_by(status="queued").order_by(WorkerJob.id).first()
        if not job:return False
        job.status="running"; db.commit()
        now=datetime.now(timezone.utc)
        if job.kind=="refresh_sources":
            for source in db.query(Source).all():
                try:
                    response=httpx.get(source.url,follow_redirects=True,timeout=10)
                    source.status="reachable_unverified" if response.status_code<400 else "unreachable"
                except httpx.HTTPError:
                    source.status="unreachable"
                source.last_checked_at=now
        elif job.kind == "precheck_application":
            application_id = (job.payload or {}).get("application_id")
            application = db.get(CreditApplication, application_id)
            if application is not None and application.status == "submitted":
                offer = db.get(CreditScenario, application.offer_id)
                if offer is None:
                    application.status = "needs_info"
                    note = "Не удалось найти выбранное предложение в демо-каталоге."
                else:
                    result = precheck(application.profile or {}, application.requested_amount, offer.min_amount, offer.max_amount)
                    application.status = result.status
                    note = result.note
                db.add(ApplicationEvent(application_id=application.id, status=application.status,
                                        actor="Автоматическая демо-проверка", note=note))
        job.status="completed"; job.completed_at=now; db.commit(); return True

if __name__=="__main__":
    bootstrap()
    while True:
        if not process_one(): time.sleep(5)
