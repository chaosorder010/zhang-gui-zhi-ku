from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from apps.backend.services.graph import app_graph
from apps.backend.core.config import get_settings

router = APIRouter(prefix="/api", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    session_id: str = Field("default", description="对话 session id, 多轮记忆键")


class AskResponse(BaseModel):
    answer: str
    session_id: str


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    if not get_settings().openai_api_key:
        raise HTTPException(400, "LLM 未配置, 请在 .env 设置 OPENAI_API_KEY")

    config = {"configurable": {"thread_id": req.session_id}}
    result = app_graph.invoke(
        {"messages": [HumanMessage(content=req.question)]},
        config=config,
    )
    answer = result["messages"][-1].content
    return AskResponse(answer=answer, session_id=req.session_id)
