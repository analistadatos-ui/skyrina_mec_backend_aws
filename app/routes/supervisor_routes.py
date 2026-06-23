# app/routes/supervisor_routes.py
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from pydantic import BaseModel

from app.database import get_db
from app.models.ticket_model import Ticket, TicketStatus, TicketType
from app.models.user_model import User
from app.models.checklist_model import Checklist


# ==========================================
# PYDANTIC MODELS
# ==========================================
class ChecklistSubmitRequest(BaseModel):
    items: List[Dict[str, Any]]


router = APIRouter(
    prefix="/supervisor",
    tags=["Supervisor"],
)


# ==========================================
# GET DASHBOARD STATS
# ==========================================
@router.get("/dashboard/stats")
def get_supervisor_stats(
    db: Session = Depends(get_db),
):
    """
    Get global statistics for supervisor dashboard
    """
    try:
        # Get all tickets (excluding cancelled)
        all_tickets = db.query(Ticket).filter(Ticket.status != TicketStatus.cancelado).all()
        
        # Active tickets (not completed, validated, or closed)
        active_tickets = db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.pendiente, TicketStatus.asignado, TicketStatus.en_proceso, TicketStatus.pausado])
        ).count()
        
        # Completed tickets (completado, validado, cerrado)
        completed_tickets = db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.completado, TicketStatus.validado, TicketStatus.cerrado])
        ).all()
        
        # Tickets pending validation
        pending_validation = db.query(Ticket).filter(
            Ticket.status == TicketStatus.completado
        ).count()
        
        # Calculate average resolution time
        total_minutes = sum(t.resolution_minutes or 0 for t in completed_tickets)
        avg_resolution = round(total_minutes / len(completed_tickets), 1) if completed_tickets else 0
        
        # Calculate global KPIs
        total_assigned = len(all_tickets)
        total_closed = len([t for t in completed_tickets if t.status == TicketStatus.cerrado])
        
        # Afectación (Completion Rate)
        afectacion = round((total_closed / total_assigned) * 100, 1) if total_assigned > 0 else 0
        
        # Cambios (Style Changes)
        style_changes = db.query(Ticket).filter(Ticket.tipo == TicketType.cambio_estilo).all()
        closed_style_changes = len([t for t in style_changes if t.status == TicketStatus.cerrado])
        cambios = round((closed_style_changes / len(style_changes)) * 100, 1) if style_changes else 100
        
        # Orden (Quality - on time)
        delayed_tickets = len([t for t in completed_tickets if t.delayed])
        orden = round(((len(completed_tickets) - delayed_tickets) / len(completed_tickets)) * 100, 1) if completed_tickets else 100
        
        # Get tickets for the table (last 20)
        recent_tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(20).all()
        
        tickets_data = []
        for ticket in recent_tickets:
            # Get mechanic name
            mechanic_name = None
            if ticket.assigned_to:
                mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
                if mechanic:
                    mechanic_name = mechanic.nombre
            
            # Get line number
            line_number = None
            if ticket.linea_id:
                from app.models.linea_model import Linea
                line = db.query(Linea).filter(Linea.id == ticket.linea_id).first()
                if line:
                    line_number = line.numero
            
            tickets_data.append({
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "prioridad": ticket.prioridad_general.value if hasattr(ticket.prioridad_general, "value") else str(ticket.prioridad_general),
                "linea_numero": line_number,
                "mechanic_name": mechanic_name,
                "resolution_minutes": ticket.resolution_minutes,
                "created_at": ticket.created_at,
            })
        
        return {
            "success": True,
            "stats": {
                "avgClosing": avg_resolution,
                "activeTickets": active_tickets,
                "pendingValidation": pending_validation,
                "totalTickets": total_assigned,
                "closedTickets": total_closed,
            },
            "kpis": {
                "afectacion": afectacion,
                "cambios": cambios,
                "orden": orden,
            },
            "tickets": tickets_data,
        }
        
    except Exception as e:
        print(f"Error in get_supervisor_stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET LINE PERFORMANCE
# ==========================================
@router.get("/lines/performance")
def get_lines_performance(
    db: Session = Depends(get_db),
):
    """
    Get performance metrics for each line
    """
    try:
        from app.models.linea_model import Linea
        
        lines = db.query(Linea).filter(Linea.activa == True).all()
        
        result = []
        for line in lines:
            tickets = db.query(Ticket).filter(Ticket.linea_id == line.id).all()
            
            total = len(tickets)
            closed = len([t for t in tickets if t.status == TicketStatus.cerrado])
            delayed = len([t for t in tickets if t.delayed])
            
            total_minutes = sum(t.resolution_minutes or 0 for t in tickets)
            avg_time = round(total_minutes / len(tickets), 1) if tickets else 0
            
            # Active tickets count
            active = len([t for t in tickets if t.status in [TicketStatus.pendiente, TicketStatus.asignado, TicketStatus.en_proceso]])
            
            result.append({
                "linea_id": str(line.id),
                "linea_numero": line.numero,
                "linea_nombre": line.nombre,
                "total_tickets": total,
                "closed_tickets": closed,
                "active_tickets": active,
                "delayed_tickets": delayed,
                "avg_resolution_minutes": avg_time,
                "completion_rate": round((closed / total) * 100, 1) if total > 0 else 0,
            })
        
        return {
            "success": True,
            "lines": result,
        }
        
    except Exception as e:
        print(f"Error in get_lines_performance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET MECHANICS PERFORMANCE
# ==========================================
@router.get("/mechanics/performance")
def get_mechanics_performance(
    db: Session = Depends(get_db),
):
    """
    Get performance metrics for each mechanic
    """
    try:
        mechanics = db.query(User).filter(User.role == "mecanico").all()
        
        result = []
        for mechanic in mechanics:
            tickets = db.query(Ticket).filter(Ticket.assigned_to == mechanic.id).all()
            
            total = len(tickets)
            closed = len([t for t in tickets if t.status == TicketStatus.cerrado])
            delayed = len([t for t in tickets if t.delayed])
            
            total_minutes = sum(t.resolution_minutes or 0 for t in tickets)
            avg_time = round(total_minutes / len(tickets), 1) if tickets else 0
            
            # Active tickets count
            active = len([t for t in tickets if t.status in [TicketStatus.pendiente, TicketStatus.asignado, TicketStatus.en_proceso]])
            
            result.append({
                "mecanico_id": str(mechanic.id),
                "mecanico_nombre": mechanic.nombre,
                "mecanico_username": mechanic.username,
                "total_tickets": total,
                "closed_tickets": closed,
                "active_tickets": active,
                "delayed_tickets": delayed,
                "avg_resolution_minutes": avg_time,
                "completion_rate": round((closed / total) * 100, 1) if total > 0 else 0,
                "current_location": mechanic.current_location,
            })
        
        # Sort by completion rate descending
        result.sort(key=lambda x: x["completion_rate"], reverse=True)
        
        return {
            "success": True,
            "mechanics": result,
        }
        
    except Exception as e:
        print(f"Error in get_mechanics_performance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET TODAY'S CHECKLIST
# ==========================================
@router.get("/checklist/today")
def get_today_checklist(
    db: Session = Depends(get_db),
):
    """
    Get today's checklist or create a new one if it doesn't exist
    """
    try:
        today = date.today()
        
        # Check if checklist exists for today
        checklist = db.query(Checklist).filter(
            Checklist.date == today
        ).first()
        
        if checklist:
            # Return existing checklist for today
            return {
                "success": True,
                "checklist": {
                    "id": str(checklist.id),
                    "date": checklist.date.isoformat(),
                    "items": checklist.items,
                    "completed": checklist.completed,
                    "submitted_at": checklist.submitted_at.isoformat() if checklist.submitted_at else None,
                }
            }
        else:
            # No checklist for today - create a fresh one with all items unchecked
            default_items = [
                {"label": "Área limpia", "checked": False, "category": "limpieza"},
                {"label": "Herramientas ordenadas", "checked": False, "category": "organizacion"},
                {"label": "Máquinas apagadas", "checked": False, "category": "seguridad"},
                {"label": "Piso limpio", "checked": False, "category": "limpieza"},
                {"label": "Botiquín completo", "checked": False, "category": "seguridad"},
                {"label": "Extintores en lugar visible", "checked": False, "category": "seguridad"},
                {"label": "Señalización visible", "checked": False, "category": "organizacion"},
                {"label": "Basura retirada", "checked": False, "category": "limpieza"},
            ]
            
            return {
                "success": True,
                "checklist": {
                    "id": None,
                    "date": today.isoformat(),
                    "items": default_items,
                    "completed": False,
                    "submitted_at": None,
                }
            }
        
    except Exception as e:
        print(f"Error in get_today_checklist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SUBMIT CHECKLIST
# ==========================================
@router.post("/checklist/submit")
def submit_checklist(
    request: ChecklistSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Submit today's checklist
    """
    try:
        today = date.today()
        items = request.items
        
        if not items:
            raise HTTPException(status_code=400, detail="No checklist items provided")
        
        # Validate that all items have required fields
        for item in items:
            if "label" not in item or "checked" not in item:
                raise HTTPException(status_code=400, detail="Invalid checklist item format")
        
        # Check if checklist already exists for today
        checklist = db.query(Checklist).filter(
            Checklist.date == today
        ).first()
        
        if checklist:
            # Update existing
            checklist.items = items
            checklist.completed = True
            checklist.submitted_at = datetime.now()
        else:
            # Create new
            checklist = Checklist(
                id=uuid.uuid4(),
                date=today,
                items=items,
                completed=True,
                submitted_at=datetime.now(),
            )
            db.add(checklist)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Checklist submitted successfully",
            "checklist_id": str(checklist.id),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in submit_checklist: {str(e)}")
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET CHECKLIST HISTORY
# ==========================================
@router.get("/checklist/history")
def get_checklist_history(
    limit: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Get checklist submission history
    """
    try:
        checklists = db.query(Checklist).order_by(Checklist.date.desc()).limit(limit).all()
        
        result = []
        for c in checklists:
            completed_items = len([item for item in c.items if item.get("checked")])
            total_items = len(c.items)
            
            result.append({
                "id": str(c.id),
                "date": c.date.isoformat(),
                "completed_items": completed_items,
                "total_items": total_items,
                "completion_percentage": round((completed_items / total_items) * 100) if total_items > 0 else 0,
                "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
            })
        
        return {
            "success": True,
            "history": result,
        }
        
    except Exception as e:
        print(f"Error in get_checklist_history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# ==========================================
# GET CHECKLIST BY DATE
# ==========================================
@router.get("/checklist/date/{checklist_date}")
def get_checklist_by_date(
    checklist_date: str,
    db: Session = Depends(get_db),
):
    """
    Get checklist for a specific date (YYYY-MM-DD)
    """
    try:
        target_date = date.fromisoformat(checklist_date)
        
        checklist = db.query(Checklist).filter(
            Checklist.date == target_date
        ).first()
        
        if not checklist:
            return {
                "success": True,
                "checklist": None,
                "message": f"No checklist found for {checklist_date}"
            }
        
        return {
            "success": True,
            "checklist": {
                "id": str(checklist.id),
                "date": checklist.date.isoformat(),
                "items": checklist.items,
                "completed": checklist.completed,
                "submitted_at": checklist.submitted_at.isoformat() if checklist.submitted_at else None,
            }
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        print(f"Error in get_checklist_by_date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))