# app/models/extraction_models.py
from pydantic import BaseModel
from typing import List, Dict, Any

class ExtractionResponse(BaseModel):
    data: Dict[str, List[Any]]