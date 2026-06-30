import datetime
import os
import uuid
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import get_db

# Models
from app.models.linea_model import Linea
from app.models.cambio_estilo_model import CambioEstilo
from app.models.ticket_model import Ticket, TicketType, TicketStatus
from app.models.falla_equipo_model import FallaEquipo
from app.models.ticket_asignacion_model import TicketAsignacion, AsignacionStatus
from app.models.ticket_historial_model import TicketHistorial
from app.models.ticket_comentario_model import TicketComentario
from app.models.ticket_validation_model import TicketValidacion
from app.models.user_model import User

from app.routes.jefe_mecanicos_routes import get_lowest_load_mechanic

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)

# Uploads now go to S3 (Lambda has no persistent local disk).
# upload_fileobj() stores the file in S3 and returns the object key,
# which we save in the database in place of the old local path.
from app.core.s3 import upload_fileobj


# ==========================================
# GENERATE TICKET NUMBER
# ==========================================
def generate_ticket_number():
    return f"TK-{uuid.uuid4().hex[:8].upper()}"


# ==========================================
# CREATE EQUIPMENT FAILURE
# ==========================================
@router.post("/falla-equipo")
async def create_falla_equipo_ticket(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    created_by: str = Form(...),
    linea_id: str = Form(...),
    maquina_nombre: str = Form(...),
    maquina_codigo: str = Form(...),
    prioridad: str = Form(...),
    area: str = Form(...),
    observaciones: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    try:
        linea_uuid = uuid.UUID(linea_id)
        created_by_uuid = uuid.UUID(created_by)

        ticket_number = generate_ticket_number()

        # Save image to S3 (returns the object key, stored as image_url)
        image_path = None
        if image and image.filename:
            image_path = upload_fileobj(
                await image.read(),
                image.filename,
            )

        # Auto assign mechanic
        mechanic = get_lowest_load_mechanic(db)

        # Create ticket
        ticket = Ticket(
            ticket_number=ticket_number,
            tipo=TicketType.falla_equipo,
            titulo=titulo,
            descripcion=descripcion,
            created_by=created_by_uuid,
            linea_id=linea_uuid,
            assigned_to=mechanic.id if mechanic else None,
            status=TicketStatus.asignado if mechanic else TicketStatus.pendiente,
            prioridad_general=prioridad,
            ubicacion="piso",
        )
        db.add(ticket)
        db.flush()

        # Create falla equipo record
        falla = FallaEquipo(
            ticket_id=ticket.id,
            maquina_nombre=maquina_nombre,
            maquina_codigo=maquina_codigo,
            area=area,
            observaciones=observaciones,
            image_url=image_path,
        )
        db.add(falla)

        # Assignment history
        if mechanic:
            asignacion = TicketAsignacion(
                ticket_id=ticket.id,
                mecanico_id=mechanic.id,
                asignado_por=created_by_uuid,
                status=AsignacionStatus.asignado,
                notas=f"Auto-assigned to {mechanic.nombre}",
            )
            db.add(asignacion)

            historial = TicketHistorial(
                ticket_id=ticket.id,
                usuario_id=created_by_uuid,
                accion="ticket_auto_asignado",
                descripcion=f"Automatically assigned to {mechanic.nombre}",
            )
            db.add(historial)

        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "message": "Equipment failure ticket created successfully",
            "assigned_mechanic": mechanic.nombre if mechanic else None,
            "ticket": {
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            }
        }

    except Exception as e:
        db.rollback()
        print(f"Error creating falla equipo ticket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CREATE STYLE CHANGE
# ==========================================
@router.post("/cambio-estilo")
async def create_cambio_estilo_ticket(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    created_by: str = Form(...),
    linea_id: str = Form(...),
    estilo_actual: str = Form(...),
    nuevo_estilo: str = Form(...),
    prioridad: str = Form(...),
    observaciones: str = Form(None),
    db: Session = Depends(get_db),
):
    try:
        linea_uuid = uuid.UUID(linea_id)
        created_by_uuid = uuid.UUID(created_by)

        ticket_number = generate_ticket_number()
        mechanic = get_lowest_load_mechanic(db)

        ticket = Ticket(
            ticket_number=ticket_number,
            tipo=TicketType.cambio_estilo,
            titulo=titulo,
            descripcion=descripcion,
            created_by=created_by_uuid,
            linea_id=linea_uuid,
            assigned_to=mechanic.id if mechanic else None,
            status=TicketStatus.asignado if mechanic else TicketStatus.pendiente,
            prioridad_general=prioridad,
            ubicacion="piso",
        )
        db.add(ticket)
        db.flush()

        cambio = CambioEstilo(
            ticket_id=ticket.id,
            estilo_actual=estilo_actual,
            nuevo_estilo=nuevo_estilo,
            observaciones=observaciones,
        )
        db.add(cambio)

        if mechanic:
            asignacion = TicketAsignacion(
                ticket_id=ticket.id,
                mecanico_id=mechanic.id,
                asignado_por=created_by_uuid,
                status=AsignacionStatus.asignado,
                notas=f"Auto-assigned to {mechanic.nombre}",
            )
            db.add(asignacion)

            historial = TicketHistorial(
                ticket_id=ticket.id,
                usuario_id=created_by_uuid,
                accion="ticket_auto_asignado",
                descripcion=f"Ticket auto-assigned to {mechanic.nombre} for style change",
            )
            db.add(historial)

        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "message": "Style change ticket created successfully",
            "assigned_mechanic": mechanic.nombre if mechanic else None,
            "ticket": {
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            }
        }

    except Exception as e:
        db.rollback()
        print(f"Error creating style change ticket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SHARED SERIALIZER — ticket + mechanic name + type details
# ==========================================
def _serialize_ticket_with_mechanic(ticket: Ticket, db: Session) -> dict:
    data = {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "titulo": ticket.titulo,
        "descripcion": ticket.descripcion,
        "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "created_at": ticket.created_at,
        "completed_at": str(ticket.completed_at) if ticket.completed_at else None,
        "closed_at": str(getattr(ticket, "closed_at", None)) if getattr(ticket, "closed_at", None) else None,
        "prioridad_general": ticket.prioridad_general,
        "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
        "assigned_mechanic": None,
        "ubicacion": (
            ticket.ubicacion.value if hasattr(ticket.ubicacion, "value")
            else str(ticket.ubicacion) if ticket.ubicacion else None
        ),
        "resolution_minutes": getattr(ticket, "resolution_minutes", None),
        "delayed": getattr(ticket, "delayed", False),
    }

    if ticket.assigned_to:
        mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
        if mechanic:
            data["assigned_mechanic"] = mechanic.nombre

    if ticket.tipo == TicketType.falla_equipo:
        falla = db.query(FallaEquipo).filter(FallaEquipo.ticket_id == ticket.id).first()
        if falla:
            data["details"] = {
                "maquina_nombre": falla.maquina_nombre,
                "maquina_codigo": falla.maquina_codigo,
                "area": falla.area,
                "observaciones": falla.observaciones,
            }
    elif ticket.tipo == TicketType.cambio_estilo:
        cambio = db.query(CambioEstilo).filter(CambioEstilo.ticket_id == ticket.id).first()
        if cambio:
            data["details"] = {
                "estilo_actual": cambio.estilo_actual,
                "nuevo_estilo": cambio.nuevo_estilo,
                "observaciones": cambio.observaciones,
            }

    return data


# ==========================================
# GET ACTIVE TICKETS (with mechanic name)
# pendiente | asignado | en_proceso
# ==========================================
@router.get("/activos")
def get_active_tickets(db: Session = Depends(get_db)):
    try:
        tickets = (
            db.query(Ticket)
            .filter(Ticket.status.in_([
                TicketStatus.pendiente,
                TicketStatus.asignado,
                TicketStatus.en_proceso,
            ]))
            .order_by(Ticket.created_at.desc())
            .all()
        )
        response = [_serialize_ticket_with_mechanic(t, db) for t in tickets]
        return {"success": True, "tickets": response}
    except Exception as e:
        print(f"Error getting active tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET CLOSED TICKETS (with mechanic name)
# ==========================================
@router.get("/cerrados")
def get_closed_tickets(db: Session = Depends(get_db)):
    try:
        tickets = (
            db.query(Ticket)
            .filter(Ticket.status == TicketStatus.cerrado)
            .order_by(Ticket.closed_at.desc())
            .all()
        )
        response = [_serialize_ticket_with_mechanic(t, db) for t in tickets]
        return {"success": True, "tickets": response}
    except Exception as e:
        print(f"Error getting closed tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET TICKETS BY LINEA ID
# ==========================================
@router.get("/linea/{linea_id}")
def get_tickets_by_linea(
    linea_id: str,
    db: Session = Depends(get_db),
):
    try:
        linea_uuid = uuid.UUID(linea_id)
        tickets = db.query(Ticket).filter(Ticket.linea_id == linea_uuid).order_by(Ticket.created_at.desc()).all()

        response = []
        for ticket in tickets:
            ticket_data = {
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "titulo": ticket.titulo,
                "descripcion": ticket.descripcion,
                "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
                "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                "created_at": ticket.created_at,
                "prioridad_general": ticket.prioridad_general,
                "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
                "ubicacion": ticket.ubicacion.value if hasattr(ticket.ubicacion, "value") else str(ticket.ubicacion) if ticket.ubicacion else None,
                "resolution_minutes": getattr(ticket, 'resolution_minutes', None),
            }

            if ticket.assigned_to:
                mechanic = db.query(User).filter(User.id == ticket.assigned_to).first()
                if mechanic:
                    ticket_data["assigned_mechanic"] = mechanic.nombre

            if ticket.tipo == TicketType.falla_equipo:
                falla = db.query(FallaEquipo).filter(FallaEquipo.ticket_id == ticket.id).first()
                if falla:
                    ticket_data["details"] = {
                        "maquina_nombre": falla.maquina_nombre,
                        "maquina_codigo": falla.maquina_codigo,
                        "area": falla.area,
                        "prioridad": ticket.prioridad_general,
                        "image_url": falla.image_url,
                        "observaciones": falla.observaciones,
                    }

            elif ticket.tipo == TicketType.cambio_estilo:
                cambio = db.query(CambioEstilo).filter(CambioEstilo.ticket_id == ticket.id).first()
                if cambio:
                    ticket_data["details"] = {
                        "estilo_actual": cambio.estilo_actual,
                        "nuevo_estilo": cambio.nuevo_estilo,
                        "observaciones": cambio.observaciones,
                    }

            response.append(ticket_data)

        return {"success": True, "tickets": response}

    except Exception as e:
        print(f"Error getting tickets by linea: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GET SINGLE TICKET
# ==========================================
@router.get("/{ticket_id}")
def get_single_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(Ticket.id == uuid.UUID(ticket_id)).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        line_number = None
        line_name = None
        if ticket.linea_id:
            linea = db.query(Linea).filter(Linea.id == ticket.linea_id).first()
            if linea:
                line_number = linea.numero
                line_name = linea.nombre

        response = {
            "id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "titulo": ticket.titulo,
            "descripcion": ticket.descripcion,
            "tipo": ticket.tipo.value if hasattr(ticket.tipo, "value") else str(ticket.tipo),
            "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            "ubicacion": ticket.ubicacion.value if hasattr(ticket.ubicacion, "value") else str(ticket.ubicacion),
            "prioridad_general": ticket.prioridad_general,
            "linea_id": str(ticket.linea_id) if ticket.linea_id else None,
            "linea_numero": line_number,
            "linea_nombre": line_name,
            "started_at": str(ticket.started_at) if ticket.started_at else None,
            "completed_at": str(ticket.completed_at) if ticket.completed_at else None,
            "resolution_minutes": getattr(ticket, 'resolution_minutes', None),
            "delayed": getattr(ticket, 'delayed', False),
            "solution_description": getattr(ticket, 'solution_description', None),
        }

        if ticket.tipo == TicketType.falla_equipo:
            falla = db.query(FallaEquipo).filter(FallaEquipo.ticket_id == ticket.id).first()
            if falla:
                response.update({
                    "area": falla.area,
                    "maquina_nombre": falla.maquina_nombre,
                    "maquina_codigo": falla.maquina_codigo,
                    "image_url": falla.image_url,
                    "observaciones": falla.observaciones,
                })

        elif ticket.tipo == TicketType.cambio_estilo:
            cambio = db.query(CambioEstilo).filter(CambioEstilo.ticket_id == ticket.id).first()
            if cambio:
                response.update({
                    "estilo_actual": cambio.estilo_actual,
                    "nuevo_estilo": cambio.nuevo_estilo,
                    "observaciones": cambio.observaciones,
                })

        return {"success": True, "ticket": response}

    except Exception as e:
        print(f"Error in get_single_ticket: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching ticket: {str(e)}")


# ==========================================
# COMPLETE TICKET (MECHANIC COMPLETES WORK)
# ==========================================
@router.post("/ticket/complete/{ticket_id}")
def complete_ticket(
    ticket_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(Ticket.id == uuid.UUID(ticket_id)).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if ticket.status == TicketStatus.completado:
            raise HTTPException(status_code=403, detail="Ticket already completed")

        now = datetime.datetime.utcnow()
        ticket.status = TicketStatus.completado
        ticket.completed_at = now
        ticket.solution_description = payload.get("solution_description")

        if ticket.started_at:
            minutes = int((now - ticket.started_at).total_seconds() / 60)
            ticket.resolution_minutes = minutes
            ticket.delayed = minutes > 7

        db.commit()
        db.refresh(ticket)

        return {
            "success": True,
            "status": ticket.status.value,
            "minutes": ticket.resolution_minutes,
            "delayed": ticket.delayed,
        }

    except Exception as e:
        print(f"Error completing ticket: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# VALIDATE TICKET (JEFE DE LÍNEA)
# ==========================================
@router.post("/{ticket_id}/validate")
async def validate_ticket(
    ticket_id: str,
    validado_por: str = Form(...),
    comentario: str = Form(None),
    photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
         
        ticket = db.query(Ticket).filter(Ticket.id == uuid.UUID(ticket_id)).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if ticket.status != TicketStatus.completado:
            raise HTTPException(
                status_code=400,
                detail=f"Ticket must be in 'completado' status to validate. Current status: {ticket.status}"
            )

        # Save validation photos to S3 (store object keys)
        photo_paths = []
        if photos:
            for photo in photos:
                if photo and photo.filename:
                    key = upload_fileobj(
                        await photo.read(),
                        photo.filename,
                        prefix="validations/",
                    )
                    photo_paths.append(key)

        ticket.status = TicketStatus.validado

        validacion = TicketValidacion(
            ticket_id=ticket.id,
            validado_por=uuid.UUID(validado_por),
            comentario=comentario,
            fotos=photo_paths if photo_paths else None,
            validated_at=func.now()
        )
        db.add(validacion)

        historial = TicketHistorial(
            ticket_id=ticket.id,
            usuario_id=uuid.UUID(validado_por),
            accion="ticket_validado",
            descripcion=f"Ticket validated: {comentario if comentario else 'No comments'}"
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": "Ticket validated successfully",
            "status": ticket.status.value,
            "photos_saved": len(photo_paths)
        }

    except Exception as e:
        print(f"Error validating ticket: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error validating ticket: {str(e)}")


# ==========================================
# CLOSE TICKET (JEFE DE LÍNEA)
# ==========================================
@router.post("/{ticket_id}/close")
async def close_ticket(
    ticket_id: str,
    closed_by: str = Form(...),
    comentario: str = Form(None),
    photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
        ticket = db.query(Ticket).filter(Ticket.id == uuid.UUID(ticket_id)).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if ticket.status not in [TicketStatus.completado, TicketStatus.validado]:
            raise HTTPException(
                status_code=400,
                detail=f"Ticket must be in 'completado' or 'validado' status to close. Current status: {ticket.status}"
            )

        # Save closing photos to S3 if any (store object keys)
        photo_paths = []
        if photos:
            for photo in photos:
                if photo and photo.filename:
                    key = upload_fileobj(
                        await photo.read(),
                        photo.filename,
                        prefix="close/",
                    )
                    photo_paths.append(key)

        ticket.status = TicketStatus.cerrado
        ticket.closed_at = func.now()
        ticket.closed_by = uuid.UUID(closed_by)

        if photo_paths:
            # Store closing photos in validation record or separate table
            pass

        historial = TicketHistorial(
            ticket_id=ticket.id,
            usuario_id=uuid.UUID(closed_by),
            accion="ticket_cerrado",
            descripcion=f"Ticket closed: {comentario if comentario else 'No comments'}"
        )
        db.add(historial)

        db.commit()

        return {
            "success": True,
            "message": "Ticket closed successfully",
            "status": ticket.status.value
        }

    except Exception as e:
        print(f"Error closing ticket: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error closing ticket: {str(e)}")