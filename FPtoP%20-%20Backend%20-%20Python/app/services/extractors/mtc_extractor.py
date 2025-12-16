import re
import os
from pypdf import PdfReader
from typing import List, Dict, Optional
from app.services.extractors.extractor_valor_dinamico import extraer_valor_dinamico
from app.services.extract_data_from_pdf import normalize_rotation

def _buscar_con_regex(texto: str) -> Optional[str]:
    """Busca el Steel Grade."""
    if not texto: return None
    regexs = [
        r"Steel Grade\s*[:\.]?\s*([A-Za-z0-9-]+)",
        r"Grade\s*[:\.]?\s*([A-Za-z0-9-]+)",
        r"Material\s*[:\.]?\s*([A-Za-z0-9-]+)"
    ]
    for r in regexs:
        match = re.search(r, texto, re.IGNORECASE)
        if match: return match.group(1).strip()
    return None

def _buscar_tipo_producto_regex(texto: str) -> str:
    """
    Busca si el documento menciona explícitamente Tubing o Casing
    en contextos de 'Product', 'Type' o 'Description'.
    """
    if not texto: return ""
    
    # Buscamos palabras clave asociadas a la definición del producto
    # Priorizamos encontrar la palabra exacta Tubing o Casing
    
    # 1. Búsqueda directa simple (lo más efectivo en MTCs)
    texto_upper = texto.upper()
    if "TUBING" in texto_upper and "CASING" not in texto_upper:
        return "Tubing"
    if "CASING" in texto_upper and "TUBING" not in texto_upper:
        return "Casing"
        
    # 2. Si ambos aparecen o ninguno, intentamos ser más específicos con Regex
    regexs = [
        r"Product\s*[:\.]?\s*([A-Za-z\s]+)",
        r"Commodity\s*[:\.]?\s*([A-Za-z\s]+)",
        r"Type\s*[:\.]?\s*([A-Za-z\s]+)"
    ]
    
    for r in regexs:
        match = re.search(r, texto, re.IGNORECASE)
        if match:
            valor = match.group(1).upper()
            if "TUBING" in valor: return "Tubing"
            if "CASING" in valor: return "Casing"
            
    return ""

def _extraer_valor_de_pagina(
    path_mtc_pdf_original: str, 
    page_num: int, 
    valor_a_buscar: str,
    texto_pagina_cache: str = None
) -> str:
    # --- OPTIMIZACIÓN: INTENTO RÁPIDO ---
    if texto_pagina_cache:
        # print(f"   ↳ Buscando '{valor_a_buscar}' con Regex...")
        valor_rapido = _buscar_con_regex(texto_pagina_cache)
        if valor_rapido:
            return valor_rapido

    # Fallback a Tabula (lento) si no se encuentra con regex
    try:
        resultado = extraer_valor_dinamico(
            pdf_path=path_mtc_pdf_original,
            valor_a_buscar=valor_a_buscar,
            posicion_dato="inline",
            modo_busqueda="inline",   
            buscar_en_cabecera=False,      
            pages=str(page_num)
        )
        if resultado and isinstance(resultado, dict):
            valor = resultado.get("valor_encontrado")
            if valor:
                return str(valor).strip()
        return "No encontrado"
    except Exception:
        return "Error extracción"

def extraer_steel_grade_de_mtc(files_info: List[tuple], coladas_a_buscar: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Devuelve: { "HEAT1": { "grade": "L80", "file": "mtc.pdf", "product_type": "Tubing" } }
    """
    resultados: Dict[str, Dict[str, str]] = {}
    coladas_pendientes = set(coladas_a_buscar)
    
    for path_mtc, original_filename in files_info:
        if not coladas_pendientes:
            break

        path_mtc_normalizado = normalize_rotation(path_mtc)
        mapa_pagina_info: Dict[int, Dict] = {}

        try:
            reader = PdfReader(path_mtc_normalizado)
            for i, page in enumerate(reader.pages):
                if not coladas_pendientes:
                    break
                
                texto_pagina = page.extract_text() or ""
                
                encontradas_aqui = []
                for colada in list(coladas_pendientes):
                    if colada in texto_pagina:
                        encontradas_aqui.append(colada)
                        coladas_pendientes.remove(colada)
                
                if encontradas_aqui:
                    mapa_pagina_info[i + 1] = {
                        "coladas": encontradas_aqui,
                        "texto": texto_pagina
                    }

        except Exception as e:
            print(f"Error leyendo texto de {original_filename}: {e}")
            continue 

        for page_num, info in mapa_pagina_info.items():
            coladas = info["coladas"]
            texto = info["texto"]
            
            # 1. Buscamos el Steel Grade
            steel_grade = _extraer_valor_de_pagina(
                path_mtc_pdf_original=str(path_mtc_normalizado),
                page_num=page_num,
                valor_a_buscar="Steel Grade",
                texto_pagina_cache=texto
            )
            
            # 2. Buscamos el Tipo de Producto (Tubing/Casing) usando el mismo texto
            tipo_producto = _buscar_tipo_producto_regex(texto)

            for colada in coladas:
                resultados[colada] = {
                    "grade": steel_grade, 
                    "file": original_filename,
                    "product_type": tipo_producto # <--- Nuevo campo
                }

        if str(path_mtc_normalizado) != str(path_mtc):
            try:
                if os.path.exists(path_mtc_normalizado):
                    os.unlink(path_mtc_normalizado)
            except: pass

    # Rellenar no encontrados
    for colada in coladas_pendientes:
        resultados[colada] = {"grade": "No encontrado", "file": "-", "product_type": ""}
    
    return resultados