import arxiv
import pytz
import openai
import time
import logging
from pydantic import BaseModel
from typing import List
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


openai.api_key = OPENAI_API_KEY


def retry_on_error(func, retries=3, delay=5):
    def wrapper(*args, **kwargs):
        for _ in range(retries):
            try:
                return func(*args, **kwargs)
            except openai.error.RateLimitError as e:
                logger.warning(f"RateLimitError: {e}, Retrying...")
                time.sleep(delay)
        logger.error("Exceeded maximum retries.")
        return None

    return wrapper


class ArxivResponse(BaseModel):
    entry_id: str
    title: str
    summary: str
    url: str
    submitted: str


def fetch_interesting_points(result):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"""以下の論文がどういう点で面白いかについて初学者にも分かりやすく解説し、論文の本文を読みたくなるように魅力づけをして促して下さい。
             論文タイトル: {result.title}\n概要: {result.summary}\n概要: {result.summary}\n\n""",
            },
        ],
    )
    res_interesting = response["choices"][0]["message"]["content"].strip()
    return res_interesting


def fetch_summary(result):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"""論文タイトル: {result.title}\n概要: {result.summary}\n\n日本語の箇条書き（・で表記）で要約してください。""",
            },
        ],
    )
    summary = response["choices"][0]["message"]["content"].strip()
    return summary


def get_papers(
    db, keyword: List[str] = ["LLM", "GPT", "LFM", "LLMM"], max_results: int = 20
):
    query = " OR ".join([f'ti:"{k}"' for k in keyword])
    exclude_ids = db.get_excluded_papers()

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    logger.info(f"arxiv response : {search.results()}")

    results = []
    for result in search.results():
        if result.entry_id in exclude_ids:
            continue
        submitted_jst = result.published.astimezone(pytz.timezone("Asia/Tokyo"))
        submitted_formatted = submitted_jst.strftime("%Y年%m月%d日 %H時%M分%S秒")
        results.append(
            ArxivResponse(
                entry_id=result.entry_id,
                title=result.title,
                summary=result.summary,
                url=result.pdf_url,
                submitted=submitted_formatted,
            )
        )
    if not results:
        return
    picked_paper = results[0]
    db.add_paper(picked_paper.entry_id)
    logger.info(f"INSERT : {picked_paper.entry_id} / {picked_paper.title}")

    return picked_paper
