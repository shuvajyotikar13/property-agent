from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from agent import chat_with_agent
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    text: str

@app.post("/chat")
async def chat_endpoint(query: Query):
    return StreamingResponse(chat_with_agent(query.text), media_type="text/plain")
