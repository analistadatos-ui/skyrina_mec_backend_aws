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
from app.models.cambio_estilo_model import CambioEstilo
from app.models.linea_model import Linea
from app.models.system_config_model import SystemConfig, DEFAULTS

router = APIRouter(
    prefix="/rh",
    tags=["RH"],
)


# ==========================================
# CONFIG HELPERS
# ==========================================

def _get_config(db: Session) -> dict:
    """Return all config keys merged with defaults."""
    rows = db.query(SystemConfig).all()
    stored = {r.key: r.value for r in rows}
    return {**DEFAULTS, **stored}


def _upsert_config(db: Session, key: str, value: str) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemConfig(key=key, value=value))


def get_bono_max(db: Session) -> int:
    """Read bono_maximo from DB config, fall back to default."""
    cfg = _get_config(db)
    return int(float(cfg.get("bono_maximo", DEFAULTS["bono_maximo"])))


def get_tiempo_thresholds(db: Session) -> tuple[float, float]:
    """Return (meta_tiempo_100, meta_tiempo_0) from DB config."""
    cfg = _get_config(db)
    t100 = float(cfg.get("meta_tiempo_100", DEFAULTS["meta_tiempo_100"]))
    t0   = float(cfg.get("meta_tiempo_0",   DEFAULTS["meta_tiempo_0"]))
    return t100, t0


# ==========================================
# SYSTEM CONFIG ROUTES
# GET  /rh/config
# PUT  /rh/config
# ==========================================

@router.get("/config")
def get_system_config(db: Session = Depends(get_db)):
    """Return all system configuration parameters."""
    try:
        return {"success": True, "config": _get_config(db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching config: {str(e)}")


@router.put("/config")
def update_system_config(payload: dict, db: Session = Depends(get_db)):
    """
    Upsert one or more system config keys.
    Only keys present in DEFAULTS are accepted; unknown keys are ignored.
    """
    try:
        allowed = set(DEFAULTS.keys())
        updated = {}
        for key, value in payload.items():
            if key not in allowed:
                continue
            str_val = str(value).strip()
            if not str_val:
                continue
            _upsert_config(db, key, str_val)
            updated[key] = str_val
        db.commit()
        return {"success": True, "updated": updated, "config": _get_config(db)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


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


def get_afectacion_score(minutes: Optional[int], t100: float, t0: float) -> float:
    """
    Linear decay score:
      <= t100 min  → 100
      >= t0   min  → 0
      between      → linear interpolation
    """
    if minutes is None:
        return 0
    if minutes <= t100:
        return 100
    if minutes >= t0:
        return 0
    slope = 100 / (t0 - t100)
    return 100 - slope * (minutes - t100)


def compute_kpis(tickets: list, start: datetime, end: datetime,
                 t100: float, t0: float, bono_max: int) -> dict:
    """
    Compute afectacion, cambios, orden for a date range using live config params.
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

    # Cumulative closed as of the end of this week (no lower bound), mirroring the
    # cumulative `assigned` filter above. This is ONLY for the dashboard's
    # "asignados vs cerrados" view, so both sides sit on the same (cumulative)
    # basis. It is intentionally NOT used by the weekly bonus math below, which
    # must keep using the week-scoped `closed` list.
    closed_all = [
        t for t in tickets
        if t.status == TicketStatus.cerrado
        and t.completed_at
        and t.completed_at.replace(tzinfo=timezone.utc) <= end
    ]

    style_total  = [t for t in assigned if t.tipo == TicketType.cambio_estilo]
    style_closed = [t for t in closed   if t.tipo == TicketType.cambio_estilo]
    delayed      = [t for t in closed   if (t.resolution_minutes or 0) > t100]

    if closed:
        total_score = sum(
            get_afectacion_score(t.resolution_minutes, t100, t0) for t in closed
        )
        afectacion = round(total_score / len(closed), 1)
    else:
        afectacion = 0.0

    cambios = round((len(style_closed) / len(style_total)) * 100, 1) if style_total else 0.0
    orden   = round(((len(closed) - len(delayed)) / len(closed)) * 100, 1) if closed else 0.0

    bono_pct = round(afectacion * 0.5 + cambios * 0.25 + orden * 0.25, 1)
    monto    = round(bono_max * bono_pct / 100)

    return {
        "afectacion_pct": afectacion,
        "cambios_pct":    cambios,
        "orden_pct":      orden,
        "bono_pct":       bono_pct,
        "monto_bono_mxn": monto,
        "closed_count":   len(closed),
        "closed_count_all": len(closed_all),  # cumulative (dashboard only, not bonus)
        "assigned_count": len(assigned),
        "style_total":    len(style_total),
        "style_closed":   len(style_closed),
        "delayed_count":  len(delayed),
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
    """
    Upsert a single mechanic's final amount in the JSON column.
    Full reassignment is required — SQLAlchemy cannot detect in-place
    mutations on JSON columns.
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

    row   = get_or_create_semana(semana, db)
    start, end = week_range(semana)

    # Load live config params
    t100, t0   = get_tiempo_thresholds(db)
    bono_max   = get_bono_max(db)

    all_tickets   = db.query(Ticket).all()
    global_kpis   = compute_kpis(all_tickets, start, end, t100, t0, bono_max)
    stored_montos = get_stored_montos(row)

    # Per-mechanic breakdown
    mecanicos_db = db.query(User).filter(User.role == "mecanico").all()
    mecanicos = []
    for m in mecanicos_db:
        my_tickets = [t for t in all_tickets if str(t.assigned_to) == str(m.id)]
        kpi = compute_kpis(my_tickets, start, end, t100, t0, bono_max)
        mecanicos.append({
            "id":                str(m.id),
            "nombre":            m.nombre,
            "email":             m.username,
            "asignacion":        m.current_location.value if m.current_location else "piso",
            "bono_pct":          kpi["bono_pct"],
            "afectacion_pct":    kpi["afectacion_pct"],
            "cambios_pct":       kpi["cambios_pct"],
            "orden_pct":         kpi["orden_pct"],
            "tickets_cerrados":  kpi["closed_count_all"],   # cumulative (matches asignados basis)
            "tickets_cerrados_semana": kpi["closed_count"], # week-scoped (still available if needed)
            "tickets_asignados": kpi["assigned_count"],     # cumulative as of week end
            "monto_bono_mxn":    kpi["monto_bono_mxn"],
            "monto_final_mxn":   stored_montos.get(str(m.id)),
        })

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
# ADJUST A SINGLE MECHANIC'S BONUS
# ==========================================
class AjustarMecanicoRequest(BaseModel):
    semana:          str
    mecanico_id:     str
    monto_final_mxn: int


@router.patch("/bonos/ajustar-mecanico")
def ajustar_mecanico(payload: AjustarMecanicoRequest, db: Session = Depends(get_db)):
    """
    Save (or update) the final bonus amount for a single mechanic for a given week.
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
        "success":         True,
        "semana":          payload.semana,
        "mecanico_id":     payload.mecanico_id,
        "monto_final_mxn": payload.monto_final_mxn,
    }


# ==========================================
# REABRIR BONO
# ==========================================
class ReabrirBonoRequest(BaseModel):
    semana:        str
    reabierto_por: Optional[str] = None


@router.post("/bonos/reabrir")
def reabrir_bono(payload: ReabrirBonoRequest, db: Session = Depends(get_db)):
    """Reopen a previously closed week so RH can adjust amounts or exclusions."""
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

    if payload.reabierto_por and hasattr(row, 'reabierto_por'):
        try:
            row.reabierto_por = uuid.UUID(payload.reabierto_por)
        except ValueError:
            pass

    db.commit()
    db.refresh(row)

    return {"success": True, "semana": row.semana, "status": row.status}


# ==========================================
# CERRAR BONO
# ==========================================
class CerrarBonoRequest(BaseModel):
    semana:      str
    exclusiones: list
    cerrado_por: Optional[str] = None


@router.post("/bonos/cerrar")
def cerrar_bono(payload: CerrarBonoRequest, db: Session = Depends(get_db)):
    """
    Close a week's bono period. Locks the week and records exclusions + KPI snapshot
    using the config params active at close time.
    """
    try:
        date.fromisoformat(payload.semana)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato inválido. Usa YYYY-MM-DD")

    row = get_or_create_semana(payload.semana, db)

    if row.status == "cerrado":
        raise HTTPException(status_code=409, detail="Esta semana ya fue cerrada.")

    start, end  = week_range(payload.semana)
    t100, t0    = get_tiempo_thresholds(db)
    bono_max    = get_bono_max(db)
    all_tickets = db.query(Ticket).all()
    kpis        = compute_kpis(all_tickets, start, end, t100, t0, bono_max)

    row.status         = "cerrado"
    row.exclusiones    = payload.exclusiones
    row.cerrado_at     = datetime.now(timezone.utc)
    row.afectacion_pct = kpis["afectacion_pct"]
    row.cambios_pct    = kpis["cambios_pct"]
    row.orden_pct      = kpis["orden_pct"]
    row.bono_pct       = kpis["bono_pct"]
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

# ==========================================
# HISTORIAL — yearly bonus history
# GET /rh/bonos/historial/{anio}
# ==========================================
# Returns, for the given year, the total paid and a per-month breakdown,
# aggregated from CLOSED bono weeks (BonoCierre.status == "cerrado").
# Shape matches HistorialPage.jsx:
#   { success, anio, total_pagado, meses: [ { mes, total_pagado, promedio_bono_pct } ] }
# ==========================================

_MESES_ES = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]


@router.get("/bonos/historial/{anio}")
def get_historial(anio: int, db: Session = Depends(get_db)):
    """
    Yearly bonus history. Aggregates CLOSED bono weeks by month.
    total_pagado uses sum of montos_individuales (actual per-mechanic
    confirmed amounts), falling back to monto_final_mxn then monto_bono_mxn.
    """
    closed_rows = (
        db.query(BonoCierre)
        .filter(BonoCierre.status == "cerrado")
        .all()
    )

    buckets: dict[int, dict] = {}
    total_pagado = 0

    for row in closed_rows:
        try:
            week_date = date.fromisoformat(row.semana)
        except (ValueError, TypeError):
            continue

        if week_date.year != anio:
            continue

        # Use actual per-mechanic confirmed payouts when available
        montos_ind = getattr(row, "montos_individuales", None) or []
        if montos_ind:
            monto = sum(entry.get("monto_final_mxn", 0) for entry in montos_ind)
        elif row.monto_final_mxn is not None:
            monto = row.monto_final_mxn
        else:
            monto = row.monto_bono_mxn or 0

        pct = row.bono_pct if row.bono_pct is not None else 0
        total_pagado += monto

        m = week_date.month
        if m not in buckets:
            buckets[m] = {"montos": [], "pcts": []}
        buckets[m]["montos"].append(monto)
        buckets[m]["pcts"].append(pct)

    meses = []
    for month_num in sorted(buckets.keys()):
        data = buckets[month_num]
        mes_total = sum(data["montos"])
        promedio = (
            round(sum(data["pcts"]) / len(data["pcts"]), 1)
            if data["pcts"]
            else 0.0
        )
        meses.append({
            "mes": _MESES_ES[month_num - 1],
            "total_pagado": mes_total,
            "promedio_bono_pct": promedio,
        })

    return {
        "success": True,
        "anio": anio,
        "total_pagado": total_pagado,
        "meses": meses,
    }


# ==========================================
# GET SEMANAS FOR A SPECIFIC YEAR
# GET /rh/bonos/semanas-anio/{anio}
# Returns all BonoCierre rows for the year, newest first.
# Used by HistorialPage weekly table.
# ==========================================
@router.get("/bonos/semanas-anio/{anio}")
def get_semanas_anio(anio: int, db: Session = Depends(get_db)):
    """Return all bono weeks for the given calendar year."""
    rows = db.query(BonoCierre).all()

    result = []
    for row in rows:
        try:
            week_date = date.fromisoformat(row.semana)
        except (ValueError, TypeError):
            continue
        if week_date.year != anio:
            continue

        montos_ind = getattr(row, "montos_individuales", None) or []
        if montos_ind:
            total_pagado_semana = sum(e.get("monto_final_mxn", 0) for e in montos_ind)
        elif row.monto_final_mxn is not None:
            total_pagado_semana = row.monto_final_mxn
        else:
            total_pagado_semana = row.monto_bono_mxn

        result.append({
            "semana":         row.semana,
            "cerrado":        row.status == "cerrado",
            "bono_pct":       row.bono_pct,
            "monto_bono_mxn": row.monto_bono_mxn,
            "total_pagado":   total_pagado_semana,
            "afectacion_pct": row.afectacion_pct,
            "cambios_pct":    row.cambios_pct,
            "orden_pct":      row.orden_pct,
            "cerrado_at":     row.cerrado_at.isoformat() if row.cerrado_at else None,
        })

    result.sort(key=lambda x: x["semana"], reverse=True)
    return {"success": True, "semanas": result}

# ==========================================
# REPORTE DE CAMBIOS DE ESTILO
# GET /rh/reportes/cambios?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
# ==========================================
# Returns style-change tickets in the date range, joined with their
# cambio detail (estilo origen/destino), the line, and the mechanic.
# Shape matches ReportesPage.jsx:
#   { success, total_cambios, promedio_tiempo_min, cambios: [ {...} ] }
# ==========================================
from fastapi import Query


@router.get("/reportes/cambios")
def reporte_cambios(
    desde: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    hasta: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    # Validate dates
    try:
        d_start = date.fromisoformat(desde)
        d_end = date.fromisoformat(hasta)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD")

    start_dt = datetime.combine(d_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(d_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    # All style-change tickets in range
    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.tipo == TicketType.cambio_estilo,
            Ticket.created_at >= start_dt,
            Ticket.created_at <= end_dt,
        )
        .order_by(Ticket.created_at.desc())
        .all()
    )

    # Preload lookups to avoid N+1
    lineas = {str(l.id): l for l in db.query(Linea).all()}
    users = {str(u.id): u for u in db.query(User).all()}

    cambios = []
    total_tiempo = 0.0
    tiempo_count = 0

    for t in tickets:
        detail = (
            db.query(CambioEstilo)
            .filter(CambioEstilo.ticket_id == t.id)
            .first()
        )

        linea = lineas.get(str(t.linea_id)) if t.linea_id else None
        linea_label = (
            getattr(linea, "nombre", None)
            or (f"Línea {linea.numero}" if linea and getattr(linea, "numero", None) else "—")
        )

        mecanico = users.get(str(t.assigned_to)) if t.assigned_to else None
        mecanico_nombre = mecanico.nombre if mecanico else "Sin asignar"

        tiempo = t.resolution_minutes if t.resolution_minutes is not None else 0
        if t.resolution_minutes is not None:
            total_tiempo += t.resolution_minutes
            tiempo_count += 1

        cambios.append({
            "fecha": t.created_at.date().isoformat() if t.created_at else None,
            "linea": linea_label,
            "estilo_origen": detail.estilo_actual if detail else "—",
            "estilo_destino": detail.nuevo_estilo if detail else "—",
            "tiempo_min": float(tiempo),
            # machine counts are not stored on CambioEstilo.
            # Returning 0 keeps the frontend table happy; add fields later if needed.
            "maquinas_mantienen": 0,
            "maquinas_agregar": 0,
            "mecanico": mecanico_nombre,
            "motivo": detail.observaciones if detail else None,
        })

    promedio = round(total_tiempo / tiempo_count, 1) if tiempo_count else 0.0

    return {
        "success": True,
        "total_cambios": len(cambios),
        "promedio_tiempo_min": promedio,
        "cambios": cambios,
    }