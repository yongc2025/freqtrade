"""
Dashboard Pydantic 请求/响应模型
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ========== 交易历史 ==========


class TradeQueryParams(BaseModel):
    pair: Optional[str] = None
    exit_reason: Optional[str] = None
    enter_tag: Optional[str] = None
    is_short: Optional[bool] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_profit: Optional[float] = None
    max_profit: Optional[float] = None
    limit: int = 500
    offset: int = 0


class TradeStats(BaseModel):
    total: int = 0
    total_pnl: float = 0.0
    avg_profit_pct: float = 0.0
    winrate: float = 0.0


class TradeResponse(BaseModel):
    trades: List[Dict[str, Any]] = []
    stats: TradeStats = TradeStats()


class TradeFilters(BaseModel):
    exit_reasons: List[str] = []
    enter_tags: List[str] = []
    pairs: List[str] = []


# ========== 选币扫描 ==========


class ScanItem(BaseModel):
    symbol: str = ""
    display: str = ""
    last_price: float = 0.0
    volume_24h: float = 0.0
    volume_3d_quote: float = 0.0
    price_change_3d: float = 0.0
    high_3d: float = 0.0
    low_3d: float = 0.0
    volume_rank_overall: int = 0
    volume_rank_3d: int = 0
    age_days: Optional[float] = None
    age_ok: bool = True


class ScanResult(BaseModel):
    data: List[ScanItem] = []
    status: str = "idle"
    updated_at: Optional[str] = None
    count: int = 0
    error: Optional[str] = None


# ========== 实盘报告 ==========


class ReportStatus(BaseModel):
    status: str = "idle"
    log: str = ""
    updated_at: Optional[str] = None


class ReportDataResponse(BaseModel):
    status: str = "idle"
    data: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None


class RunReportResponse(BaseModel):
    message: str = "started"
    balance: float = 0.0
    db: str = ""


# ========== 回测对比 ==========


class CompareResult(BaseModel):
    ready: bool = False
    overview: Dict[str, Any] = {}
    diagnosis: Dict[str, Any] = {}
    attribution: Dict[str, Any] = {}
    matching: Dict[str, Any] = {}


# ========== Bot 信息 ==========


class BotInfo(BaseModel):
    exchange: str = "unknown"
    stake_currency: str = "USDT"
    trading_mode: str = "spot"
    run_mode: str = "unknown"
    db_path: str = ""
    starting_balance: float = 1000.0
    dry_run: bool = True
    current_balance: Optional[float] = None
    db_exists: bool = False
    db_total_trades: int = 0
    db_closed_trades: int = 0
