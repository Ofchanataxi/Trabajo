import re
from pypdf import PdfReader

def extraer_datos_logistica(pdf_path: str):
    datos_extraidos = []
    
    try:
        reader = PdfReader(pdf_path)
        
        for page in reader.pages:
            text = page.extract_text()
            if not text: 
                continue
            
            # Limpieza y aplanado del texto
            text_flat = text.replace('\n', ' ').replace('\r', ' ').replace('"', ' ').replace(',', ' ')
            text_flat = re.sub(r'\s+', ' ', text_flat)
            
            # Regex para detectar el inicio de la fila: Order + 3 longitudes decimales
            pattern_start = re.compile(r'\b(\d+)\s+(\d{1,5}\.\d{2})\s+(\d{1,5}\.\d{2})\s+(\d{1,5}\.\d{2})\b')
            matches = list(pattern_start.finditer(text_flat))

            for i, match in enumerate(matches):
                item = {
                    "order": match.group(1),
                    "total_length_ft": match.group(2),
                    "running_length_ft": match.group(3),
                    "cum_running_length": match.group(4)
                }
                
                # Definir chunk de texto hasta la siguiente fila
                start_idx = match.end()
                if i + 1 < len(matches):
                    end_idx = matches[i+1].start()
                else:
                    end_idx = min(len(text_flat), start_idx + 400)
                
                rest_chunk = text_flat[start_idx:end_idx].strip()
                
                # Buscar anclas numéricas (OD, Mass, Drift Diam)
                decimal_matches = list(re.finditer(r'\b\d+\.\d{3,4}\b', rest_chunk))
                
                if len(decimal_matches) >= 3:
                    od_match = decimal_matches[0]
                    mass_match = decimal_matches[1]
                    drift_match = decimal_matches[2]
                    
                    item["product_type"] = rest_chunk[:od_match.start()].strip()
                    item["od_in"] = od_match.group()
                    item["mass_ppf"] = mass_match.group()
                    
                    # Grade y Thread entre Mass y Drift
                    middle_text = rest_chunk[mass_match.end():drift_match.start()].strip()
                    parts_middle = middle_text.split(maxsplit=1)
                    if parts_middle:
                        item["grade"] = parts_middle[0]
                        item["thread"] = parts_middle[1] if len(parts_middle) > 1 else ""
                    else:
                        item["grade"] = ""
                        item["thread"] = ""

                    item["drift_diam_in"] = drift_match.group()
                    
                    # Resto de campos (Cola)
                    tail_text = rest_chunk[drift_match.end():].strip()
                    tokens_tail = tail_text.split()
                    
                    # Identificar Heat, Former, URC por dígitos
                    id_indices = [idx for idx, t in enumerate(tokens_tail) if any(c.isdigit() for c in t) and len(t) > 3]
                    
                    if len(id_indices) >= 3:
                        idx_heat = id_indices[0]
                        idx_former = id_indices[1]
                        idx_urc = id_indices[2]
                        
                        item["drift_type"] = " ".join(tokens_tail[:idx_heat])
                        item["heat"] = tokens_tail[idx_heat]
                        item["former_code"] = tokens_tail[idx_former]
                        item["urc"] = tokens_tail[idx_urc]
                        
                        remaining = tokens_tail[idx_urc+1:]
                        if remaining:
                            item["manuf_proc"] = remaining[-1]
                            item["manuf_norm"] = " ".join(remaining[:-1])
                        else:
                            item["manuf_proc"] = ""
                            item["manuf_norm"] = ""
                    else:
                        # Fallback parcial
                        item["drift_type"] = " ".join(tokens_tail[:2]) if len(tokens_tail) >= 2 else ""
                        item["heat"] = tokens_tail[2] if len(tokens_tail) > 2 else ""
                        item["former_code"] = ""
                        item["urc"] = ""
                        item["manuf_norm"] = ""
                        item["manuf_proc"] = ""
                else:
                    item["product_type"] = rest_chunk
                    for k in ["od_in", "mass_ppf", "grade", "thread", "drift_diam_in", "drift_type", "heat", "former_code", "urc", "manuf_norm", "manuf_proc"]:
                        item[k] = ""
                
                datos_extraidos.append(item)

    except Exception as e:
        print(f"Error en logistica_extractor: {e}", flush=True)
        return []

    return datos_extraidos