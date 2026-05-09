from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
import os

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("/databases")
async def list_databases(request: Request):
    """列出 user_data 目录下所有的 sqlite 数据库文件"""
    # 修正路径获取方式
    root = Path(__file__).parent.parent.parent.parent
    user_data_dir = root / "user_data"
    
    dbs = []
    if user_data_dir.exists():
        for f in user_data_dir.glob("*.sqlite"):
            # 排除 shm 和 wal 文件
            if f.suffix == ".sqlite":
                dbs.append(f.name)
    
    return {"databases": sorted(dbs)}

@router.get("/current-db")
async def get_current_db(request: Request):
    """获取当前正在使用的数据库文件名"""
    db_path = request.app.state.trade_service.db_path
    return {"current_db": db_path.name}

@router.post("/switch-db")
async def switch_database(request: Request, db_name: str):
    """切换当前使用的数据库文件"""
    root = Path(__file__).parent.parent.parent.parent
    db_path = root / "user_data" / db_name
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    
    # 更新 TradeService 和 LiveReporter 的数据库路径
    request.app.state.trade_service.db_path = db_path
    request.app.state.reporter.db_path = db_path
    
    return {"message": f"Switched to {db_name}", "current_db": db_name}
