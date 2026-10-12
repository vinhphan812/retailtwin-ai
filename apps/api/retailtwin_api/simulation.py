from typing import List
from pydantic import BaseModel

class SimulationSummary(BaseModel):
    simulation_id: str
    proposed_actions: List[str]
    status: str

class SimulationCandidateDTO(BaseModel):
    candidate_id: str
    simulation_id: str
    kpi_score: float

class SimulationRepository:
    def __init__(self):
        self._simulations = {}
        
    def list_simulations(self) -> List[SimulationSummary]:
        return list(self._simulations.values())
        
    def get_candidates(self, simulation_id: str) -> List[SimulationCandidateDTO]:
        return []
