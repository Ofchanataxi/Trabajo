from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, List
from app.services import extraction_service, tallyMTC_service

router = APIRouter()

@router.post("/extract-data")
async def extract_data_from_pdf(
    release_type: int = Form(..., description="Tipo de liberación (Logística: 2=Cruce, 3=Tally | ALS: 1-5)"),
    business_line_id: int = Form(..., description="ID de la línea de negocio (1=Logística, 2=ALS)"),
    file: UploadFile = File(..., description="Archivo principal PDF"),
    mtc_files: List[UploadFile] = File(default=[], description="Archivos MTC (Requerido para Logística Tipo 2)"),
    itp_files: List[UploadFile] = File(default=[], description="Archivos ITP (Opcional para Logística Tipo 2)"),
    valor_a_buscar: Optional[str] = Form(None),
    posicion_dato: Optional[str] = Form(None),
    modo_busqueda: Optional[str] = Form("lattice"),
    buscar_en_cabecera: bool = Form(False)
):
    """
    Endpoint inteligente que rutea la extracción según la Línea de Negocio.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")

    print(f"--> [Iniciando] Negocio: {business_line_id} | Tipo: {release_type} | File: {file.filename}", flush=True)

    try:
        data = None

        # ==============================================================================
        # LÓGICA PARA LOGÍSTICA (ID 1)
        # ==============================================================================
        if business_line_id == 1:
            
            if release_type == 2:
                if not mtc_files:
                    raise HTTPException(status_code=400, detail="Logística Tipo 2 requiere archivos MTC.")
                
                print(f"    [Logística] Iniciando Cruce Tally-MTC (Tipo 2)...", flush=True)
                data = await tallyMTC_service.process_tally_mtc_cross_reference(
                    tally_file=file,
                    mtc_files=mtc_files,
                    itp_files=itp_files
                )

            elif release_type == 3:
                print("    [Logística] Iniciando Extracción Tally Simple (Tipo 3)...", flush=True)
                data = await extraction_service.process_pdf_by_type(
                    release_type=release_type, 
                    file=file, 
                    business_line_id=1 
                )

            else:
                raise HTTPException(status_code=400, detail=f"Tipo {release_type} no válido para Logística (Use 2 o 3).")

        # ==============================================================================
        # LÓGICA PARA ALS (ID 2)
        # ==============================================================================
        elif business_line_id == 2:
            
            # IDs 1 al 5: Estándar ALS
            if release_type in [1, 2, 3, 4, 5]:
                print(f"    [ALS] Iniciando extracción estándar (Tipo {release_type})...", flush=True)
                data = await extraction_service.process_pdf_by_type(
                    release_type=release_type, 
                    file=file,
                    business_line_id=2, # Importante especificar que es ALS
                    valor_a_buscar=valor_a_buscar, 
                    posicion_dato=posicion_dato, 
                    modo_busqueda=modo_busqueda, 
                    buscar_en_cabecera=buscar_en_cabecera
                )
            else:
                raise HTTPException(status_code=400, detail=f"Tipo {release_type} no válido para ALS (Use 1-5).")

        else:
            raise HTTPException(status_code=400, detail="ID de línea de negocio desconocido.")

        print(f"<-- [Finalizado] Registros extraídos: {len(data) if data else 0}", flush=True)
        return JSONResponse(content={"extracted_data": data if data else []})

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error Crítico: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))