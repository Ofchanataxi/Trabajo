from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 

def extraer_datos_tally_tenaris(pdf_path: str) -> dict:

    print("extraer_datos_tally_tenaris")
    data = extract_data_from_pdf(pdf_path)

    # Rules from TENARIS
    data_converted = config_tally_tenaris.obtain_data_tally_tenaris(data)
    
    if len(data_converted) == 0:
        return None
    
    return {}