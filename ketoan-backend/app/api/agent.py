from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentAlert
from app.agent.orchestrator import run_agent_turn
from app.core.audit import write_audit_log
from app.services.watchdog_service import find_alerts

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat(payload: AgentChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Agent tra cứu (READ) và soạn thẻ đề xuất phiếu chi (propose). Không có tool ghi
    dữ liệu: muốn lưu phiếu, giao diện gọi POST /vouchers/ — đúng đường RBAC thường.
    """
    try:
        result = run_agent_turn(db, payload.message, payload.history, payload.context)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    write_audit_log(
        db, entity_type="agent_chat", entity_id=current_user.id, action="chat",
        actor_id=current_user.id, actor_type="agent",
        after_data={
            "tools_used": result.tool_calls_made,
            "proposals": len(result.proposals),
            "message_preview": payload.message[:200],
        },
    )
    db.commit()

    return AgentChatResponse(
        reply=result.reply, history=result.history,
        tool_calls_made=result.tool_calls_made, proposals=result.proposals,
    )


@router.get("/alerts", response_model=list[AgentAlert])
def alerts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Cảnh báo chủ động (giá lệch, công nợ quá hạn, thiếu CCCD) — quy tắc xác định, không gọi LLM."""
    return find_alerts(db)
