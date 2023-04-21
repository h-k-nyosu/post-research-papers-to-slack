import os

SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DATABASE_NAME = "papers.db"

SEARCH_KEYWORDS = ["LLM", "GPT", "LFM", "prompt"]
SEARCH_AUTHORS = []  # ["John Doe", "Jane Smith"] のように検索する著者名を追加できます（完全一致検索）
