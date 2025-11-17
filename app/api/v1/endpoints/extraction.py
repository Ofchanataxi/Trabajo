# app/api/v1/endpoints/extraction.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.services import extraction_service
from typing import Optional

router = APIRouter()

@router.post("/extract-data")
async def extract_data_from_pdf(
    release_type: int = Form(...),
    file: UploadFile = File(...),
    # --- INICIO DE CAMPOS NUEVOS (opcionales) ---
    valor_a_buscar: Optional[str] = Form(None),
    posicion_dato: Optional[str] = Form(None), # Ej: "right", "left", "above", "below"
    modo_busqueda: Optional[str] = Form(None)
    # --- FIN DE CAMPOS NUEVOS ---
):
    print(release_type)
    print(file)
    """
    Recibe un file PDF y un tipo de release (ID), y devuelve los datos extraídos.
    - **release_type**: 1=equipos de fondo, 2=protectores nuevos, 3=protectores reparados, 4=elementos adicionales.
    - **file**: El file PDF a procesar.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El file debe ser un PDF.")

    print("Inicia proceso de extraccion de informacion")
    data = await extraction_service.process_pdf_by_type(
        release_type=release_type,
        file=file,
        valor_a_buscar=valor_a_buscar,
        posicion_dato=posicion_dato,
        modo_busqueda=modo_busqueda
    )
    print("Finaliza proceso de extraccion de informacion")
    if data is None:
        raise HTTPException(status_code=404, detail="No se pudo extraer información de la tabla de Trazabilidad o el tipo de release no tiene una función definida.")

    return JSONResponse(content={"extracted_data": data})