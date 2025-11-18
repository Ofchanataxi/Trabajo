import re
from pypdf import PdfReader
from typing import List, Dict
import tempfile
import os

# --- MODIFICACIÓN 1 ---
# ¡Importamos tu extractor dinámico!
from app.services.extractors.extractor_valor_dinamico import extraer_valor_dinamico
# También importamos la función de normalización que usa tu extractor
from app.services.extract_data_from_pdf import normalize_rotation


def _extraer_valor_de_pagina(
    path_mtc_pdf_original: str, 
    page_num: int, 
    valor_a_buscar: str
) -> str:
    """
    Función auxiliar que llama a tu extractor dinámico en una sola página
    del PDF MTC.
    """
    try:
        # Tu extractor dinámico espera un path, así que le damos el path.
        # Pero le diremos que *solo* procese la página 'page_num'.
        # El lattice=True y "inline" que mencionaste se configuran aquí.
        
        valor_encontrado = extraer_valor_dinamico(
            path=path_mtc_pdf_original,
            valor_a_buscar=valor_a_buscar,
            posicion_dato="inline",        # <--- Parámetro que mencionaste
            modo_busqueda="inline",    # <--- Asumo "inline" para ambos
            buscar_en_cabecera=False,      # <--- Asumo que no está en cabecera
            pages=str(page_num)            # <--- ¡La clave! Le pasamos la página.
        )
        
        if valor_encontrado:
            # Tu extractor puede devolver una lista o un solo valor.
            # Asegurémonos de que sea una cadena.
            if isinstance(valor_encontrado, list):
                return str(valor_encontrado[0])
            return str(valor_encontrado)
        
        return "No encontrado (dinámico)"

    except Exception as e:
        print(f"Error en extractor_valor_dinamico para página {page_num}: {e}")
        return "Error (dinámico)"


def extraer_steel_grade_de_mtc(path_mtc_pdf: str, coladas_a_buscar: List[str]) -> Dict[str, str]:
    """
    Busca coladas en un MTC PDF usando pypdf para encontrar la PÁGINA,
    y luego usa 'extractor_valor_dinamico' para encontrar el 'Steel Grade'
    EN ESA PÁGINA.
    """
    print(f"Buscando {len(coladas_a_buscar)} coladas en {path_mtc_pdf}")
    
    # Normalizamos el PDF una sola vez, ya que tu extractor también lo hace.
    # Esto evita problemas si pypdf y tabula leen un PDF rotado de forma diferente.
    path_mtc_normalizado = normalize_rotation(path_mtc_pdf)
    
    resultados: Dict[str, str] = {}
    coladas_pendientes = set(coladas_a_buscar) 
    
    try:
        reader = PdfReader(path_mtc_normalizado)
        
        for i, page in enumerate(reader.pages):
            if not coladas_pendientes:
                break
            
            texto_pagina = page.extract_text()
            if not texto_pagina:
                continue
            
            page_num_actual = i + 1 # pypdf es 0-indexado, tabula es 1-indexado
            coladas_encontradas_en_esta_pagina = []
            
            for colada in list(coladas_pendientes): 
                if colada in texto_pagina:
                    coladas_encontradas_en_esta_pagina.append(colada)
                    coladas_pendientes.remove(colada)
            
            if coladas_encontradas_en_esta_pagina:
                print(f"Coladas {coladas_encontradas_en_esta_pagina} encontradas en página {page_num_actual}")
                
                # --- REEMPLAZO DE LÓGICA ---
                # ¡Adiós regex! Hola extractor_valor_dinamico.
                # NOTA: Ajusta "Steel Grade" si la etiqueta en el MTC es otra
                # (ej: "Material", "Grado de Acero")
                steel_grade = _extraer_valor_de_pagina(
                    path_mtc_normalizado,
                    page_num_actual,
                    "Steel Grade" # <--- ¡Ajusta esta etiqueta si es necesario!
                )
                
                print(f"Steel Grade encontrado en página {page_num_actual}: {steel_grade}")

                for colada in coladas_encontradas_en_esta_pagina:
                    resultados[colada] = steel_grade

    except Exception as e:
        print(f"Error crítico leyendo MTC PDF con pypdf: {e}")
        for colada in coladas_pendientes:
            resultados[colada] = "Error de lectura PDF"
        return resultados
    
    finally:
        # Borramos el archivo normalizado temporal si lo creamos
        if path_mtc_normalizado != path_mtc_pdf:
            os.unlink(path_mtc_normalizado)

    for colada in coladas_pendientes:
        resultados[colada] = "Colada no encontrada en MTC"
    
    return resultados