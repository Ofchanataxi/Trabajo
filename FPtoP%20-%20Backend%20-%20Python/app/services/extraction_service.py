import tempfile, os
from fastapi import UploadFile
from typing import Optional # <--- Añadir Optional
from app.services.extractors import (
    equipos_fondo_extractor,
    protectores_nuevos_extractor,
    protectores_reparados_extractor,
    elementos_adicionales_extractor,
    equipos_superficie_extractor,
    extraer_datos_tally_tenaris,
    extractor_valor_dinamico # <--- 1. Importar el nuevo extractor
)

async def process_pdf_by_type(
    release_type: int, 
    file: UploadFile,
    valor_a_buscar: Optional[str] = None,
    posicion_dato: Optional[str] = None,
    modo_busqueda: Optional[str] = None,
    buscar_en_cabecera: bool = False
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        pdf_path = tmp.name
    try:
        # --- 3. Usar lambdas para manejar diferentes argumentos ---
        extractors = {
            1: lambda path: equipos_fondo_extractor.extraer_datos_equipos_de_fondo(path),
            2: lambda path: protectores_nuevos_extractor.extraer_datos_protectores_nuevos(path),
            3: lambda path: protectores_reparados_extractor.extraer_datos_protectores_reparados(path),
            4: lambda path: elementos_adicionales_extractor.extraer_datos_elementos_adicionales(path),
            5: lambda path: equipos_superficie_extractor.extraer_datos_equipos_de_superficie(path),
            666: lambda path: extraer_datos_tally_tenaris.extraer_datos_tally_tenaris(path),
            333: lambda path: extractor_valor_dinamico.extraer_valor_dinamico(
                                    path, 
                                    valor_a_buscar=valor_a_buscar, 
                                    posicion_dato=posicion_dato,
                                    modo_busqueda=modo_busqueda,
                                    buscar_en_cabecera=buscar_en_cabecera
                                )
        }
        
        extractor = extractors.get(release_type)
        
        if not extractor:
            # Actualizar mensaje de error
            return {"error": "Tipo de release no válido. IDs válidos: 1, 2, 3, 4, 5, 333, 666."}
        
        # 5. Llamar al extractor (que ahora es un lambda)
        return extractor(pdf_path)
    
    finally:
        os.unlink(pdf_path)