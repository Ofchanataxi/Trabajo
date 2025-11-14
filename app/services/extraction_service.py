import tempfile, os
from fastapi import UploadFile
from app.services.extractors import (
    equipos_fondo_extractor,
    protectores_nuevos_extractor,
    protectores_reparados_extractor,
    elementos_adicionales_extractor,
    equipos_superficie_extractor,
    extraer_datos_tally_tenaris,
)

async def process_pdf_by_type(release_type: int, file: UploadFile):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        pdf_path = tmp.name
    try:
        extractors = {
            1: equipos_fondo_extractor.extraer_datos_equipos_de_fondo,
            2: protectores_nuevos_extractor.extraer_datos_protectores_nuevos,
            3: protectores_reparados_extractor.extraer_datos_protectores_reparados,
            4: elementos_adicionales_extractor.extraer_datos_elementos_adicionales,
            5: equipos_superficie_extractor.extraer_datos_equipos_de_superficie,
            666: extraer_datos_tally_tenaris.extraer_datos_tally_tenaris
        }
        extractor = extractors.get(release_type)
        if not extractor:
            return {"error": "Tipo de release no válido. Use un ID del 1 al 5."}
        return extractor(pdf_path)
    finally:
        os.unlink(pdf_path)