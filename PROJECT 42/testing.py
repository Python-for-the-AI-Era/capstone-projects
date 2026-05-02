class MockScoringClient:
    def __init__(self, preset_score: float = 0.85):
        self.preset_score = preset_score

    def score(self, features: Dict[str, float]) -> ScoringResponse:
        return ScoringResponse(score=self.preset_score, model_version="mock-1.0")

    def health(self) -> bool:
        return True