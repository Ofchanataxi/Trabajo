# app/api/v1/endpoints/extraction.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.services import extraction_service, orchestration_service
from typing import Optional

router = APIRouter()

@router.post("/extract-data")
async def extract_data_from_pdf(
    release_type: int = Form(...),
    file: UploadFile = File(...),
    valor_a_buscar: Optional[str] = Form(None),
    posicion_dato: Optional[str] = Form(None), # Ej: "right", "left", "above", "below"
    modo_busqueda: Optional[str] = Form("lattice"),
    buscar_en_cabecera: bool = Form(False)
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
        modo_busqueda=modo_busqueda,
        buscar_en_cabecera=buscar_en_cabecera
    )
    print("Finaliza proceso de extraccion de informacion")
    if data is None:
        raise HTTPException(status_code=404, detail="No se pudo extraer información de la tabla de Trazabilidad o el tipo de release no tiene una función definida.")

    return JSONResponse(content={"extracted_data": data})

@router.post("/tally-mtc-cross-reference")
async def cross_reference_tally_mtc(
    tally_file: UploadFile = File(..., description="El archivo PDF del Tally de Tenaris"),
    mtc_file: UploadFile = File(..., description="El archivo PDF del MTC")
):
    """
    Endpoint para cruzar información del Tally Tenaris contra un MTC.
    Extrae 'Heat N°' del Tally, busca el 'Steel Grade' en el MTC y los combina.
    """
    try:
        # Llama al nuevo servicio de orquestación
        data = await orchestration_service.process_tally_mtc_cross_reference(
            tally_file=tally_file,
            mtc_file=mtc_file
        )
        
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        
        return data
        
    except Exception as e:
        # Manejo de errores
        print(f"Error en endpoint /tally-mtc-cross-reference: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")