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
from app.models.user_model import User, MechanicLocation
from app.models.tipo_falla_model import TipoFalla

from app.routes.jefe_mecanicos_routes import get_lowest_load_mechanic, location_for_linea

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)

# Uploads now go to S3 (Lambda has no persistent local disk).
# upload_fileobj() stores the file in S3 and returns the object key,
# which we save in the database in place of the old local path.
from app.core.s3 import upload_fileobj

# Web Push notifications (best-effort; never breaks the request)
from app.core.push import send_push

import threading

# ==========================================
# PUSH WITH TIMEOUT
# send_push makes blocking HTTP calls to the browsers' push
# services. A stale/dead subscription can hang for 20-30s,
# which pushes the whole request past API Gateway's hard 29s
# limit and the client gets "Endpoint request timed out"
# even though the ticket WAS created. Run the push in a
# worker thread and wait at most a few seconds — creating
# the ticket matters more than the notification.
# ==========================================
def run_push_with_timeout(push_fn, timeout_seconds=5):
    done = threading.Event()

    def _worker():
        try:
            push_fn()
        except Exception as e:
            print(f"Push notification failed: {e}")
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    if not done.wait(timeout_seconds):
        print("Push notification timed out — responding without waiting for it")


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
        # Route to the right pool: muestra-line tickets go to sample-room
        # mechanics, everything else to the floor.
        location = location_for_linea(linea_uuid)
        mechanic = get_lowest_load_mechanic(db, location)

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
            ubicacion=location.value,
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

        # Notify the assigned mechanic on their phone
        # (capped at 5s so a hanging push can't time out the request)
        if mechanic:
            run_push_with_timeout(lambda: send_push(
                db,
                user_id=mechanic.id,
                title="\U0001F527 Nuevo ticket asignado",
                body=f"{titulo} \u00b7 {maquina_nombre} \u00b7 {area}",
                url="/mecanico",
            ))

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
        location = location_for_linea(linea_uuid)
        mechanic = get_lowest_load_mechanic(db, location)

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
            ubicacion=location.value,
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

        # Notify the assigned mechanic on their phone
        # (capped at 5s so a hanging push can't time out the request)
        if mechanic:
            run_push_with_timeout(lambda: send_push(
                db,
                user_id=mechanic.id,
                title="\U0001F504 Nuevo cambio de estilo",
                body=f"{titulo} \u00b7 {estilo_actual} \u2192 {nuevo_estilo}",
                url="/mecanico",
            ))

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
# GET FAILURE TYPES
# NOTE: must be declared BEFORE "/{ticket_id}"
# or FastAPI will match "tipos-falla" as a
# ticket_id and fail on uuid.UUID().
# ==========================================
@router.get("/tipos-falla")
def get_tipos_falla(db: Session = Depends(get_db)):
    try:
        tipos = (
            db.query(TipoFalla)
            .filter(TipoFalla.activo == True)
            .order_by(TipoFalla.nombre.asc())
            .all()
        )
        return {
            "success": True,
            "tipos_falla": [
                {"id": str(t.id), "nombre": t.nombre} for t in tipos
            ],
        }
    except Exception as e:
        print(f"Error getting tipos de falla: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CREATE FAILURE TYPE
# Called from the "Agregar tipo de falla"
# modal in NuevaFallaPage.
# ==========================================
@router.post("/tipos-falla")
def create_tipo_falla(
    nombre: str = Form(...),
    created_by: str = Form(None),
    db: Session = Depends(get_db),
):
    try:
        nombre = nombre.strip()
        if not nombre:
            raise HTTPException(
                status_code=400, detail="El nombre de la falla es requerido"
            )
        if len(nombre) > 100:
            raise HTTPException(
                status_code=400, detail="El nombre no puede exceder 100 caracteres"
            )

        # Case-insensitive duplicate check: if it already exists,
        # return it as a success so the frontend just selects it.
        existing = (
            db.query(TipoFalla)
            .filter(func.lower(TipoFalla.nombre) == nombre.lower())
            .first()
        )
        if existing:
            if not existing.activo:
                existing.activo = True
                db.commit()
                db.refresh(existing)
            return {
                "success": True,
                "tipo_falla": {"id": str(existing.id), "nombre": existing.nombre},
            }

        tipo = TipoFalla(nombre=nombre)
        if created_by:
            try:
                tipo.created_by = uuid.UUID(created_by)
            except (ValueError, TypeError):
                pass  # created_by is optional; ignore malformed ids

        db.add(tipo)
        db.commit()
        db.refresh(tipo)

        return {
            "success": True,
            "tipo_falla": {"id": str(tipo.id), "nombre": tipo.nombre},
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating tipo de falla: {e}")
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

        # Persist closing photos so the S3 keys aren't orphaned.
        # We reuse the TicketValidacion table (same as /validate) —
        # the "close/" prefix in the keys distinguishes them.
        if photo_paths:
            cierre_record = TicketValidacion(
                ticket_id=ticket.id,
                validado_por=uuid.UUID(closed_by),
                comentario=comentario or "Fotos de cierre",
                fotos=photo_paths,
                validated_at=func.now(),
            )
            db.add(cierre_record)

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


# ==========================================
# DELETE TICKET (JEFE DE LÍNEA)
# DELETE /tickets/{ticket_id}?deleted_by=<user_id>
#
# Only tickets that have NOT been completed/validated/
# closed can be deleted (i.e. pendiente, asignado,
# en_proceso). Once a mechanic finished the work we keep
# the record for metrics/audit.
#
# Child rows (asignaciones, historial, comentarios,
# validaciones, falla/cambio details) are removed first
# so foreign-key constraints don't block the delete.
# ==========================================
@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    deleted_by: str,
    db: Session = Depends(get_db),
):
    try:
        try:
            ticket_uuid = uuid.UUID(ticket_id)
            deleted_by_uuid = uuid.UUID(deleted_by)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="ID inválido")

        ticket = db.query(Ticket).filter(Ticket.id == ticket_uuid).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Protect finished work — only unfinished tickets can be deleted
        if ticket.status in [
            TicketStatus.completado,
            TicketStatus.validado,
            TicketStatus.cerrado,
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se puede eliminar un ticket completado, validado o cerrado. "
                    f"Estado actual: {ticket.status.value if hasattr(ticket.status, 'value') else ticket.status}"
                ),
            )

        # Delete child records first (FK constraints)
        db.query(TicketAsignacion).filter(TicketAsignacion.ticket_id == ticket.id).delete(synchronize_session=False)
        db.query(TicketHistorial).filter(TicketHistorial.ticket_id == ticket.id).delete(synchronize_session=False)
        db.query(TicketComentario).filter(TicketComentario.ticket_id == ticket.id).delete(synchronize_session=False)
        db.query(TicketValidacion).filter(TicketValidacion.ticket_id == ticket.id).delete(synchronize_session=False)
        db.query(FallaEquipo).filter(FallaEquipo.ticket_id == ticket.id).delete(synchronize_session=False)
        db.query(CambioEstilo).filter(CambioEstilo.ticket_id == ticket.id).delete(synchronize_session=False)

        ticket_number = ticket.ticket_number
        db.delete(ticket)
        db.commit()

        print(f"Ticket {ticket_number} deleted by user {deleted_by_uuid}")

        return {
            "success": True,
            "message": f"Ticket {ticket_number} eliminado correctamente",
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print(f"Error deleting ticket: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting ticket: {str(e)}")


# ==========================================
# SERVE TICKET PHOTO (presigned S3 URL)
# GET /tickets/{ticket_id}/image
# ==========================================
# The uploads bucket is PRIVATE, so the browser cannot read the object
# directly. This endpoint generates a short-lived presigned URL and
# redirects the browser to it, so the <img> tag can load the photo
# without making the bucket public.
#
# Frontend usage:  <img src={`/api/v1/tickets/${ticket.id}/image`} />
# ==========================================
import boto3
from botocore.config import Config as BotoConfig
from fastapi.responses import RedirectResponse


@router.get("/{ticket_id}/image")
def get_ticket_image(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    # Find the ticket's falla record (that's where image_url lives)
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de ticket inválido")

    falla = (
        db.query(FallaEquipo)
        .filter(FallaEquipo.ticket_id == ticket_uuid)
        .first()
    )

    if not falla or not falla.image_url:
        raise HTTPException(status_code=404, detail="Este ticket no tiene imagen")

    key = falla.image_url  # stored S3 object key, e.g. "abc.jpg"
    bucket = os.environ.get("UPLOADS_BUCKET")
    region = os.environ.get("AWS_REGION", "mx-central-1")

    if not bucket:
        raise HTTPException(status_code=500, detail="UPLOADS_BUCKET no configurado")

    try:
        # IMPORTANT: newer regions like mx-central-1 require the S3 client to be
        # pinned to the correct regional endpoint AND use s3v4 signing + regional
        # addressing. Without the explicit endpoint_url, the presigned URL gets
        # signed against the wrong endpoint and S3 rejects it with
        # IllegalLocationConstraintException.
        s3 = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3.{region}.amazonaws.com",
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                # The stored objects have a bad Content-Type (e.g. "jpg" instead
                # of "image/jpeg"), which makes browsers refuse to render them.
                # Override the response content-type on the way out so the image
                # always displays correctly — fixes existing AND future photos
                # without needing to re-upload anything.
                "ResponseContentType": "image/jpeg",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=3600,  # URL valid for 1 hour
        )
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail="No se pudo generar la URL de la imagen")

    # Redirect the browser straight to the temporary S3 URL
    return RedirectResponse(url)


# ==========================================
# GET VALIDATION / CLOSING PHOTOS (presigned)
# GET /tickets/{ticket_id}/validacion-fotos
# ==========================================
# Returns short-lived presigned URLs for every photo attached during
# validation ("validations/" keys) or closing ("close/" keys) of the
# ticket, so RH can review the evidence without the bucket being public.
#
# Response: { success, fotos: [ { url, tipo, comentario, fecha } ] }
# ==========================================
@router.get("/{ticket_id}/validacion-fotos")
def get_validacion_fotos(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de ticket inválido")

    bucket = os.environ.get("UPLOADS_BUCKET")
    region = os.environ.get("AWS_REGION", "mx-central-1")

    if not bucket:
        raise HTTPException(status_code=500, detail="UPLOADS_BUCKET no configurado")

    registros = (
        db.query(TicketValidacion)
        .filter(TicketValidacion.ticket_id == ticket_uuid)
        .order_by(TicketValidacion.validated_at.asc())
        .all()
    )

    # Same client config as /image: mx-central-1 needs the explicit
    # regional endpoint + s3v4 signing for presigned URLs to work.
    s3 = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )

    fotos = []
    for registro in registros:
        keys = registro.fotos or []
        for key in keys:
            if not key:
                continue
            try:
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": bucket,
                        "Key": key,
                        "ResponseContentType": "image/jpeg",
                        "ResponseContentDisposition": "inline",
                    },
                    ExpiresIn=3600,
                )
            except Exception as e:
                print(f"Error presigning validation photo {key}: {e}")
                continue

            fotos.append({
                "url": url,
                # "close/" keys come from Cerrar Ticket, the rest from Validar
                "tipo": "cierre" if key.startswith("close/") else "validacion",
                "comentario": registro.comentario,
                "fecha": str(registro.validated_at) if registro.validated_at else None,
            })

    return {"success": True, "fotos": fotos}