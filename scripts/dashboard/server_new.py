import sys
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# 路径初始化
THIS_DIR = Path(__file__).parent
ROOT = THIS_DIR.parent.parent

# 引入服务模块
from services.core import TradeService, MarketScanner, LiveReporter
from routers import trades, analysis

# 配置参数 - 支持从命令行读取 (例如: python server_new.py db.sqlite 1000 8788)
DB_NAME = sys.argv[1] if len(sys.argv) > 1 else "tradesv3_momentum_live_v2.sqlite"
DB_PATH = ROOT / "user_data" / Path(DB_NAME).name
STARTING_BALANCE = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8788

LIVE_REPORT_SCRIPT = THIS_DIR / "scripts" / "live_report.py"
LIVE_REPORT_JSON = ROOT / "user_data" / "live_report.json"
SCAN_CACHE_FILE = ROOT / "user_data" / "market_scan_cache.json"

# 初始化服务
scanner = MarketScanner(SCAN_CACHE_FILE)
reporter = LiveReporter(DB_PATH, LIVE_REPORT_SCRIPT, LIVE_REPORT_JSON)
trade_service = TradeService(DB_PATH)

app = FastAPI(title="FreqTrade Dashboard")
app.state.trade_service = trade_service
app.state.scanner = scanner
app.state.reporter = reporter

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 挂载静态文件
app.mount("/static", StaticFiles(directory=THIS_DIR / "static"), name="static")
app.mount("/views", StaticFiles(directory=THIS_DIR / "views"), name="views")

# 挂载模块化路由
app.include_router(trades.router)
app.include_router(analysis.router)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((THIS_DIR / "index.html").read_text(encoding="utf-8"))

@app.get("/api/market-scan")
async def get_scan():
    return {
        "data": scanner.data,
        "status": scanner.status,
        "updated_at": scanner.updated_at,
        "count": scanner.count,
        "error": scanner.error,
    }

@app.post("/api/market-scan/refresh")
async def refresh_scan(bg: BackgroundTasks):
    if scanner.status == "running":
        return {"message": "already running"}
    bg.add_task(scanner.scan)
    return {"message": "started"}

@app.get("/api/live-report/status")
async def get_report_status():
    return {"status": reporter.status, "log": reporter.log, "updated_at": reporter.updated_at}

@app.get("/api/live-report/data")
async def get_report_data():
    return {"status": reporter.status, "data": reporter.data, "updated_at": reporter.updated_at}

@app.post("/api/live-report/run")
async def run_report(bg: BackgroundTasks):
    bg.add_task(reporter.run_analysis, STARTING_BALANCE)
    return {"message": "started"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
