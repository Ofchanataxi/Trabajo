import re
from pypdf import PdfReader
from typing import List, Dict, Tuple
import os
from app.services.extractors.extractor_valor_dinamico import extraer_valor_dinamico
from app.services.extract_data_from_pdf import normalize_rotation

def _extraer_valor_de_pagina(
    path_mtc_pdf_original: str, 
    page_num: int, valor_a_buscar: str
) -> str:
    try:
        resultado = extraer_valor_dinamico(
            pdf_path=path_mtc_pdf_original, valor_a_buscar=valor_a_buscar, posicion_dato="inline",
            modo_busqueda="inline", buscar_en_cabecera=False, pages=str(page_num)
        )
        
        if resultado and isinstance(resultado, dict):
            valor = resultado.get("valor_encontrado")
            if valor:
                return str(valor).strip()

        return "No encontrado"

    except Exception as e:
        print(f"Error en extractor_valor_dinamico para página {page_num}: {e}")
        return f"Error: {str(e)}"


def extraer_steel_grade_de_mtc(path_mtc_pdf: str, coladas_a_buscar: List[str]) -> Dict[str, str]:

    print(f"Buscando {len(coladas_a_buscar)} coladas en {path_mtc_pdf}")
    
    path_mtc_normalizado = normalize_rotation(path_mtc_pdf)
    
    resultados: Dict[str, str] = {}
    coladas_pendientes = set(coladas_a_buscar) 
    
    mapa_pagina_coladas: Dict[int, List[str]] = {}

    try:
        reader = PdfReader(path_mtc_normalizado)
        
        for i, page in enumerate(reader.pages):
            if not coladas_pendientes:
                break
            
            texto_pagina = page.extract_text()
            if not texto_pagina:
                continue
            
            # Buscar qué coladas están en esta página
            encontradas_aqui = []
            for colada in list(coladas_pendientes):
                if colada in texto_pagina:
                    encontradas_aqui.append(colada)
                    coladas_pendientes.remove(colada)
            
            if encontradas_aqui:
                page_num_actual = i + 1 # 1-based para Tabula (Tabula usa paginación desde 1)
                mapa_pagina_coladas[page_num_actual] = encontradas_aqui
                print(f"Página {page_num_actual}: Encontradas coladas {encontradas_aqui}")

    except Exception as e:
        print(f"Error crítico leyendo texto MTC PDF: {e}")
        for colada in coladas_pendientes:
            resultados[colada] = "Error lectura PDF base"
        return resultados

    for page_num, coladas in mapa_pagina_coladas.items():
        print(f"Extrayendo Steel Grade de página {page_num}...")
        
        steel_grade = _extraer_valor_de_pagina(
            path_mtc_pdf_original=str(path_mtc_normalizado),
            page_num=page_num, valor_a_buscar="Steel Grade" 
        )
        
        print(f" -> Steel Grade obtenido: {steel_grade}")

        for colada in coladas:
            resultados[colada] = steel_grade

    if str(path_mtc_normalizado) != str(path_mtc_pdf):
        try:
            os.unlink(path_mtc_normalizado)
        except:
            pass

    for colada in coladas_pendientes:
        resultados[colada] = "Colada no encontrada en MTC"
    
    return resultados