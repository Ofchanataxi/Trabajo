import re
import pandas as pd
from typing import List
from app.services.data_cleaner import build_final_description

def clean_quantities(quantities: List) -> List[str]:
    cantidades_limpias = []
    for valor in quantities:
        if pd.isna(valor):
            cantidades_limpias.append("")
            continue
        texto = str(valor).strip()
        match = re.search(r'\d+(?:\.\d+)?', texto)
        cantidades_limpias.append(match.group(0) if match else "")
    return cantidades_limpias


def merge_descriptions(descriptions: List, num_rows: int) -> List[str]:

    descriptions1 = descriptions[0:num_rows]
    descriptions2 = descriptions[num_rows:]
    final_descriptions = []

    for d1, d2 in zip(descriptions1, descriptions2):
        d1 = str(d1).strip() if pd.notna(d1) else ""
        d2 = str(d2).strip() if pd.notna(d2) else ""
        final_descriptions.append(build_final_description(d1, d2))

    return final_descriptions
