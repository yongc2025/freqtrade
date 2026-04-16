from fastapi import APIRouter, HTTPException, Request, Query
from typing import List, Optional
import sqlite3
import os

router = APIRouter(prefix="/api/trades", tags=["trades"])

@router.get("")
async def get_trades(
    request: Request,
    pair: Optional[str] = Query(None),
    exit_reason: Optional[str] = Query(None),
    enter_tag: Optional[str] = Query(None),
    is_short: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_profit: Optional[float] = Query(None),
    max_profit: Optional[float] = Query(None)
):
    # 使用 app.state 中挂载的全局实例
    svc = request.app.state.trade_service
    filters = {
        "pair": pair,
        "exit_reason": exit_reason,
        "enter_tag": enter_tag,
        "is_short": is_short,
        "date_from": date_from,
        "date_to": date_to,
        "min_profit": min_profit,
        "max_profit": max_profit
    }
    trades, stats = svc.query(**filters)
    return {"trades": trades, "stats": stats}

@router.get("/filters")
async def get_filters(request: Request):
    svc = request.app.state.trade_service
    return svc.get_filters()
