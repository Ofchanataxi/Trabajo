import re
import os
from pypdf import PdfReader
from typing import List, Dict, Optional
from app.services.extractors.extractor_valor_dinamico import extraer_valor_dinamico
from app.services.extract_data_from_pdf import normalize_rotation

def _buscar_con_regex(texto: str, patron: str) -> Optional[str]:
    """Busca un valor usando Regex en el texto plano."""
    if not texto:
        return None
    
    # Patrones comunes para Steel Grade. 
    # Busca "Steel Grade", dos puntos o espacio opcionales, y captura el valor alfanumérico
    # Ej: "Steel Grade: L80", "Steel Grade L-80", "Grade: P110"
    regexs = [
        r"Steel Grade\s*[:\.]?\s*([A-Za-z0-9-]+)",
        r"Grade\s*[:\.]?\s*([A-Za-z0-9-]+)",
        r"Material\s*[:\.]?\s*([A-Za-z0-9-]+)"
    ]
    
    for r in regexs:
        match = re.search(r, texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def _extraer_valor_de_pagina(
    path_mtc_pdf_original: str, 
    page_num: int, 
    valor_a_buscar: str,
    texto_pagina_cache: str = None
) -> str:
    """
    Intenta extraer primero con Regex (rápido) y falla hacia Tabula (lento).
    """
    # --- OPTIMIZACIÓN: INTENTO RÁPIDO ---
    if texto_pagina_cache:
        print(f"   ↳ Buscando '{valor_a_buscar}' con Regex en página {page_num}...")
        valor_rapido = _buscar_con_regex(texto_pagina_cache, valor_a_buscar)
        if valor_rapido:
            print(f"   ✅ ¡Encontrado rápido!: {valor_rapido}")
            return valor_rapido
    # ------------------------------------

    print(f"   ↳ Regex falló. Usando extracción pesada (Tabula) en página {page_num}...")
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
    except Exception as e:
        print(f"Error en extracción pesada: {e}")
        return "Error extracción"

def extraer_steel_grade_de_mtc(files_info: List[tuple], coladas_a_buscar: List[str]) -> Dict[str, Dict[str, str]]:
    # El resultado ahora será: { "HEAT123": { "grade": "L80", "file": "MTC_original.pdf" } }
    resultados: Dict[str, Dict[str, str]] = {}
    coladas_pendientes = set(coladas_a_buscar)
    
    # Desempaquetamos la tupla
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
                
                texto_pagina = page.extract_text()
                if not texto_pagina:
                    continue
                
                encontradas_aqui = []
                for colada in list(coladas_pendientes):
                    if colada in texto_pagina:
                        encontradas_aqui.append(colada)
                        coladas_pendientes.remove(colada)
                
                if encontradas_aqui:
                    page_num_actual = i + 1
                    mapa_pagina_info[page_num_actual] = {
                        "coladas": encontradas_aqui,
                        "texto": texto_pagina
                    }

        except Exception as e:
            print(f"Error leyendo texto de {original_filename}: {e}")
            continue 

        for page_num, info in mapa_pagina_info.items():
            coladas = info["coladas"]
            texto = info["texto"]
            
            steel_grade = _extraer_valor_de_pagina(
                path_mtc_pdf_original=str(path_mtc_normalizado),
                page_num=page_num,
                valor_a_buscar="Steel Grade",
                texto_pagina_cache=texto
            )
            
            for colada in coladas:
                # AQUÍ GUARDAMOS EL GRADO Y EL NOMBRE DEL ARCHIVO
                resultados[colada] = {
                    "grade": steel_grade, 
                    "file": original_filename
                }

        # Limpieza de archivo temporal... (código existente)
        if str(path_mtc_normalizado) != str(path_mtc):
            try:
                if os.path.exists(path_mtc_normalizado):
                    os.unlink(path_mtc_normalizado)
            except:
                pass

    # Para los no encontrados
    for colada in coladas_pendientes:
        resultados[colada] = {"grade": "No encontrado", "file": "-"}
    
    return resultados