from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
import os

from app.database import get_db
from app.models.simcard import SimCard, Budget

router = APIRouter(tags=["dashboard"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)

    total       = db.query(func.count(SimCard.id)).scalar()
    active      = db.query(func.count(SimCard.id)).filter(SimCard.status == "active").scalar()
    inactive    = db.query(func.count(SimCard.id)).filter(SimCard.status == "inactive").scalar()
    suspended   = db.query(func.count(SimCard.id)).filter(SimCard.status == "suspended").scalar()

    # SIM expiring within 30 days
    today       = date.today()
    expiring    = db.query(SimCard).filter(
        SimCard.expiry_date != None,
        SimCard.expiry_date <= today + timedelta(days=30),
        SimCard.expiry_date >= today,
        SimCard.status == "active",
    ).order_by(SimCard.expiry_date).all()

    # Monthly cost by carrier
    carrier_costs = db.query(
        SimCard.carrier,
        func.sum(SimCard.monthly_cost).label("total"),
    ).filter(SimCard.status == "active").group_by(SimCard.carrier).all()

    # Cost by department
    dept_costs = db.query(
        SimCard.department,
        func.sum(SimCard.monthly_cost).label("total"),
        func.count(SimCard.id).label("count"),
    ).filter(SimCard.status == "active").group_by(SimCard.department).all()

    total_monthly = db.query(func.sum(SimCard.monthly_cost)).filter(
        SimCard.status == "active"
    ).scalar() or 0

    # Budget comparison
    budgets = db.query(Budget).all()
    budget_map = {b.department: float(b.monthly_budget) for b in budgets}

    dept_budget_data = []
    for row in dept_costs:
        dept_name = row.department or "ไม่ระบุแผนก"
        actual    = float(row.total or 0)
        budget    = budget_map.get(dept_name, 0)
        dept_budget_data.append({
            "department": dept_name,
            "actual":     actual,
            "budget":     budget,
            "over":       actual > budget > 0,
        })

    recent = db.query(SimCard).order_by(SimCard.created_at.desc()).limit(5).all()

    return templates.TemplateResponse("dashboard.html", {
        "request":          request,
        "total":            total,
        "active":           active,
        "inactive":         inactive,
        "suspended":        suspended,
        "expiring":         expiring,
        "carrier_costs":    [{"carrier": r.carrier, "total": float(r.total or 0)} for r in carrier_costs],
        "dept_budget_data": dept_budget_data,
        "total_monthly":    float(total_monthly),
        "recent":           recent,
    })
