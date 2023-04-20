import os
import arxiv
import pytz
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import openai
from dotenv import load_dotenv
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


load_dotenv()

SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]
openai.api_key = os.environ["OPENAI_API_KEY"]

app = FastAPI()


def init_database():
    conn = sqlite3.connect("papers.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS papers (entry_id TEXT PRIMARY KEY, timestamp DATETIME)"
    )
    conn.commit()
    conn.close()


init_database()


def add_paper_to_db(entry_id):
    conn = sqlite3.connect("papers.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO papers (entry_id, timestamp) VALUES (?, datetime('now'))",
        (entry_id,),
    )
    conn.commit()
    conn.close()


def get_excluded_papers():
    conn = sqlite3.connect("papers.db")
    c = conn.cursor()
    c.execute("SELECT entry_id FROM papers")
    exclude_ids = [row[0] for row in c.fetchall()]
    conn.close()
    return exclude_ids


class ArxivResponse(BaseModel):
    entry_id: str
    title: str
    summary: str
    url: str
    submitted: str


def get_papers(
    keyword: List[str] = ["LLM", "GPT", "LFM", "LLMM"], max_results: int = 10
):
    query = " OR ".join([f'ti:"{k}"' for k in keyword])

    exclude_ids = get_excluded_papers()

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
    add_paper_to_db(picked_paper.entry_id)
    logger.info(f"INSERT : {picked_paper.entry_id} / {picked_paper.title}")

    return picked_paper


client = WebClient(token=SLACK_API_TOKEN)


def post_to_slack(text):
    try:
        response = client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
    except SlackApiError as e:
        logger.error(f"Error posting to Slack: {e}")


def fetch_interesting_points(result):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"""以下の論文がどういう点で面白いかについて初学者にも分かりやすく解説し、論文の本文を読みたくなるように魅力づけをして促して下さい。
             論文タイトル: {result.title}\n概要: {result.summary}\n\n""",
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
                "content": f"""
             論文タイトル: {result.title}\n概要: {result.summary}\n\n日本語の箇条書き（・で表記）で要約してください。""",
            },
        ],
    )
    summary = response["choices"][0]["message"]["content"].strip()
    return summary


def main():
    paper = get_papers()
    if not paper:
        logger.info("No new papers found.")
        return
    print(paper)
    summary = fetch_summary(paper)
    interesting_points = fetch_interesting_points(paper)
    text = f"*タイトル: {paper.title}*\n\n*概要*\n{summary}\n\n*リンク*\n{paper.url}\n\n*提出日*\n{paper.submitted}\n\n*以下、面白いポイント*\n{interesting_points}\n\nChatPDFで読む: https://www.chatpdf.com/ \n\n 論文を読む: {paper.url}.pdf"
    post_to_slack(text)
    logger.info(f"Posted a paper: {paper.title}")


scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
scheduler.add_job(main, IntervalTrigger(minutes=5))
scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
