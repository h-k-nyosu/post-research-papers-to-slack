import os
import asyncio
import arxiv
import pytz
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import openai
from dotenv import load_dotenv

load_dotenv()
SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]
openai.api_key = os.environ["OPENAI_API_KEY"]




app = FastAPI()


client = WebClient(token=SLACK_API_TOKEN)

class ArxivResponse(BaseModel):
    entry_id: str
    title: str
    summary: str
    url: str
    submitted: str

async def get_papers(keyword: List[str] = ["LLM", "GPT", "LFM", "LLMM"], max_results: int = 1, exclude_ids: Optional[str] = ""):
    query = " OR ".join([f"ti:\"{k}\"" for k in keyword])

    exclude_id_list = exclude_ids.split("_") if exclude_ids else []

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    results = []
    for result in search.results():
        if exclude_id_list and result.entry_id in exclude_id_list:
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

def post_to_slack(text):
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=text
        )
    except SlackApiError as e:
        print(f"Error posting to Slack: {e}")


async def fetch_summary(result):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"""
             論文タイトル: {result.title}\n概要: {result.summary}\n\n日本語の箇条書き（・で表記）で要約してください。"""},
        ]
    )

    summary = response['choices'][0]['message']['content'].strip()
    return summary



async def main():
    papers = await get_papers()
    for paper in papers:
        summary = await fetch_summary(paper)
        text = f"*タイトル: {paper.title}*\n\n*概要*\n{summary}\n\n*リンク*\n{paper.url}\n\n*提出日*\n{paper.submitted}\n"
        post_to_slack(text)


scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
scheduler.add_job(main, IntervalTrigger(minutes=1))  # 朝6時日本時間はUTCの21時
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

