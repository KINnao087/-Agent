import json
import os

from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

def tavliy_search(q: str, sdepth: str = "advanced") -> dict:
    # return {
    #     "query": q,
    #     "search_depth": sdepth,
    #     "follow_up_questions": None,
    #     "answer": None,
    #     "images": [],
    #     "results": [
    #         {
    #             "url": "https://baike.baidu.com/item/%E8%85%BE%E8%AE%AF/112204",
    #             "title": "腾讯_百度百科",
    #             "content": "腾讯，全称深圳市腾讯计算机系统有限公司，是一家互联网科技公司。",
    #             "score": 0.91,
    #             "raw_content": None,
    #         }
    #     ],
    #     "response_time": 0,
    #     "request_id": "mock",
    # }

    return client.search(query = q, search_septh=sdepth)


def main():
    return 0

if __name__ == '__main__':
    main()