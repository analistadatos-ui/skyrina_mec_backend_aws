import uuid

from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.ticket_model import (
    Ticket,
    TicketStatus,
)

from app.models.user_model import (
    User,
)

from app.models.falla_equipo_model import (
    FallaEquipo,
)

router = APIRouter(
    prefix="/mecanico",
    tags=["Mecanico"],
)


# ==========================================
# GET MY TICKETS
# ==========================================
@router.get("/tickets/{mecanico_id}")
def get_my_tickets(
    mecanico_id: str,
    db: Session = Depends(get_db),
):
    mechanic = db.query(User).filter(
        User.id == mecanico_id,
        User.role == "mecanico"
    ).first()

    if not mechanic:
        raise HTTPException(
            status_code=404,
            detail="Mechanic not found",
        )

    tickets = db.query(Ticket).filter(
        Ticket.assigned_to == mechanic.id
    ).order_by(
        Ticket.created_at.desc()
    ).all()

    response = []
    for ticket in tickets:
        # =====================================
        # FALLA EQUIPO DATA
        # =====================================
        falla = db.query(FallaEquipo).filter(
            FallaEquipo.ticket_id == ticket.id
        ).first()

        response.append({
            "id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "titulo": ticket.titulo,
            "descripcion": ticket.descripcion,
            "tipo": (
                ticket.tipo.value
                if hasattr(ticket.tipo, "value")
                else str(ticket.tipo)
            ),
            "status": (
                ticket.status.value
                if hasattr(ticket.status, "value")
                else str(ticket.status)
            ),
            "ubicacion": (
                ticket.ubicacion.value
                if hasattr(ticket.ubicacion, "value")
                else str(ticket.ubicacion)
            ),
            "prioridad_general": ticket.prioridad_general,
            "area": (
                falla.area
                if falla
                else None
            ),
            "maquina_nombre": (
                falla.maquina_nombre
                if falla
                else None
            ),
            "maquina_codigo": (
                falla.maquina_codigo
                if falla
                else None
            ),
            "image_url": (
                falla.image_url
                if falla
                else None
            ),
            "observaciones": (
                falla.observaciones
                if falla
                else None
            ),
            "created_at": ticket.created_at,
            # =====================================
            # ADDED TIMER FIELDS
            # =====================================
            "resolution_minutes": getattr(ticket, 'resolution_minutes', None),
            "delayed": getattr(ticket, 'delayed', False),
            "completed_at": str(ticket.completed_at) if ticket.completed_at else None,
        })

    return {
        "success": True,
        "tickets": response,
    }


# ==========================================
# START TICKET TIMER
# ==========================================
@router.post("/ticket/start/{ticket_id}")
def start_ticket(

    ticket_id: str,

    db: Session = Depends(get_db),
):

    ticket = db.query(Ticket).filter(

        Ticket.id ==
        uuid.UUID(ticket_id)

    ).first()

    if not ticket:

        raise HTTPException(

            status_code=404,

            detail="Ticket not found",
        )

    # =====================================
    # BLOCK COMPLETED TICKETS
    # =====================================

    if ticket.status == TicketStatus.completado:

        raise HTTPException(

            status_code=403,

            detail="This ticket is already completed and closed"
        )

    # =====================================
    # START ONLY ONCE
    # =====================================

    if not ticket.started_at:

        ticket.started_at = datetime.now(
            timezone.utc
        )

        ticket.status = (
            TicketStatus.en_proceso
        )

        db.commit()

    return {

        "success": True,

        "message":
            "Ticket timer started",
    }

# ==========================================
# COMPLETE TICKET
# ==========================================
@router.post("/ticket/complete/{ticket_id}")
def complete_ticket(

    ticket_id: str,

    payload: dict,

    db: Session = Depends(get_db),
):

    ticket = db.query(Ticket).filter(

        Ticket.id ==
        uuid.UUID(ticket_id)

    ).first()

    if not ticket:

        raise HTTPException(

            status_code=404,

            detail="Ticket not found",
        )

    # =====================================
    # BLOCK DUPLICATE COMPLETE
    # =====================================

    if ticket.status == TicketStatus.completado:

        raise HTTPException(

            status_code=403,

            detail="Ticket already completed"
        )

    now = datetime.now(
        timezone.utc
    )

    # =====================================
    # UPDATE STATUS
    # =====================================

    ticket.status = (
        TicketStatus.completado
    )

    ticket.completed_at = now

    # =====================================
    # SOLUTION DESCRIPTION
    # =====================================

    ticket.solution_description = (
        payload.get(
            "solution_description"
        )
    )

    # =====================================
    # CALCULATE TIME
    # =====================================

    if ticket.started_at:

        minutes = int(

            (
                now -
                ticket.started_at
            ).total_seconds() / 60
        )

        ticket.resolution_minutes = (
            minutes
        )

        # =================================
        # DELAY CHECK
        # =================================

        ticket.delayed = (
            minutes > 7
        )

    db.commit()

    db.refresh(ticket)

    return {

        "success": True,

        "status":
            ticket.status.value,

        "minutes":
            ticket.resolution_minutes,

        "delayed":
            ticket.delayed,
    }