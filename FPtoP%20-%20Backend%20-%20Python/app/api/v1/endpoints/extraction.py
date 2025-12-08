# app/api/v1/endpoints/extraction.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.services import extraction_service, tallyMTC_service
from typing import Optional, List

router = APIRouter()

@router.post("/extract-data")
async def extract_data_from_pdf(
    release_type: int = Form(...),
    file: UploadFile = File(..., description="Archivo principal (o Tally si es tipo 7)"),
    mtc_files: List[UploadFile] = File(default=[], description="Archivos MTC (Solo para tipo 7)"),
    valor_a_buscar: Optional[str] = Form(None),
    posicion_dato: Optional[str] = Form(None),
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
    print("release type: ", release_type, flush=True)
    if release_type == 7:
        if not mtc_files:
            raise HTTPException(status_code=400, detail="Para release_type 7 se requieren archivos en 'mtc_files'.")
            
        print("Iniciando proceso de cruce Tally-MTC (Tipo 7)")
        data = await tallyMTC_service.process_tally_mtc_cross_reference(
            tally_file=file,
            mtc_files=mtc_files
        )
    else:
        print(f"Iniciando extracción simple (Tipo {release_type})")
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