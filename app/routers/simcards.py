from datetime import date, datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, asc, desc
import qrcode, io, base64, os

from app.database import get_db
from app.models.simcard import SimCard, ActivityLog

router = APIRouter(prefix="/simcards", tags=["simcards"])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

CARRIERS    = ["AIS", "DTAC", "TRUE", "NT", "other"]
DEPARTMENTS = ["IT", "Sales", "HR", "Finance", "Operations", "Management", "other"]
STATUSES    = ["active", "inactive", "suspended", "expired"]

SORT_MAP = {
    "phone_number":    SimCard.phone_number,
    "carrier":         SimCard.carrier,
    "status":          SimCard.status,
    "department":      SimCard.department,
    "assigned_to":     SimCard.assigned_to,
    "expiry_date":     SimCard.expiry_date,
    "monthly_cost":    SimCard.monthly_cost,
    "activation_date": SimCard.activation_date,
    "created_at":      SimCard.created_at,
}


def _log(db, request, action, sim_id=None, detail=None):
    db.add(ActivityLog(
        user_id=request.session.get("user_id"),
        sim_id=sim_id, action=action, detail=detail,
        timestamp=datetime.utcnow(),
    ))


@router.get("", response_class=HTMLResponse)
async def list_simcards(
    request: Request,
    q: str = "",
    status: str = "",
    carrier: str = "",
    department: str = "",
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    db: Session = Depends(get_db),
):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)

    query = db.query(SimCard)
    if q:
        query = query.filter(or_(
            SimCard.iccid.ilike(f"%{q}%"),
            SimCard.phone_number.ilike(f"%{q}%"),
            SimCard.assigned_to.ilike(f"%{q}%"),
        ))
    if status:
        query = query.filter(SimCard.status == status)
    if carrier:
        query = query.filter(SimCard.carrier == carrier)
    if department:
        query = query.filter(SimCard.department == department)

    sort_col = SORT_MAP.get(sort, SimCard.created_at)
    query = query.order_by(asc(sort_col) if order == "asc" else desc(sort_col))

    total_count = query.count()
    per_page    = 15
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    sims        = query.offset((page - 1) * per_page).limit(per_page).all()

    all_carriers    = sorted({r[0] for r in db.query(SimCard.carrier).distinct().all() if r[0]})
    all_departments = sorted({r[0] for r in db.query(SimCard.department).distinct().all() if r[0]})

    return templates.TemplateResponse("simcards.html", {
        "request":         request,
        "sims":            sims,
        "q":               q,
        "status":          status,
        "carrier":         carrier,
        "department":      department,
        "sort":            sort,
        "order":           order,
        "page":            page,
        "total_pages":     total_pages,
        "total_count":     total_count,
        "all_carriers":    all_carriers,
        "all_departments": all_departments,
        "statuses":        STATUSES,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_form(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("simcard_form.html", {
        "request": request, "sim": None,
        "carriers": CARRIERS, "departments": DEPARTMENTS, "statuses": STATUSES,
        "error": None,
    })


@router.post("/new")
async def create_sim(
    request: Request,
    iccid: str           = Form(...),
    phone_number: str    = Form(...),
    carrier: str         = Form(...),
    status: str          = Form("active"),
    plan: str            = Form(""),
    assigned_to: str     = Form(""),
    department: str      = Form(""),
    activation_date: str = Form(""),
    expiry_date: str     = Form(""),
    monthly_cost: float  = Form(0),
    notes: str           = Form(""),
    db: Session          = Depends(get_db),
):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    if db.query(SimCard).filter(SimCard.iccid == iccid).first():
        return templates.TemplateResponse("simcard_form.html", {
            "request": request, "sim": None,
            "carriers": CARRIERS, "departments": DEPARTMENTS, "statuses": STATUSES,
            "error": f"ICCID {iccid} มีอยู่แล้วในระบบ",
        })
    sim = SimCard(
        iccid=iccid.strip(), phone_number=phone_number.strip(),
        carrier=carrier, status=status, plan=plan,
        assigned_to=assigned_to, department=department,
        activation_date=date.fromisoformat(activation_date) if activation_date else date.today(),
        expiry_date=date.fromisoformat(expiry_date) if expiry_date else None,
        monthly_cost=monthly_cost, notes=notes,
    )
    db.add(sim)
    db.flush()
    _log(db, request, f"เพิ่ม SIM {phone_number}", sim.id)
    db.commit()
    return RedirectResponse(url="/simcards", status_code=302)


@router.get("/{sim_id}/edit", response_class=HTMLResponse)
async def edit_form(sim_id: int, request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    sim = db.query(SimCard).filter(SimCard.id == sim_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="ไม่พบ SIM")
    return templates.TemplateResponse("simcard_form.html", {
        "request": request, "sim": sim,
        "carriers": CARRIERS, "departments": DEPARTMENTS, "statuses": STATUSES,
        "error": None,
    })


@router.post("/{sim_id}/edit")
async def update_sim(
    sim_id: int, request: Request,
    phone_number: str    = Form(...),
    carrier: str         = Form(...),
    status: str          = Form("active"),
    plan: str            = Form(""),
    assigned_to: str     = Form(""),
    department: str      = Form(""),
    activation_date: str = Form(""),
    expiry_date: str     = Form(""),
    monthly_cost: float  = Form(0),
    notes: str           = Form(""),
    db: Session          = Depends(get_db),
):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    sim = db.query(SimCard).filter(SimCard.id == sim_id).first()
    if not sim:
        raise HTTPException(status_code=404)
    sim.phone_number    = phone_number
    sim.carrier         = carrier
    sim.status          = status
    sim.plan            = plan
    sim.assigned_to     = assigned_to
    sim.department      = department
    sim.activation_date = date.fromisoformat(activation_date) if activation_date else sim.activation_date
    sim.expiry_date     = date.fromisoformat(expiry_date) if expiry_date else None
    sim.monthly_cost    = monthly_cost
    sim.notes           = notes
    sim.updated_at      = datetime.utcnow()
    _log(db, request, f"แก้ไข SIM {phone_number}", sim.id)
    db.commit()
    return RedirectResponse(url="/simcards", status_code=302)


@router.post("/{sim_id}/delete")
async def delete_sim(sim_id: int, request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    sim = db.query(SimCard).filter(SimCard.id == sim_id).first()
    if sim:
        _log(db, request, f"ลบ SIM {sim.phone_number}", None, f"ICCID: {sim.iccid}")
        db.delete(sim)
        db.commit()
    return RedirectResponse(url="/simcards", status_code=302)


@router.get("/{sim_id}/qr")
async def generate_qr(sim_id: int, request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=302)
    sim = db.query(SimCard).filter(SimCard.id == sim_id).first()
    if not sim:
        raise HTTPException(status_code=404)
    qr_data = f"ICCID:{sim.iccid}|TEL:{sim.phone_number}|CARRIER:{sim.carrier}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Content-Disposition": f"inline; filename=sim_{sim.iccid}.png"})


@router.get("/api/qr/{iccid}")
async def qr_base64(iccid: str, request: Request):
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401)
    img = qrcode.make(iccid)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"qr": f"data:image/png;base64,{b64}"}
