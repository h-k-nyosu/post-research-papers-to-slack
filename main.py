from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import arxiv
import pytz

app = FastAPI()

class ArxivResponse(BaseModel):
    entry_id: str
    title: str
    summary: str
    url: str
    submitted: str

@app.get("/papers", response_model=List[ArxivResponse])
async def get_papers(
    keyword: List[str] = Query(["LLM", "GPT", "LFM", "LLMM"]),
    max_results: int = 10,
    exclude_ids: Optional[List[str]] = Query(None)
):
    query = " OR ".join([f"ti:\"{k}\"" for k in keyword])
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    results = []
    for result in search.results():
        if exclude_ids and result.entry_id in exclude_ids:
            continue
        submitted_jst = result.published.astimezone(pytz.timezone('Asia/Tokyo'))
        submitted_formatted = submitted_jst.strftime('%Y年%m月%d日 %H時%M分%S秒')
        results.append(
            ArxivResponse(
                entry_id=result.entry_id,
                title=result.title,
                summary=result.summary,
                url=result.pdf_url,
                submitted=submitted_formatted,
            )
        )

    return results
