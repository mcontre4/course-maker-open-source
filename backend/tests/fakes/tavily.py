from tavily import AsyncTavilyClient


class RecordingTavilyClient(AsyncTavilyClient):
    def __init__(self):
        self.queries = []

    async def search(self, query, **kwargs):
        self.queries.append((query, kwargs))
        return {
            "results": [
                {
                    "title": "Python tutorial",
                    "url": "https://docs.python.org/3/tutorial/",
                    "content": "Official Python tutorial",
                    "score": 1.0,
                }
            ]
        }
