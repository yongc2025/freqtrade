"""
FreqUI 统计分析 API 路由
前缀: /api/v1/dashboard

迁移自:
  - scripts/dashboard/routers/trades.py
  - scripts/dashboard/routers/analysis.py (完整迁移 _build_compare_payload)
  - scripts/dashboard/routers/config.py
  - scripts/dashboard/server_new.py (market-scan, live-report)
"""

import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from freqtrade.rpc.api_server.dashboard_schemas import (
    BotInfo,
    ReportDataResponse,
    ReportStatus,
    RunReportResponse,
    ScanResult,
    TradeFilters,
    TradeResponse,
)

def _require_dashboard(request: Request):
    """依赖守卫：确保 Dashboard 服务已初始化"""
    if not getattr(request.app.state, "dashboard_trade_service", None):
        raise HTTPException(
            status_code=503,
            detail="Dashboard services not initialized. Check freqtrade logs.",
        )


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(_require_dashboard)],
)


# ============================================================================
# 交易历史
# ============================================================================


@router.get("/trades", response_model=TradeResponse)
async def dashboard_trades(
    request: Request,
    pair: Optional[str] = Query(None),
    exit_reason: Optional[str] = Query(None),
    enter_tag: Optional[str] = Query(None),
    is_short: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_profit: Optional[float] = Query(None),
    max_profit: Optional[float] = Query(None),
    limit: int = Query(500),
    offset: int = Query(0),
):
    """查询历史交易记录（已平仓），支持多维筛选"""
    svc = request.app.state.dashboard_trade_service
    filters = {
        "pair": pair,
        "exit_reason": exit_reason,
        "enter_tag": enter_tag,
        "is_short": is_short,
        "date_from": date_from,
        "date_to": date_to,
        "min_profit": min_profit,
        "max_profit": max_profit,
        "limit": limit,
        "offset": offset,
    }
    trades, stats = svc.query(**filters)
    return TradeResponse(trades=trades, stats=stats)


@router.get("/trades/filters", response_model=TradeFilters)
async def dashboard_filters(request: Request):
    """获取筛选选项（卖出原因、入场标签、交易对列表）"""
    svc = request.app.state.dashboard_trade_service
    result = svc.get_filters()
    return TradeFilters(**result)


# ============================================================================
# 选币扫描
# ============================================================================


@router.get("/market-scan", response_model=ScanResult)
async def get_scan(request: Request):
    """获取最新扫描结果"""
    scanner = request.app.state.dashboard_scanner
    return ScanResult(
        data=scanner.data,
        status=scanner.status,
        updated_at=scanner.updated_at,
        count=scanner.count,
        error=scanner.error,
    )


@router.post("/market-scan/refresh")
async def refresh_scan(request: Request, bg: BackgroundTasks):
    """触发后台扫描"""
    scanner = request.app.state.dashboard_scanner
    if scanner.status == "running":
        return {"message": "already running"}
    bg.add_task(scanner.scan)
    return {"message": "started"}


# ============================================================================
# 实盘报告
# ============================================================================


@router.get("/live-report/status", response_model=ReportStatus)
async def report_status(request: Request):
    """获取报告生成状态"""
    reporter = request.app.state.dashboard_reporter
    return ReportStatus(
        status=reporter.status,
        log=reporter.log,
        updated_at=reporter.updated_at,
    )


@router.get("/live-report/data", response_model=ReportDataResponse)
async def report_data(request: Request):
    """获取报告数据"""
    reporter = request.app.state.dashboard_reporter
    return ReportDataResponse(
        status=reporter.status,
        data=reporter.data,
        updated_at=reporter.updated_at,
    )


@router.post("/live-report/run", response_model=RunReportResponse)
async def run_report(
    request: Request,
    bg: BackgroundTasks,
    starting_balance: Optional[float] = Query(None),
):
    """
    触发实盘报告生成
    - 若传 starting_balance，使用传入值
    - 若未传，自动从 bot 配置获取（dry_run_wallet 或实盘余额）
    """
    from freqtrade.rpc.api_server.dashboard_services import _resolve_starting_balance

    reporter = request.app.state.dashboard_reporter
    config = getattr(request.app.state, "ft_config", {}) or {}
    rpc = None
    try:
        from freqtrade.rpc.api_server.webserver import ApiServer
        rpc = getattr(ApiServer, "_rpc", None)
    except Exception:
        pass

    if starting_balance is None:
        try:
            starting_balance = _resolve_starting_balance(config, rpc)
        except Exception:
            starting_balance = 1000.0

    # 同步数据库路径
    reporter.db_path = request.app.state.dashboard_trade_service.db_path

    bg.add_task(reporter.run_analysis, starting_balance)
    return RunReportResponse(
        message="started",
        balance=starting_balance,
        db=str(reporter.db_path),
    )


# ============================================================================
# 回测对比（完整迁移自 scripts/dashboard/routers/analysis.py）
# ============================================================================

def _safe_num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


def _safe_str(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt_value = datetime.fromisoformat(text)
    except ValueError:
        dt_value = None
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                dt_value = datetime.strptime(str(value), pattern)
                break
            except ValueError:
                continue
        if dt_value is None:
            return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def _fmt_dt(value: Optional[datetime]) -> str:
    if not value:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _seconds_between(
    left: Optional[datetime], right: Optional[datetime]
) -> Optional[float]:
    if not left or not right:
        return None
    return (left - right).total_seconds()


def _signed_pct_diff(left: float, right: float) -> float:
    if not right:
        return 0.0
    return (left - right) / abs(right) * 100


def _trade_side(trade: Dict[str, Any]) -> str:
    return "short" if bool(trade.get("is_short")) else "long"


def _normalize_trade(
    trade: Dict[str, Any], source: str, index: int
) -> Dict[str, Any]:
    open_dt = _parse_dt(trade.get("open_date"))
    close_dt = _parse_dt(trade.get("close_date"))
    stake_amount = _safe_num(trade.get("stake_amount"))
    profit_pct = _safe_num(trade.get("profit_ratio")) * 100
    fee_open = _safe_num(trade.get("fee_open")) * stake_amount
    fee_close = _safe_num(trade.get("fee_close")) * max(
        stake_amount + _safe_num(trade.get("profit_abs")), 0
    )
    funding_fee = _safe_num(trade.get("funding_fees"))
    pair = _safe_str(trade.get("pair"))
    enter_tag = _safe_str(trade.get("enter_tag"), "unknown")
    exit_reason = _safe_str(trade.get("exit_reason"), "unknown")
    direction = _trade_side(trade)
    return {
        "source": source,
        "index": index,
        "id": f"{source}-{index}",
        "pair": pair,
        "side": direction,
        "enter_tag": enter_tag,
        "exit_reason": exit_reason,
        "open_dt": open_dt,
        "close_dt": close_dt,
        "open_ts": open_dt.timestamp() if open_dt else None,
        "close_ts": close_dt.timestamp() if close_dt else None,
        "entry_price": _safe_num(trade.get("open_rate")),
        "exit_price": _safe_num(trade.get("close_rate")),
        "stake_amount": stake_amount,
        "profit_pct": profit_pct,
        "profit_abs": _safe_num(trade.get("profit_abs")),
        "duration_min": _safe_num(trade.get("trade_duration")),
        "fees_abs": fee_open + fee_close,
        "funding_fee": funding_fee,
        "raw": trade,
    }


def _compare_value(
    label: str, live: float, bt: float, unit: str = "", digits: int = 2
) -> Dict[str, Any]:
    diff_pct = _signed_pct_diff(live, bt) if bt else 0.0
    return {
        "label": label,
        "live": round(live, digits),
        "bt": round(bt, digits),
        "unit": unit,
        "diff_pct": round(diff_pct, 1),
    }


def _closeness_score(delta_value: Optional[float], max_value: float) -> float:
    if delta_value is None:
        return 0.0
    return max(0.0, 1.0 - min(abs(delta_value), max_value) / max_value)


def _size_similarity(left: float, right: float) -> float:
    base = max(abs(left), abs(right), 1.0)
    return max(0.0, 1.0 - abs(left - right) / base)


def _match_score(
    bt_trade: Dict[str, Any], live_trade: Dict[str, Any]
) -> Tuple[float, Dict[str, float]]:
    if bt_trade["pair"] != live_trade["pair"]:
        return 0.0, {}
    if bt_trade["side"] != live_trade["side"]:
        return 0.0, {}

    open_delta_sec = _seconds_between(live_trade["open_dt"], bt_trade["open_dt"])
    size_score = _size_similarity(bt_trade["stake_amount"], live_trade["stake_amount"])
    tag_score = 1.0 if bt_trade["enter_tag"] == live_trade["enter_tag"] else 0.0
    close_delta_sec = _seconds_between(live_trade["close_dt"], bt_trade["close_dt"])
    duration_delta_min = live_trade["duration_min"] - bt_trade["duration_min"]

    components = {
        "pair": 1.0,
        "side": 1.0,
        "tag": tag_score,
        "time": _closeness_score(open_delta_sec, 10800),
        "close": _closeness_score(close_delta_sec, 21600),
        "size": size_score,
        "duration": _closeness_score(duration_delta_min, 720),
    }
    score = (
        components["pair"] * 0.20
        + components["side"] * 0.15
        + components["tag"] * 0.15
        + components["time"] * 0.25
        + components["close"] * 0.10
        + components["size"] * 0.10
        + components["duration"] * 0.05
    )
    return score, components


def _adverse_entry_slippage_pct(
    bt_trade: Dict[str, Any], live_trade: Dict[str, Any]
) -> float:
    bt_entry = bt_trade["entry_price"]
    live_entry = live_trade["entry_price"]
    if not bt_entry:
        return 0.0
    if bt_trade["side"] == "long":
        return (live_entry - bt_entry) / bt_entry * 100
    return (bt_entry - live_entry) / bt_entry * 100


def _adverse_exit_slippage_pct(
    bt_trade: Dict[str, Any], live_trade: Dict[str, Any]
) -> float:
    bt_exit = bt_trade["exit_price"]
    live_exit = live_trade["exit_price"]
    if not bt_exit:
        return 0.0
    if bt_trade["side"] == "long":
        return (bt_exit - live_exit) / bt_exit * 100
    return (live_exit - bt_exit) / bt_exit * 100


def _diagnose_bucket(match: Dict[str, Any]) -> str:
    if abs(match["entry_delay_sec"]) >= 600:
        return "入场延迟型"
    if match["entry_slippage_pct"] >= 0.3:
        return "入场滑点型"
    if match["exit_slippage_pct"] >= 0.3:
        return (
            "止损滑点型" if "stop" in match["live_exit_reason"].lower() else "出场滑点型"
        )
    if (
        abs(match["duration_diff_min"]) >= 120
        or match["bt_exit_reason"] != match["live_exit_reason"]
    ):
        return "持仓漂移型"
    return "轻微偏移型"


def _summarize_conclusion(
    contributions: List[Dict[str, Any]],
    matched_rate: float,
    bt_only_rate: float,
    live_only_rate: float,
) -> str:
    top_reasons = contributions[:3]
    if not top_reasons:
        return "当前只有汇总对比，没有足够的逐笔差异可供分析。"
    reason_text = "，".join(
        f"{item['label']} {item['share_pct']:.0f}%" for item in top_reasons
    )
    return (
        f"当前逐笔匹配率为 {matched_rate:.1f}%，"
        f"回测漏单率 {bt_only_rate:.1f}%，实盘额外单率 {live_only_rate:.1f}%。"
        f"收益偏差主要来自 {reason_text}。"
    )


def _build_compare_payload(
    live_report: Dict[str, Any], bt_report: Dict[str, Any]
) -> Dict[str, Any]:
    """完整迁移自 scripts/dashboard/routers/analysis.py"""
    live_trades = [
        _normalize_trade(trade, "live", index)
        for index, trade in enumerate(live_report.get("trades") or [])
        if not trade.get("is_open")
    ]
    bt_trades = [
        _normalize_trade(trade, "bt", index)
        for index, trade in enumerate(bt_report.get("trades") or [])
        if not trade.get("is_open")
    ]

    matched: List[Dict[str, Any]] = []
    used_live_ids: set = set()
    bt_only: List[Dict[str, Any]] = []

    for bt_trade in bt_trades:
        candidates: List[Tuple[float, Dict[str, float], Dict[str, Any]]] = []
        for live_trade in live_trades:
            if live_trade["id"] in used_live_ids:
                continue
            score, components = _match_score(bt_trade, live_trade)
            if score >= 0.60:
                candidates.append((score, components, live_trade))

        if not candidates:
            bt_only.append(bt_trade)
            continue

        score, components, live_trade = sorted(
            candidates, key=lambda item: item[0], reverse=True
        )[0]
        used_live_ids.add(live_trade["id"])

        entry_delay_sec = (
            _seconds_between(live_trade["open_dt"], bt_trade["open_dt"]) or 0.0
        )
        exit_delay_sec = (
            _seconds_between(live_trade["close_dt"], bt_trade["close_dt"]) or 0.0
        )
        duration_diff_min = live_trade["duration_min"] - bt_trade["duration_min"]
        entry_slippage_pct = _adverse_entry_slippage_pct(bt_trade, live_trade)
        exit_slippage_pct = _adverse_exit_slippage_pct(bt_trade, live_trade)
        fee_diff = live_trade["fees_abs"] - bt_trade["fees_abs"]
        funding_fee_diff = live_trade["funding_fee"] - bt_trade["funding_fee"]
        pnl_diff_pct = live_trade["profit_pct"] - bt_trade["profit_pct"]
        bucket = _diagnose_bucket(
            {
                "entry_delay_sec": entry_delay_sec,
                "entry_slippage_pct": entry_slippage_pct,
                "exit_slippage_pct": exit_slippage_pct,
                "duration_diff_min": duration_diff_min,
                "bt_exit_reason": bt_trade["exit_reason"],
                "live_exit_reason": live_trade["exit_reason"],
            }
        )

        matched.append(
            {
                "pair": bt_trade["pair"],
                "side": bt_trade["side"],
                "enter_tag": bt_trade["enter_tag"],
                "bt_entry_time": _fmt_dt(bt_trade["open_dt"]),
                "live_entry_time": _fmt_dt(live_trade["open_dt"]),
                "entry_delay_sec": round(entry_delay_sec, 1),
                "bt_entry_price": round(bt_trade["entry_price"], 8),
                "live_entry_price": round(live_trade["entry_price"], 8),
                "entry_slippage_pct": round(entry_slippage_pct, 4),
                "bt_exit_time": _fmt_dt(bt_trade["close_dt"]),
                "live_exit_time": _fmt_dt(live_trade["close_dt"]),
                "exit_delay_sec": round(exit_delay_sec, 1),
                "bt_exit_price": round(bt_trade["exit_price"], 8),
                "live_exit_price": round(live_trade["exit_price"], 8),
                "exit_slippage_pct": round(exit_slippage_pct, 4),
                "bt_duration": round(bt_trade["duration_min"], 1),
                "live_duration": round(live_trade["duration_min"], 1),
                "duration_diff_min": round(duration_diff_min, 1),
                "bt_exit_reason": bt_trade["exit_reason"],
                "live_exit_reason": live_trade["exit_reason"],
                "bt_profit_pct": round(bt_trade["profit_pct"], 4),
                "live_profit_pct": round(live_trade["profit_pct"], 4),
                "pnl_diff_pct": round(pnl_diff_pct, 4),
                "fee_diff": round(fee_diff, 6),
                "funding_fee_diff": round(funding_fee_diff, 6),
                "match_confidence": round(score * 100, 1),
                "match_components": components,
                "bucket": bucket,
            }
        )

    live_only = [
        trade for trade in live_trades if trade["id"] not in used_live_ids
    ]

    metrics = [
        _compare_value(
            "收益率",
            _safe_num(live_report.get("profit_total")) * 100,
            _safe_num(bt_report.get("profit_total")) * 100,
            "%",
        ),
        _compare_value(
            "夏普比率",
            _safe_num(live_report.get("sharpe")),
            _safe_num(bt_report.get("sharpe")),
        ),
        _compare_value(
            "索提诺比率",
            _safe_num(live_report.get("sortino")),
            _safe_num(bt_report.get("sortino")),
        ),
        _compare_value(
            "卡玛比率",
            _safe_num(live_report.get("calmar")),
            _safe_num(bt_report.get("calmar")),
        ),
        _compare_value(
            "获利因子",
            _safe_num(live_report.get("profit_factor")),
            _safe_num(bt_report.get("profit_factor")),
        ),
        _compare_value(
            "期望值",
            _safe_num(live_report.get("expectancy")) * 100,
            _safe_num(bt_report.get("expectancy")) * 100,
            "%",
        ),
        _compare_value(
            "最大回撤",
            _safe_num(live_report.get("max_drawdown_account")) * 100,
            _safe_num(bt_report.get("max_drawdown_account")) * 100,
            "%",
        ),
    ]

    matched_count = len(matched)
    bt_count = len(bt_trades)
    live_count = len(live_trades)
    matched_rate = matched_count / bt_count * 100 if bt_count else 0.0
    bt_only_rate = len(bt_only) / bt_count * 100 if bt_count else 0.0
    live_only_rate = len(live_only) / live_count * 100 if live_count else 0.0
    avg_entry_delay = (
        sum(abs(row["entry_delay_sec"]) for row in matched) / matched_count
        if matched_count
        else 0.0
    )
    avg_exit_delay = (
        sum(abs(row["exit_delay_sec"]) for row in matched) / matched_count
        if matched_count
        else 0.0
    )
    avg_entry_slippage = (
        sum(row["entry_slippage_pct"] for row in matched) / matched_count
        if matched_count
        else 0.0
    )
    avg_exit_slippage = (
        sum(row["exit_slippage_pct"] for row in matched) / matched_count
        if matched_count
        else 0.0
    )

    contribution_buckets = {
        "入场滑点": sum(
            max(0.0, row["entry_slippage_pct"]) for row in matched
        ),
        "出场滑点": sum(
            max(0.0, row["exit_slippage_pct"]) for row in matched
        ),
        "费用与资金费": sum(
            abs(row["fee_diff"]) + abs(row["funding_fee_diff"]) for row in matched
        ),
        "回测漏单": sum(abs(item["profit_pct"]) for item in bt_only),
        "实盘额外单": sum(abs(item["profit_pct"]) for item in live_only),
        "持仓/时机偏差": sum(
            max(
                0.0,
                abs(row["pnl_diff_pct"])
                - max(0.0, row["entry_slippage_pct"])
                - max(0.0, row["exit_slippage_pct"]),
            )
            for row in matched
        ),
    }
    total_contribution = sum(contribution_buckets.values()) or 1.0
    contributions = [
        {
            "label": label,
            "value": round(value, 4),
            "share_pct": round(value / total_contribution * 100, 1),
        }
        for label, value in sorted(
            contribution_buckets.items(), key=lambda item: item[1], reverse=True
        )
        if value > 0
    ]

    cluster_map: Dict[str, Dict[str, Any]] = {}
    for row in matched:
        bucket = row["bucket"]
        entry = cluster_map.setdefault(
            bucket,
            {
                "label": bucket,
                "count": 0,
                "avg_entry_delay_sec": 0.0,
                "avg_exit_delay_sec": 0.0,
                "avg_entry_slippage_pct": 0.0,
                "avg_exit_slippage_pct": 0.0,
                "avg_pnl_diff_pct": 0.0,
            },
        )
        entry["count"] += 1
        entry["avg_entry_delay_sec"] += abs(row["entry_delay_sec"])
        entry["avg_exit_delay_sec"] += abs(row["exit_delay_sec"])
        entry["avg_entry_slippage_pct"] += row["entry_slippage_pct"]
        entry["avg_exit_slippage_pct"] += row["exit_slippage_pct"]
        entry["avg_pnl_diff_pct"] += row["pnl_diff_pct"]

    clusters = []
    for bucket, entry in cluster_map.items():
        count = entry["count"] or 1
        clusters.append(
            {
                "label": bucket,
                "count": entry["count"],
                "avg_entry_delay_sec": round(entry["avg_entry_delay_sec"] / count, 1),
                "avg_exit_delay_sec": round(entry["avg_exit_delay_sec"] / count, 1),
                "avg_entry_slippage_pct": round(
                    entry["avg_entry_slippage_pct"] / count, 4
                ),
                "avg_exit_slippage_pct": round(
                    entry["avg_exit_slippage_pct"] / count, 4
                ),
                "avg_pnl_diff_pct": round(entry["avg_pnl_diff_pct"] / count, 4),
            }
        )
    clusters.sort(key=lambda item: item["count"], reverse=True)

    top_anomalies = sorted(
        matched, key=lambda item: abs(item["pnl_diff_pct"]), reverse=True
    )[:20]

    def _brief_unmatched(trade: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pair": trade["pair"],
            "side": trade["side"],
            "enter_tag": trade["enter_tag"],
            "entry_time": _fmt_dt(trade["open_dt"]),
            "exit_time": _fmt_dt(trade["close_dt"]),
            "exit_reason": trade["exit_reason"],
            "profit_pct": round(trade["profit_pct"], 4),
            "stake_amount": round(trade["stake_amount"], 4),
        }

    overview_cards = [
        {"label": "匹配率", "value": round(matched_rate, 1), "unit": "%"},
        {"label": "回测漏单率", "value": round(bt_only_rate, 1), "unit": "%"},
        {"label": "实盘额外单率", "value": round(live_only_rate, 1), "unit": "%"},
        {"label": "平均入场延迟", "value": round(avg_entry_delay, 1), "unit": "s"},
        {"label": "平均出场延迟", "value": round(avg_exit_delay, 1), "unit": "s"},
        {"label": "平均入场滑点", "value": round(avg_entry_slippage, 4), "unit": "%"},
        {"label": "平均出场滑点", "value": round(avg_exit_slippage, 4), "unit": "%"},
        {"label": "已匹配交易", "value": matched_count, "unit": "笔"},
    ]

    score = max(
        0.0,
        min(
            100.0,
            matched_rate
            - bt_only_rate * 0.6
            - live_only_rate * 0.5
            - max(0.0, avg_entry_slippage) * 12
            - max(0.0, avg_exit_slippage) * 12,
        ),
    )

    return {
        "ready": True,
        "overview": {
            "metrics": metrics,
            "cards": overview_cards,
            "matched_count": matched_count,
            "bt_trade_count": bt_count,
            "live_trade_count": live_count,
        },
        "diagnosis": {
            "score": round(score, 1),
            "conclusion": _summarize_conclusion(
                contributions, matched_rate, bt_only_rate, live_only_rate
            ),
            "limitations": "当前归因基于成交结果做准归因；由于缺少信号生成时间、下单发送时间和成交确认时间，还不能做执行链路级强归因。",
        },
        "attribution": {
            "contributions": contributions,
            "clusters": clusters,
        },
        "matching": {
            "matched": matched,
            "bt_only": [_brief_unmatched(item) for item in bt_only[:50]],
            "live_only": [_brief_unmatched(item) for item in live_only[:50]],
            "top_anomalies": top_anomalies,
        },
    }


@router.post("/backtest/compare")
async def compare_backtest(
    request: Request,
    live_file: UploadFile = File(...),
    bt_file: UploadFile = File(...),
):
    """
    上传实盘报告 JSON 和回测结果 JSON，进行逐笔对比分析
    完整迁移自 scripts/dashboard/routers/analysis.py 的 _build_compare_payload
    """
    try:
        live_content = await live_file.read()
        live_report = json.loads(live_content)

        bt_content = await bt_file.read()
        if bt_file.filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(bt_content)) as archive:
                result_files = [
                    item
                    for item in archive.namelist()
                    if item.startswith("backtest-result-")
                    and item.endswith(".json")
                    and not item.endswith("_config.json")
                ]
                if not result_files:
                    raise HTTPException(
                        status_code=400,
                        detail="No backtest-result JSON found in zip",
                    )
                with archive.open(result_files[0]) as payload:
                    bt_data = json.load(payload)
            strategy_name = list(bt_data["strategy"].keys())[0]
            bt_report = bt_data["strategy"][strategy_name]
        else:
            bt_report = json.loads(bt_content)

        return _build_compare_payload(live_report, bt_report)
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ============================================================================
# Bot 信息
# ============================================================================


@router.get("/config/bot-info", response_model=BotInfo)
async def bot_info(request: Request):
    """获取 bot 自动检测信息"""
    from freqtrade.rpc.api_server.dashboard_services import _resolve_starting_balance

    config = getattr(request.app.state, "ft_config", {}) or {}
    rpc = None
    try:
        from freqtrade.rpc.api_server.webserver import ApiServer
        rpc = getattr(ApiServer, "_rpc", None)
    except Exception:
        pass

    try:
        starting_balance = _resolve_starting_balance(config, rpc)
    except Exception:
        starting_balance = 1000.0

    db_path = ""
    db_exists = False
    db_total_trades = 0
    db_closed_trades = 0
    try:
        svc = getattr(request.app.state, "dashboard_trade_service", None)
        if svc:
            db_path = str(svc.db_path)
            db_exists = svc.db_path.exists()
            if db_exists:
                import sqlite3
                conn = sqlite3.connect(str(svc.db_path))
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM trades")
                db_total_trades = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM trades WHERE is_open=0")
                db_closed_trades = c.fetchone()[0]
                conn.close()
    except Exception:
        pass

    info = BotInfo(
        exchange=config.get("exchange", "unknown"),
        stake_currency=config.get("stake_currency", "USDT"),
        trading_mode=config.get("trading_mode", "spot"),
        run_mode=config.get("runmode", "unknown"),
        db_path=db_path,
        starting_balance=starting_balance,
        dry_run=config.get("dry_run", True),
        db_exists=db_exists,
        db_total_trades=db_total_trades,
        db_closed_trades=db_closed_trades,
    )

    if rpc:
        try:
            balance = rpc._rpc_balance()
            info.current_balance = balance.get("total", 0)
        except Exception:
            pass

    return info
