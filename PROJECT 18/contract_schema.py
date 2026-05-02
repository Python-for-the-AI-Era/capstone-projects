from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class ContractSchema(BaseModel):
    parties: List[str] = Field(description="Names of the organizations or individuals involved")
    effective_date: Optional[date] = Field(description="The date the contract starts")
    governing_law: str = Field(description="The jurisdiction (e.g., Laws of the Federation of Nigeria)")
    penalty_amount: Optional[float] = Field(description="Specific monetary penalty for breach")
    termination_clause: str = Field(description="The full text explaining how to end the contract")