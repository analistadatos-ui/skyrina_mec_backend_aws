# app/routes/rh_routes.py
import uuid

from datetime import datetime, timezone, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ticket_model import Ticket, TicketStatus, TicketType
from app.models.user_model import User
from app.models.bono_model import BonoCierre

router = APIRouter(
    prefix="/rh",
    tags=["RH"],
)

BONO_MAX_MXN = 1000


# ==========================================
# HELPERS
# ==========================================

def get_week_monday(ref: date = None) -> str:
    """Return the Monday of the week containing ref (or today)."""
    ref = ref or date.today()
    monday = ref - timedelta(days=ref.weekday())
    return monday.isoformat()


def week_range(semana: str):
    """Return (start_dt, end_dt) as timezone-aware datetimes for the week."""
    monday = date.fromisoformat(semana)
    sunday = monday + timedelta(days=6)
    start = datetime.combine(monday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end   = datetime.combine(sunday, datetime.max.time()).replace(tzinfo=timezone.utc)
    return start, end


def get_afectacion_score(minutes: Optional[int]) -> float:
    """Score per ticket: <7 min = 100, 7-15 = 50, >15 = 0."""
    if minutes is None:
        return 0
    if minutes < 7:
        return 100
    if minutes <= 15:
        return 50
    return 0


def compute_kpis(tickets: list, start: datetime, end: datetime) -> dict:
    """
    Compute afectacion, cambios, orden for a date range.
    Mirrors the logic in the mechanic's BonoPage.jsx.
    """
    closed = [
        t for t in tickets
        if t.status == TicketStatus.cerrado
        and t.completed_at
        and start <= t.completed_at.replace(tzinfo=timezone.utc) <= end
    ]
    assigned = [
        t for t in tickets
        if t.status != TicketStatus.cancelado
        and t.created_at.replace(tzinfo=timezone.utc) <= end
    ]

    style_total  = [t for t in assigned if t.tipo == TicketType.cambio_estilo]
    style_closed = [t for t in closed   if t.tipo == TicketType.cambio_estilo]
    delayed      = [t for t in closed   if (t.resolution_minutes or 0) > 7]

    if closed:
        total_score = sum(get_afectacion_score(t.resolution_minutes) for t in closed)
        afectacion = round(total_score / len(closed), 1)
    else:
        afectacion = 0.0

    cambios = round((len(style_closed) / len(style_total)) * 100, 1) if style_total else 0.0
    orden   = round(((len(closed) - len(delayed)) / len(closed)) * 100, 1) if closed else 0.0

    bono_pct = round(afectacion * 0.5 + cambios * 0.25 + orden * 0.25, 1)
    monto    = round(BONO_MAX_MXN * bono_pct / 100)

    return {
        "afectacion_pct": afectacion,
        "cambios_pct": cambios,
        "orden_pct": orden,
        "bono_pct": bono_pct,
        "monto_bono_mxn": monto,
        "closed_count": len(closed),
        "assigned_count": len(assigned),
        "style_total": len(style_total),
        "style_closed": len(style_closed),
        "delayed_count": len(delayed),
    }


def get_or_create_semana(semana: str, db: Session) -> BonoCierre:
    """Get existing BonoCierre row or create an open one."""
    row = db.query(BonoCierre).filter(BonoCierre.semana == semana).first()
    if not row:
        row = BonoCierre(semana=semana, status="abierto", exclusiones=[], montos_individuales=[])
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_stored_montos(row: BonoCierre) -> dict:
    """Return {mecanico_id: monto_final_mxn} from the stored JSON column."""
    montos = getattr(row, 'montos_individuales', None) or []
    return {entry["mecanico_id"]: entry["monto_final_mxn"] for entry in montos}


def set_stored_monto(row: BonoCierre, mecanico_id: str, monto: int):
    """Upsert a single mechanic's final amount in the JSON column.

    IMPORTANT: We build a completely new list and reassign the attribute.
    SQLAlchemy cannot detect in-place mutations on JSON columns, so mutating
    the existing list (e.g. entry["key"] = val) is silently ignored and the
    change is never written to the database.
    """
    current = list(getattr(row, 'montos_individuales', None) or [])
    updated = [
        {**entry, "monto_final_mxn": monto}
        if entry["mecanico_id"] == mecanico_id
        else entry
        for entry in current
    ]
    if not any(e["mecanico_id"] == mecanico_id for e in current):
        updated.append({"mecanico_id": mecanico_id, "monto_final_mxn": monto})
    # Full reassignment triggers SQLAlchemy change tracking on JSON columns
    row.montos_individuales = updated


# ==========================================
# GET LIST OF WEEKS
# ==========================================
@router.get("/bonos/semanas")
def get_semanas(db: Session = Depends(get_db)):
    """Return the last 8 weeks. Auto-creates the current week if missing."""
    current = get_week_monday()
    get_or_create_semana(current, db)

    today = date.today()
    weeks = [
        (today - timedelta(days=today.weekday()) - timedelta(weeks=i)).isoformat()
        for i in range(8)
    ]

    rows = {
        r.semana: r
        for r in db.query(BonoCierre).filter(BonoCierre.semana.in_(weeks)).all()
    }

    result = []
    for semana in weeks:
        row = rows.get(semana)
        result.append({
            "semana":         semana,
            "cerrado":        row.status == "cerrado" if row else False,
            "monto_bono_mxn": row.monto_bono_mxn  if row else None,
            "bono_pct":       row.bono_pct         if row else None,
            "afectacion_pct": row.afectacion_pct   if row else None,
            "cambios_pct":    row.cambios_pct       if row else None,
            "orden_pct":      row.orden_pct         if row else None,
        })

    return {"success": True, "semanas": result}


# ==========================================
# GET WEEK DETAIL (live KPIs + mecanicos)
# ==========================================
@router.get("/bonos/semana/{semana}")
def get_semana_detail(semana: str, db: Session = Depends(get_db)):
    """
    Returns live-computed KPIs for the week + list of all mecanicos
    with their individual stats, any saved per-mechanic amounts, and exclusions.
    """
    try:
        date.fromisoformat(semana)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa YYYY-MM-DD")

    row = get_or_create_semana(semana, db)
    start, end = week_range(semana)

    all_tickets  = db.query(Ticket).all()
    global_kpis  = compute_kpis(all_tickets, start, end)
    stored_montos = get_stored_montos(row)

    # Per-mechanic breakdown
    mecanicos_db = db.query(User).filter(User.role == "mecanico").all()
    mecanicos = []
    for m in mecanicos_db:
        my_tickets = [t for t in all_tickets if str(t.assigned_to) == str(m.id)]
        kpi = compute_kpis(my_tickets, start, end)

        entry = {
            "id":               str(m.id),
            "nombre":           m.nombre,
            "email":            m.username,
            "asignacion":       m.current_location.value if m.current_location else "piso",
            "bono_pct":         kpi["bono_pct"],
            "afectacion_pct":   kpi["afectacion_pct"],
            "cambios_pct":      kpi["cambios_pct"],
            "orden_pct":        kpi["orden_pct"],
            "tickets_cerrados": kpi["closed_count"],
            "tickets_asignados": kpi["assigned_count"],
            # Always include the stored individual final amount if it exists.
            # None means RH has not yet adjusted this mechanic manually.
            "monto_final_mxn":  stored_montos.get(str(m.id)),
        }
        mecanicos.append(entry)

    # Global KPIs: use stored snapshot when closed, live otherwise
    if row.status == "cerrado":
        kpis = {
            "afectacion_pct": row.afectacion_pct,
            "cambios_pct":    row.cambios_pct,
            "orden_pct":      row.orden_pct,
            "bono_pct":       row.bono_pct,
            "monto_bono_mxn": row.monto_bono_mxn,
        }
    else:
        kpis = {
            "afectacion_pct": global_kpis["afectacion_pct"],
            "cambios_pct":    global_kpis["cambios_pct"],
            "orden_pct":      global_kpis["orden_pct"],
            "bono_pct":       global_kpis["bono_pct"],
            "monto_bono_mxn": global_kpis["monto_bono_mxn"],
        }

    return {
        "success":    True,
        "semana":     semana,
        "cerrado":    row.status == "cerrado",
        "cerrado_at": row.cerrado_at.isoformat() if row.cerrado_at else None,
        "exclusiones": row.exclusiones or [],
        **kpis,
        "mecanicos":  mecanicos,
    }


# ==========================================
# ADJUST A SINGLE MECHANIC'S BONUS (new)
# ==========================================
class AjustarMecanicoRequest(BaseModel):
    semana:          str
    mecanico_id:     str
    monto_final_mxn: int


@router.patch("/bonos/ajustar-mecanico")
def ajustar_mecanico(payload: AjustarMecanicoRequest, db: Session = Depends(get_db)):
    """
    Save (or update) the final bonus amount for a single mechanic for a given week.
    Can be called multiple times — each call is independent.
    The week must not be closed yet.
    """
    try:
        date.fromisoformat(payload.semana)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa YYYY-MM-DD")

    if payload.monto_final_mxn < 0:
        raise HTTPException(status_code=422, detail="El monto no puede ser negativo.")

    row = get_or_create_semana(payload.semana, db)

    if row.status == "cerrado":
        raise HTTPException(status_code=409, detail="Esta semana ya fue cerrada. No se puede modificar.")

    # Verify the mechanic exists
    mecanico = db.query(User).filter(
        User.id == uuid.UUID(payload.mecanico_id),
        User.role == "mecanico",
    ).first()
    if not mecanico:
        raise HTTPException(status_code=404, detail="Mecánico no encontrado.")

    set_stored_monto(row, payload.mecanico_id, payload.monto_final_mxn)
    db.commit()
    db.refresh(row)

    return {
        "success":        True,
        "semana":         payload.semana,
        "mecanico_id":    payload.mecanico_id,
        "monto_final_mxn": payload.monto_final_mxn,
    }



# ==========================================
# REABRIR BONO — unlock a closed week
# ==========================================
class ReabrirBonoRequest(BaseModel):
    semana:        str
    reabierto_por: Optional[str] = None


@router.post("/bonos/reabrir")
def reabrir_bono(payload: ReabrirBonoRequest, db: Session = Depends(get_db)):
    """
    Reopen a previously closed week so RH can adjust individual amounts
    or exclusions before closing again.
    Clears the cerrado_at timestamp and resets status to 'abierto'.
    Stored per-mechanic amounts and KPI snapshot are preserved so RH
    can see what was there and modify only what's needed.
    """
    try:
        date.fromisoformat(payload.semana)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa YYYY-MM-DD")

    row = db.query(BonoCierre).filter(BonoCierre.semana == payload.semana).first()
    if not row:
        raise HTTPException(status_code=404, detail="Semana no encontrada.")
    if row.status != "cerrado":
        raise HTTPException(status_code=409, detail="Esta semana no está cerrada.")

    row.status     = "abierto"
    row.cerrado_at = None

    # Optionally log who reopened it (if model has the column)
    if payload.reabierto_por and hasattr(row, 'reabierto_por'):
        try:
            row.reabierto_por = uuid.UUID(payload.reabierto_por)
        except ValueError:
            pass

    db.commit()
    db.refresh(row)

    return {
        "success": True,
        "semana":  row.semana,
        "status":  row.status,
    }

class CerrarBonoRequest(BaseModel):
    semana:      str
    exclusiones: list          # [{ "mecanico_id": "uuid", "nombre": "...", "motivo": "..." }]
    cerrado_por: Optional[str] = None


@router.post("/bonos/cerrar")
def cerrar_bono(payload: CerrarBonoRequest, db: Session = Depends(get_db)):
    """
    Close a week's bono period.
    Individual amounts must be saved first via PATCH /bonos/ajustar-mecanico.
    This endpoint only locks the week and records exclusions + KPI snapshot.
    """
    try:
        date.fromisoformat(payload.semana)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa YYYY-MM-DD")

    row = get_or_create_semana(payload.semana, db)

    if row.status == "cerrado":
        raise HTTPException(status_code=409, detail="Esta semana ya fue cerrada.")

    start, end = week_range(payload.semana)
    all_tickets = db.query(Ticket).all()
    kpis = compute_kpis(all_tickets, start, end)

    row.status        = "cerrado"
    row.exclusiones   = payload.exclusiones
    row.cerrado_at    = datetime.now(timezone.utc)
    row.afectacion_pct = kpis["afectacion_pct"]
    row.cambios_pct   = kpis["cambios_pct"]
    row.orden_pct     = kpis["orden_pct"]
    row.bono_pct      = kpis["bono_pct"]
    row.monto_bono_mxn = kpis["monto_bono_mxn"]

    if payload.cerrado_por:
        try:
            row.cerrado_por = uuid.UUID(payload.cerrado_por)
        except ValueError:
            pass

    db.commit()
    db.refresh(row)

    return {
        "success":    True,
        "semana":     row.semana,
        "bono_pct":   row.bono_pct,
        "cerrado_at": row.cerrado_at.isoformat(),
    }