from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
import os

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("/databases")
async def list_databases(request: Request):
    """同时支持本地 Windows 和服务器 Docker 环境的数据库列表获取"""
    from pathlib import Path
    
    # 按照优先级探测路径
    # 1. 探测 Docker 容器内的绝对路径 (对应你的 compose 挂载)
    # 2. 探测基于代码位置向上回溯的路径 (本地开发常用)
    # 3. 探测当前工作目录
    
    candidates = [
        Path("/freqtrade/user_data"),
        Path(__file__).resolve().parent.parent.parent.parent / "user_data",
        Path.cwd() / "user_data"
    ]
    
    user_data_dir = None
    for p in candidates:
        if p.exists() and p.is_dir():
            user_data_dir = p
            break
    
    dbs = []
    if user_data_dir:
        # 只匹配 .sqlite 结尾，且排除 SQL 临时文件
        dbs = [f.name for f in user_data_dir.glob("*.sqlite") 
               if f.is_file() and not f.name.endswith(("-shm", "-wal"))]
    
    return {
        "databases": sorted(list(set(dbs))),
        "environment": "docker" if str(user_data_dir).startswith("/freqtrade") else "local",
        "active_path": str(user_data_dir)
    }

@router.get("/current-db")
async def get_current_db(request: Request):
    """获取当前正在使用的数据库文件名"""
    db_path = request.app.state.trade_service.db_path
    return {"current_db": db_path.name}

@router.post("/switch-db")
async def switch_database(request: Request, db_name: str):
    """切换当前使用的数据库文件，同时支持两种环境"""
    from pathlib import Path
    
    candidates = [
        Path("/freqtrade/user_data") / db_name,
        Path(__file__).resolve().parent.parent.parent.parent / "user_data" / db_name,
        Path.cwd() / "user_data" / db_name
    ]
    
    db_path = None
    for p in candidates:
        if p.exists():
            db_path = p
            break
            
    if not db_path:
        raise HTTPException(status_code=404, detail=f"Database {db_name} not found")
    
    # 更新全局服务状态
    request.app.state.trade_service.db_path = db_path
    request.app.state.reporter.db_path = db_path
    
    return {"message": f"Switched to {db_name}", "path": str(db_path)}
