import os, smtplib
from datetime import date, timedelta, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from app.database import get_db, SessionLocal
from app.models.simcard import SimCard, ActivityLog

load_dotenv()

router    = APIRouter(prefix="/notifications", tags=["notifications"])
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
scheduler = BackgroundScheduler()


# ── Settings page ─────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)

    # Load current .env settings (read-only display)
    settings = {
        "smtp_host":        os.getenv("SMTP_HOST", ""),
        "smtp_port":        os.getenv("SMTP_PORT", "587"),
        "smtp_user":        os.getenv("SMTP_USER", ""),
        "notify_email":     os.getenv("NOTIFY_EMAIL", ""),
        "line_token":       os.getenv("LINE_NOTIFY_TOKEN", ""),
        "alert_days":       os.getenv("ALERT_DAYS_BEFORE", "7,14,30"),
    }

    # Upcoming expiry list for display
    today    = date.today()
    expiring = db.query(SimCard).filter(
        SimCard.expiry_date != None,
        SimCard.expiry_date <= today + timedelta(days=30),
        SimCard.expiry_date >= today,
    ).order_by(SimCard.expiry_date).all()

    return templates.TemplateResponse("notifications.html", {
        "request": request, "settings": settings, "expiring": expiring,
        "success": request.query_params.get("success"),
    })


# ── Manual trigger ────────────────────────────────────────────
@router.post("/send-now")
async def send_now(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    count = _check_and_notify(db)
    return RedirectResponse(url=f"/notifications?success=ส่งการแจ้งเตือนแล้ว+{count}+รายการ", status_code=302)


# ── Core notification logic ───────────────────────────────────
def _check_and_notify(db: Session = None) -> int:
    """Check expiring SIMs and send alerts. Returns number of SIMs notified."""
    close_db = False
    if db is None:
        db       = SessionLocal()
        close_db = True

    try:
        alert_days_raw = os.getenv("ALERT_DAYS_BEFORE", "7,14,30")
        thresholds     = [int(d.strip()) for d in alert_days_raw.split(",")]
        today          = date.today()
        notified       = 0

        for days in thresholds:
            target_date = today + timedelta(days=days)
            sims = db.query(SimCard).filter(
                SimCard.expiry_date == target_date,
                SimCard.status == "active",
            ).all()

            for sim in sims:
                msg = (
                    f"⚠️ SIM แจ้งเตือน: {sim.phone_number} ({sim.carrier})\n"
                    f"ผู้ใช้: {sim.assigned_to or 'ไม่ระบุ'} | แผนก: {sim.department or 'ไม่ระบุ'}\n"
                    f"วันหมดอายุ: {sim.expiry_date} (อีก {days} วัน)"
                )
                _send_email(f"แจ้งเตือน SIM หมดอายุ — {sim.phone_number}", msg)
                _send_line(msg)

                db.add(ActivityLog(
                    action=f"แจ้งเตือนอัตโนมัติ: SIM {sim.phone_number} หมดอายุใน {days} วัน",
                    sim_id=sim.id,
                    timestamp=datetime.utcnow(),
                ))
                notified += 1

        db.commit()
        return notified
    finally:
        if close_db:
            db.close()


def _send_email(subject: str, body: str):
    host     = os.getenv("SMTP_HOST")
    port     = int(os.getenv("SMTP_PORT", "587"))
    user     = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_addr  = os.getenv("NOTIFY_EMAIL")

    if not all([host, user, password, to_addr]):
        print("[Notification] Email not configured — skipping")
        return
    try:
        msg            = MIMEMultipart()
        msg["From"]    = user
        msg["To"]      = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        print(f"[Notification] Email sent: {subject}")
    except Exception as e:
        print(f"[Notification] Email error: {e}")


def _send_line(message: str):
    token = os.getenv("LINE_NOTIFY_TOKEN")
    if not token:
        print("[Notification] LINE_NOTIFY_TOKEN not set — skipping")
        return
    try:
        with httpx.Client() as client:
            client.post(
                "https://notify-api.line.me/api/notify",
                headers={"Authorization": f"Bearer {token}"},
                data={"message": message},
                timeout=10,
            )
        print("[Notification] Line Notify sent")
    except Exception as e:
        print(f"[Notification] Line error: {e}")


# ── Background scheduler ──────────────────────────────────────
def start_scheduler():
    """Run daily at 08:00 to check expiring SIMs."""
    if not scheduler.running:
        scheduler.add_job(
            _check_and_notify,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_sim_check",
            replace_existing=True,
        )
        scheduler.start()
        print("⏰ Scheduler started — daily SIM expiry check at 08:00")
