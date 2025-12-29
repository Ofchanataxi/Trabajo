import pandas as pd
from typing import Dict, Optional, List
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.extractors.pdf_extractor_core import get_adjacent_value

def _buscar_en_tablas(
    tablas: Optional[List[pd.DataFrame]], 
    valor_a_buscar: str, 
    posicion_dato: str, 
    modo_busqueda: str,
    buscar_en_cabecera: bool
) -> Optional[Dict[str, str]]:
    if not tablas:
        return None
        
    for i, df in enumerate(tablas):
        valor_encontrado = get_adjacent_value(
            df, 
            anchor_text=valor_a_buscar, 
            direction=posicion_dato,
            buscar_en_cabecera=buscar_en_cabecera
        )
        if valor_encontrado is not None:
            print(f"  Encontrado en Tabla {modo_busqueda} {i}: {valor_encontrado}")
            return {
                "valor_buscado": valor_a_buscar,
                "posicion": posicion_dato,
                "valor_encontrado": valor_encontrado,
                "modo_busqueda": modo_busqueda
            }
    return None


def extraer_valor_dinamico(
    pdf_path: str, 
    valor_a_buscar: Optional[str], 
    posicion_dato: Optional[str],
    modo_busqueda: Optional[str],
    buscar_en_cabecera: bool,
    pages: str="all"
) -> Optional[Dict[str, str]]:
    print(f"--- Ejecutando extractor_valor_dinamico (ID 333) ---")
    print(f"Buscando: '{valor_a_buscar}', Posición: '{posicion_dato}', Modo: '{modo_busqueda}', Cabeceras: {buscar_en_cabecera}")
    
    if not valor_a_buscar or not posicion_dato:
        return {"error": "Para release_type 333, 'valor_a_buscar' y 'posicion_dato' son requeridos."}

    use_lattice = True
    modo_str = "lattice"
    if modo_busqueda == "stream":
        use_lattice = False
        modo_str = "stream"

    print(f"Paso 1: Buscando SÓLO en modo {modo_str}...")
    
    tablas = extract_data_from_pdf(pdf_path, lattice=use_lattice, pages=pages)
    
    resultado = _buscar_en_tablas(
        tablas, 
        valor_a_buscar, 
        posicion_dato, 
        modo_str,
        buscar_en_cabecera=buscar_en_cabecera
    )

    if resultado:
        return resultado

    print(f"No se encontró el valor en modo {modo_str}.")
    return None