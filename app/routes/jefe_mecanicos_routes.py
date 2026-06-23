import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from sqlalchemy.sql import func

from app.database import get_db

from app.models.ticket_model import (
    Ticket,
    TicketStatus,
    TicketType,
)

from app.models.user_model import (
    User,
)

from app.models.ticket_asignacion_model import (
    TicketAsignacion,
    AsignacionStatus,
)

from app.models.ticket_historial_model import (
    TicketHistorial,
)

from app.models.ticket_comentario_model import (
    TicketComentario,
)

router = APIRouter(
    prefix="/jefe-mecanicos",
    tags=["Jefe Mecánicos"],
)


# ==========================================
# GET LOWEST LOAD MECHANIC
# ==========================================
def get_lowest_load_mechanic(
    db: Session
):
    mechanics = db.query(User).filter(
        User.role == "mecanico"
    ).all()

    if not mechanics:
        return None

    mechanic_ticket_counts = []

    for mechanic in mechanics:
        active_tickets = db.query(Ticket).filter(
            Ticket.assigned_to == mechanic.id,
            Ticket.status.in_([
                TicketStatus.asignado,
                TicketStatus.en_proceso,
                TicketStatus.pausado,
            ])
        ).count()

        mechanic_ticket_counts.append({
            "mechanic": mechanic,
            "count": active_tickets,
        })

    mechanic_ticket_counts.sort(
        key=lambda x: x["count"]
    )

    return mechanic_ticket_counts[0]["mechanic"]


# ==========================================
# GET PENDING TICKETS (ACTIVE TICKETS)
# ==========================================
@router.get("/tickets/pendientes")
def get_pending_tickets(
    db: Session = Depends(get_db),
):
    """
    Get all active tickets (not completed, validated, or closed)
    """
    try:
        tickets = db.query(Ticket).filter(
            Ticket.status.in_([
                TicketStatus.pendiente,
                TicketStatus.asignado,
                TicketStatus.en_proceso,
                TicketStatus.pausado,
            ])
        ).order_by(
            Ticket.created_at.desc()
        ).all()

        print(f"Found {len(tickets)} pending tickets")

        response = []
        
        for ticket in tickets:
            mechanic_name = None
            if ticket.assigned_to:
                mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
                if mechanic:
                    mechanic_name = mechanic.nombre
            
            ubicacion_value = "piso"
            if hasattr(ticket, 'ubicacion'):
                if hasattr(ticket.ubicacion, 'value'):
                    ubicacion_value = ticket.ubicacion.value
                elif ticket.ubicacion:
                    ubicacion_value = str(ticket.ubicacion)
            
            response.append({
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "ubicacion": ubicacion_value,
                "prioridad_general": getattr(ticket, 'prioridad_general', 'normal'),
                "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
                "assigned_mechanic_name": mechanic_name,
                "created_at": ticket.created_at,
            })

        return {
            "success": True,
            "tickets": response,
        }
        
    except Exception as e:
        print(f"Error in get_pending_tickets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching pending tickets: {str(e)}"
        )


# ==========================================
# GET COMPLETED/VALIDATED/CLOSED TICKETS (ONE FUNCTION - FIXED)
# ==========================================
@router.get("/tickets/completados")
def get_completed_tickets(
    db: Session = Depends(get_db),
):
    """
    Get all tickets that are completed, validated, or closed
    """
    try:
        tickets = db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.completado, TicketStatus.validado, TicketStatus.cerrado])
        ).order_by(
            Ticket.completed_at.desc()
        ).all()
        
        print(f"Found {len(tickets)} completed/validated/closed tickets")

        response = []
        
        for ticket in tickets:
            mechanic_name = None
            if ticket.assigned_to:
                mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
                if mechanic:
                    mechanic_name = mechanic.nombre
            
            solution_desc = getattr(ticket, 'solution_description', None)
            resolution_min = getattr(ticket, 'resolution_minutes', None)
            is_delayed = getattr(ticket, 'delayed', False)
            
            response.append({
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "solution_description": solution_desc,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "resolution_minutes": resolution_min,
                "delayed": is_delayed,
                "mechanic_name": mechanic_name,
                "completed_at": ticket.completed_at,
                "closed_at": ticket.closed_at,
            })
        
        return {
            "success": True,
            "tickets": response,
        }
        
    except Exception as e:
        print(f"Error in get_completed_tickets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching completed tickets: {str(e)}"
        )


# ==========================================
# GET CLOSED TICKETS ONLY
# ==========================================
@router.get("/tickets/cerrados")
def get_closed_tickets(
    db: Session = Depends(get_db),
):
    """
    Get all closed tickets only
    """
    try:
        tickets = db.query(Ticket).filter(
            Ticket.status == TicketStatus.cerrado
        ).order_by(
            Ticket.closed_at.desc()
        ).all()
        
        print(f"Found {len(tickets)} closed tickets")

        response = []
        
        for ticket in tickets:
            mechanic_name = None
            if ticket.assigned_to:
                mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
                if mechanic:
                    mechanic_name = mechanic.nombre
            
            resolution_min = getattr(ticket, 'resolution_minutes', None)
            is_delayed = getattr(ticket, 'delayed', False)
            
            response.append({
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "resolution_minutes": resolution_min,
                "delayed": is_delayed,
                "mechanic_name": mechanic_name,
                "closed_at": ticket.closed_at,
            })

        return {
            "success": True,
            "tickets": response,
        }
        
    except Exception as e:
        print(f"Error in get_closed_tickets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching closed tickets: {str(e)}"
        )


# ==========================================
# AUTO ASSIGN MECHANIC
# ==========================================
@router.post("/tickets/asignar")
def assign_mechanic(
    ticket_id: str,
    jefe_mecanicos_id: str,
    notas: str = None,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found",
            )

        mechanic = get_lowest_load_mechanic(db)

        if not mechanic:
            raise HTTPException(
                status_code=404,
                detail="No mechanics available",
            )

        ticket.assigned_to = mechanic.id
        ticket.assigned_by = jefe_mecanicos_id
        ticket.status = TicketStatus.asignado
        ticket.assigned_at = func.now()

        try:
            asignacion = TicketAsignacion(
                ticket_id=ticket_id,
                mecanico_id=mechanic.id,
                asignado_por=jefe_mecanicos_id,
                status=AsignacionStatus.asignado,
                notas=notas,
            )
        except AttributeError:
            asignacion = TicketAsignacion(
                ticket_id=ticket_id,
                mecanico_id=mechanic.id,
                asignado_por=jefe_mecanicos_id,
                status="asignado",
                notas=notas,
            )
        db.add(asignacion)

        historial = TicketHistorial(
            ticket_id=ticket_id,
            usuario_id=jefe_mecanicos_id,
            accion="ticket_asignado",
            descripcion=f"Ticket assigned to {mechanic.nombre}",
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "assigned_mechanic": {
                "id": str(mechanic.id),
                "nombre": mechanic.nombre,
                "username": mechanic.username,
            },
            "message": "Ticket assigned automatically",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in assign_mechanic: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error assigning ticket: {str(e)}"
        )


# ==========================================
# REASSIGN TICKET
# ==========================================
@router.post("/tickets/reasignar")
def reassign_ticket(
    ticket_id: str,
    nuevo_mecanico_id: str,
    jefe_mecanicos_id: str,
    notas: str = None,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found",
            )

        new_mechanic = db.query(User).filter(
            User.id == nuevo_mecanico_id,
            User.role == "mecanico"
        ).first()

        if not new_mechanic:
            raise HTTPException(
                status_code=404,
                detail="Mechanic not found",
            )

        old_mechanic_id = ticket.assigned_to
        ticket.assigned_to = new_mechanic.id
        ticket.assigned_by = jefe_mecanicos_id
        ticket.assigned_at = func.now()
        ticket.status = TicketStatus.asignado

        try:
            asignacion = TicketAsignacion(
                ticket_id=ticket_id,
                mecanico_id=new_mechanic.id,
                asignado_por=jefe_mecanicos_id,
                status=AsignacionStatus.asignado,
                notas=notas,
            )
        except AttributeError:
            asignacion = TicketAsignacion(
                ticket_id=ticket_id,
                mecanico_id=new_mechanic.id,
                asignado_por=jefe_mecanicos_id,
                status="asignado",
                notas=notas,
            )
        db.add(asignacion)

        historial = TicketHistorial(
            ticket_id=ticket_id,
            usuario_id=jefe_mecanicos_id,
            accion="ticket_reasignado",
            descripcion=f"Ticket reassigned from {old_mechanic_id} to {new_mechanic.nombre}",
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": f"Ticket reassigned successfully to {new_mechanic.nombre}",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in reassign_ticket: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error reassigning ticket: {str(e)}"
        )


# ==========================================
# UPDATE MECHANIC LOCATION
# ==========================================
@router.post("/mecanicos/location")
def update_mechanic_location(
    mecanico_id: str,
    location: str,
    db: Session = Depends(get_db),
):
    try:
        mechanic = db.query(User).filter(
            User.id == mecanico_id,
            User.role == "mecanico"
        ).first()

        if not mechanic:
            raise HTTPException(
                status_code=404,
                detail="Mechanic not found",
            )

        mechanic.current_location = location
        db.commit()

        return {
            "success": True,
            "message": "Location updated successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in update_mechanic_location: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating location: {str(e)}"
        )


# ==========================================
# GET MECHANIC TICKETS
# ==========================================
@router.get("/tickets/mecanico/{mecanico_id}")
def get_mechanic_tickets(
    mecanico_id: str,
    db: Session = Depends(get_db),
):
    try:
        tickets = db.query(Ticket).filter(
            Ticket.assigned_to == mecanico_id
        ).order_by(
            Ticket.created_at.desc()
        ).all()

        response = []

        for ticket in tickets:
            response.append({
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "created_at": ticket.created_at,
            })

        return {
            "success": True,
            "tickets": response,
        }
        
    except Exception as e:
        print(f"Error in get_mechanic_tickets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching mechanic tickets: {str(e)}"
        )


# ==========================================
# GET MECHANIC NAME
# ==========================================
@router.get("/mecanico/nombre/{mecanico_id}")
def get_mechanic_nombre(
    mecanico_id: str,
    db: Session = Depends(get_db),
):
    try:
        mechanic = db.query(User).filter(
            User.id == mecanico_id,
            User.role == "mecanico"
        ).first()

        if not mechanic:
            raise HTTPException(
                status_code=404,
                detail="Mechanic not found",
            )

        return {
            "success": True,
            "nombre": mechanic.nombre,
            "id": str(mechanic.id),
        }
        
    except Exception as e:
        print(f"Error in get_mechanic_nombre: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching mechanic: {str(e)}"
        )


# ==========================================
# START WORK ON TICKET
# ==========================================
@router.post("/tickets/iniciar")
def start_ticket_work(
    ticket_id: str,
    mecanico_id: str,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found",
            )

        ticket.status = TicketStatus.en_proceso
        ticket.started_at = func.now()

        historial = TicketHistorial(
            ticket_id=ticket_id,
            usuario_id=mecanico_id,
            accion="trabajo_iniciado",
            descripcion="Mechanic started work",
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": "Work started successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in start_ticket_work: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error starting work: {str(e)}"
        )


# ==========================================
# COMPLETE TICKET (MECHANIC)
# ==========================================
@router.post("/tickets/completar")
def complete_ticket(
    ticket_id: str,
    mecanico_id: str,
    comentario: str = None,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found",
            )

        ticket.status = TicketStatus.completado
        ticket.completed_at = func.now()

        if comentario:
            comment = TicketComentario(
                ticket_id=ticket_id,
                usuario_id=mecanico_id,
                comentario=comentario,
            )
            db.add(comment)

        historial = TicketHistorial(
            ticket_id=ticket_id,
            usuario_id=mecanico_id,
            accion="ticket_completado",
            descripcion="Mechanic completed ticket",
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": "Ticket completed successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in complete_ticket: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error completing ticket: {str(e)}"
        )


# ==========================================
# CLOSE TICKET (JEFE MECANICOS)
# ==========================================
@router.post("/tickets/cerrar")
def close_ticket(
    ticket_id: str,
    jefe_mecanicos_id: str,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found",
            )

        ticket.status = TicketStatus.cerrado
        ticket.closed_at = func.now()

        historial = TicketHistorial(
            ticket_id=ticket_id,
            usuario_id=jefe_mecanicos_id,
            accion="ticket_cerrado",
            descripcion="Ticket closed by jefe mecanicos",
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": "Ticket closed successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in close_ticket: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error closing ticket: {str(e)}"
        )