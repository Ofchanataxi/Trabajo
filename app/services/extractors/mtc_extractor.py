import re
import os
import concurrent.futures
from pypdf import PdfReader
from typing import List, Dict, Optional, Any
from app.services.extractors.extractor_valor_dinamico import extraer_valor_dinamico
from app.services.extract_data_from_pdf import normalize_rotation

MARKER_FALLBACK = "__REQ_TABULA__"

def _buscar_con_regex(texto: str) -> Optional[str]:
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
    if not texto: return ""
    texto_upper = texto.upper()
    if "TUBING" in texto_upper and "CASING" not in texto_upper:
        return "Tubing"
    if "CASING" in texto_upper and "TUBING" not in texto_upper:
        return "Casing"
        
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

def _resolver_valor_con_tabula(
    path_mtc_pdf_original: str, 
    page_num: int, 
    valor_a_buscar: str
) -> str:
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

def _procesar_un_mtc_fase_rapida(args) -> Dict[str, Dict[str, Any]]:
    path_mtc, original_filename, coladas_a_buscar = args
    resultados_archivo = {}
    
    path_mtc_normalizado = normalize_rotation(path_mtc)
    mapa_pagina_info = {}

    try:
        reader = PdfReader(path_mtc_normalizado)
        for i, page in enumerate(reader.pages):
            texto_pagina = page.extract_text() or ""
            
            encontradas_aqui = [c for c in coladas_a_buscar if c in texto_pagina]
            
            if encontradas_aqui:
                mapa_pagina_info[i + 1] = {
                    "coladas": encontradas_aqui,
                    "texto": texto_pagina
                }
        
        for page_num, info in mapa_pagina_info.items():
            coladas = info["coladas"]
            texto = info["texto"]
            
            steel_grade = _buscar_con_regex(texto)
            if not steel_grade:
                steel_grade = (MARKER_FALLBACK, page_num)
            
            tipo_producto = _buscar_tipo_producto_regex(texto)

            for colada in coladas:
                resultados_archivo[colada] = {
                    "grade": steel_grade, 
                    "file": original_filename,
                    "product_type": tipo_producto,
                    "temp_path": str(path_mtc_normalizado) # Necesario para Fase 2
                }

    except Exception as e:
        print(f"Error procesando {original_filename}: {e}")
            
    return resultados_archivo

def _procesar_un_itp(args) -> Dict[str, str]:
    path_pdf, original_filename, coladas_a_buscar = args
    resultados_archivo = {}
    
    path_normalizado = normalize_rotation(path_pdf)
    try:
        reader = PdfReader(path_normalizado)
        for page in reader.pages:
            texto_pagina = page.extract_text() or ""
            for colada in coladas_a_buscar:
                if colada in texto_pagina:
                    resultados_archivo[colada] = original_filename
    except Exception as e:
        print(f"Error leyendo ITP {original_filename}: {e}")
    finally:
        if str(path_normalizado) != str(path_pdf):
             try:
                if os.path.exists(path_normalizado):
                    os.unlink(path_normalizado)
             except: pass
             
    return resultados_archivo

def extraer_steel_grade_de_mtc(files_info: List[tuple], coladas_a_buscar: List[str]) -> Dict[str, Dict[str, str]]:
    resultados_globales = {}
    rutas_temporales_creadas = set()
    max_workers_fase1 = min(os.cpu_count() or 4, 8)
    
    work_items = [(path, fname, coladas_a_buscar) for path, fname in files_info]
    
    pendientes_de_tabula = [] # Lista de tuplas (colada, path_pdf, page_num)

    print(f"--- Iniciando FASE 1 (Regex Paralelo) con {max_workers_fase1} workers ---", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers_fase1) as executor:
        futures = [executor.submit(_procesar_un_mtc_fase_rapida, item) for item in work_items]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                res_parcial = future.result()
                
                for colada, datos in res_parcial.items():
                    val_grade = datos["grade"]
                    rutas_temporales_creadas.add(datos.get("temp_path"))
                    
                    if isinstance(val_grade, tuple) and val_grade[0] == MARKER_FALLBACK:
                        page_num = val_grade[1]
                        path_pdf = datos["temp_path"] # Usamos el rotado
                        pendientes_de_tabula.append((colada, path_pdf, page_num))
                        datos["grade"] = "Buscando..." 
                    
                    resultados_globales[colada] = datos

            except Exception as e:
                print(f"Excepción en worker MTC Fase 1: {e}")

    if pendientes_de_tabula:
        print(f"--- Iniciando FASE 2 (Tabula) para {len(pendientes_de_tabula)} elementos ---", flush=True)
        cache_tabula = {} # {(path, page): "ValorEncontrado"}

        for colada, path_pdf, page_num in pendientes_de_tabula:
            key = (path_pdf, page_num)
            
            if key in cache_tabula:
                valor_final = cache_tabula[key]
            else:
                print(f"   -> Ejecutando Tabula en {os.path.basename(path_pdf)} Pag {page_num}...", flush=True)
                valor_final = _resolver_valor_con_tabula(path_pdf, page_num, "Steel Grade")
                cache_tabula[key] = valor_final
            
            if colada in resultados_globales:
                resultados_globales[colada]["grade"] = valor_final

    for path_temp in rutas_temporales_creadas:
        if path_temp and "rot0.pdf" in path_temp and os.path.exists(path_temp):
             try: os.unlink(path_temp)
             except: pass

    for colada in coladas_a_buscar:
        if colada not in resultados_globales:
            resultados_globales[colada] = {"grade": "No encontrado", "file": "-", "product_type": ""}

    for k, v in resultados_globales.items():
        if "temp_path" in v:
            del v["temp_path"]

    return resultados_globales

def buscar_coladas_en_pdfs(files_info: List[tuple], coladas_a_buscar: List[str]) -> Dict[str, str]:
    resultados_globales = {}
    work_items = [(path, fname, coladas_a_buscar) for path, fname in files_info]
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(_procesar_un_itp, item) for item in work_items]
        for future in concurrent.futures.as_completed(futures):
            try:
                resultados_globales.update(future.result())
            except Exception as e:
                print(f"Excepción en worker ITP: {e}")

    for colada in coladas_a_buscar:
        if colada not in resultados_globales:
            resultados_globales[colada] = "-"
            
    return resultados_globales