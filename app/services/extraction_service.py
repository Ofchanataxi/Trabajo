import tempfile
import os
from fastapi import UploadFile
from typing import Optional

# Importamos los extractores
from app.services.extractors import (
    equipos_fondo_extractor,
    protectores_nuevos_extractor,
    protectores_reparados_extractor,
    elementos_adicionales_extractor,
    equipos_superficie_extractor,
    logistica_extractor,
    extractor_valor_dinamico
)

async def process_pdf_by_type(
    release_type: int, 
    file: UploadFile,
    business_line_id: int,
    valor_a_buscar: Optional[str] = None,
    posicion_dato: Optional[str] = None,
    modo_busqueda: Optional[str] = None,
    buscar_en_cabecera: bool = False
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        pdf_path = tmp.name
    
    try:
        extractor_func = None

        # ---------------------------------------------------------
        # MAPA DE EXTRACTORES: LOGÍSTICA (ID 1)
        # ---------------------------------------------------------
        if business_line_id == 1:
            extractors_logistica = {
                3: lambda path: logistica_extractor.extraer_datos_logistica(path)
            }
            extractor_func = extractors_logistica.get(release_type)
        elif business_line_id == 2:
            extractors_als = {
                1: lambda path: equipos_fondo_extractor.extraer_datos_equipos_de_fondo(path),
                2: lambda path: protectores_nuevos_extractor.extraer_datos_protectores_nuevos(path),
                3: lambda path: protectores_reparados_extractor.extraer_datos_protectores_reparados(path),
                4: lambda path: elementos_adicionales_extractor.extraer_datos_elementos_adicionales(path),
                5: lambda path: equipos_superficie_extractor.extraer_datos_equipos_de_superficie(path),
                
                # Herramientas extra (Legacy)
                333: lambda path: extractor_valor_dinamico.extraer_valor_dinamico(
                                        path, 
                                        valor_a_buscar=valor_a_buscar, 
                                        posicion_dato=posicion_dato,
                                        modo_busqueda=modo_busqueda,
                                        buscar_en_cabecera=buscar_en_cabecera
                                    )
            }
            extractor_func = extractors_als.get(release_type)

        if not extractor_func:
            print(f"⚠️ Warning: No hay extractor definido para Negocio {business_line_id} - Tipo {release_type}", flush=True)
            return []
        
        return extractor_func(pdf_path)
    
    except Exception as e:
        print(f"Error en process_pdf_by_type: {e}", flush=True)
        raise e
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)