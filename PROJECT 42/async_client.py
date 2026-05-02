class AsyncScoringClient:
    def __init__(self, base_url: str, api_key: str):
        self.client = httpx.AsyncClient(base_url=base_url, headers={"X-API-Key": api_key})

    async def batch_score(self, feature_list: List[Dict[str, float]]) -> List[ScoringResponse]:
        async with self.client as client:
            # Concurrent processing of scores
            responses = await asyncio.gather(*[
                client.post("/v1/score", json=f) for f in feature_list
            ])
            return [ScoringResponse(**r.json()) for r in responses]