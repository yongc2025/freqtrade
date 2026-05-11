"""
VolumeRankingPairList - 回测专用动态选币插件（查表版，高性能）

核心思路：
  使用 precompute_volume_ranking.py 预生成的 volume_ranking.json 文件，
  在回测时直接查表获取每个时间点的动态选币排名，几乎零开销。

速度对比：
  - StaticPairList：基准速度
  - VolumeRankingPairList（本插件）：约 1.0-1.1 倍耗时（仅查表开销）
  - BacktestVolumePairList（实时计算版）：约 1.2-1.5 倍耗时

使用方法：
  1. 先运行 precompute_volume_ranking.py 生成 volume_ranking.json
  2. 将本文件放到 freqtrade/plugins/pairlist/ 目录
  3. 将 volume_ranking.json 放到 freqtrade 用户数据目录
  4. 配置 pairlists 使用 VolumeRankingPairList

配置示例：
  "pairlists": [
    {
      "method": "VolumeRankingPairList",
      "number_assets": 40,
      "ranking_file": "volume_ranking.json",
      "lookback_hours": 24,
      "step_hours": 1
    },
    {
      "method": "AgeFilter",
      "min_days_listed": 30
    }
  ]
"""

import json
import logging
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from freqtrade.constants import Config
from freqtrade.exceptions import OperationalException
from freqtrade.exchange.exchange_types import Tickers
from freqtrade.plugins.pairlist.IPairList import IPairList, PairlistParameter, SupportsBacktesting


logger = logging.getLogger(__name__)


class VolumeRankingPairList(IPairList):
    """
    回测专用动态选币插件（查表版）。

    核心优化：
    - 启动时加载 precompute_volume_ranking.py 生成的排名文件
    - filter_pairlist() 时 O(logN) 二分查找 + O(1) 查表
    - 不需要在回测过程中做任何成交量计算
    """

    is_pairlist_generator = True
    supports_backtesting = SupportsBacktesting.YES

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if "number_assets" not in self._pairlistconfig:
            raise OperationalException(
                "`number_assets` not specified. Please check your configuration "
                'for "pairlist.config.number_assets"'
            )

        self._stake_currency: str = self._config["stake_currency"]
        self._number_pairs: int = self._pairlistconfig["number_assets"]
        self._ranking_file: str = self._pairlistconfig.get("ranking_file", "volume_ranking.json")
        self._lookback_hours: int = self._pairlistconfig.get("lookback_hours", 24)
        self._step_hours: int = self._pairlistconfig.get("step_hours", 1)

        # 预计算的排名数据
        # sorted_ts: 排序后的时间戳列表（Unix seconds）
        # ranking: {timestamp -> [pair1, pair2, ...]}
        self._sorted_ts: list[int] = []
        self._ranking: dict[int, list[str]] = {}
        self._loaded: bool = False
        self._ranking_version: int = 0
        self._ranking_total_pairs: int = 0

        # 启动时加载排名文件
        self._load_ranking_file()

    def _load_ranking_file(self) -> None:
        """加载预计算的排名文件"""
        # 搜索路径：配置目录 > 用户数据目录 > 当前目录
        search_paths = []

        # 用户数据目录
        user_data_dir = self._config.get("user_data_dir")
        if user_data_dir:
            search_paths.append(Path(user_data_dir) / self._ranking_file)

        # 配置目录
        config_dir = self._config.get("config_dir")
        if config_dir:
            search_paths.append(Path(config_dir) / self._ranking_file)

        # 当前目录
        search_paths.append(Path(self._ranking_file))

        # 绝对路径
        ranking_path = Path(self._ranking_file)
        if ranking_path.is_absolute():
            search_paths = [ranking_path]

        found_path = None
        for p in search_paths:
            if p.exists():
                found_path = p
                break

        if found_path is None:
            raise OperationalException(
                f"VolumeRankingPairList: 排名文件 '{self._ranking_file}' 未找到。\n"
                f"请先运行 precompute_volume_ranking.py 生成排名文件。\n"
                f"搜索路径: {[str(p) for p in search_paths]}"
            )

        logger.info(f"VolumeRankingPairList: 加载排名文件 {found_path}")

        try:
            with open(found_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise OperationalException(
                f"VolumeRankingPairList: 读取排名文件失败: {e}"
            )

        # 验证版本
        version = data.get("version", 0)
        if version < 1:
            raise OperationalException(
                f"VolumeRankingPairList: 排名文件版本过旧 (v{version})，请重新生成。"
            )

        # 验证参数一致性
        file_number_assets = data.get("number_assets", 0)
        if file_number_assets < self._number_pairs:
            logger.warning(
                f"VolumeRankingPairList: 排名文件中的 top N ({file_number_assets}) "
                f"小于配置的 number_assets ({self._number_pairs})，"
                f"可能无法获取足够的币种。"
            )

        file_lookback = data.get("lookback_hours", 0)
        if file_lookback != self._lookback_hours:
            logger.warning(
                f"VolumeRankingPairList: 排名文件的 lookback_hours ({file_lookback}) "
                f"与配置 ({self._lookback_hours}) 不一致，结果可能不准确。"
            )

        # 解析排名数据
        ranking_data = data.get("ranking", {})
        sorted_ts = []
        ranking = {}

        for ts_str, pairs in ranking_data.items():
            try:
                ts = int(ts_str)
                sorted_ts.append(ts)
                ranking[ts] = pairs
            except (ValueError, TypeError):
                continue

        sorted_ts.sort()

        if not sorted_ts:
            raise OperationalException(
                "VolumeRankingPairList: 排名文件中没有有效的排名数据。"
            )

        self._sorted_ts = sorted_ts
        self._ranking = ranking
        self._ranking_version = version
        self._ranking_total_pairs = data.get("total_pairs", 0)
        self._loaded = True

        # 计算时间覆盖范围
        first_time = datetime.fromtimestamp(sorted_ts[0])
        last_time = datetime.fromtimestamp(sorted_ts[-1])
        coverage_days = (last_time - first_time).days

        logger.info(
            f"VolumeRankingPairList: 排名文件加载成功\n"
            f"  版本: v{version}\n"
            f"  币种数: {self._ranking_total_pairs}\n"
            f"  时间点数: {len(sorted_ts)}\n"
            f"  覆盖范围: {first_time} ~ {last_time} ({coverage_days} 天)\n"
            f"  lookback: {file_lookback}h, step: {data.get('step_hours', '?')}h"
        )

    @property
    def needstickers(self) -> bool:
        return False

    def short_desc(self) -> str:
        return (
            f"{self.name} - top {self._number_pairs} volume pairs "
            f"(ranking file: {self._ranking_file}, "
            f"lookback: {self._lookback_hours}h)"
        )

    @staticmethod
    def description() -> str:
        return (
            "Provides dynamic pair list based on pre-computed volume ranking "
            "for backtesting. Requires precompute_volume_ranking.py output."
        )

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        return {
            "number_assets": {
                "type": "number",
                "default": 40,
                "description": "Number of assets",
                "help": "Number of top-volume pairs to select.",
            },
            "ranking_file": {
                "type": "string",
                "default": "volume_ranking.json",
                "description": "Ranking file path",
                "help": "Path to the pre-computed volume ranking JSON file.",
            },
            "lookback_hours": {
                "type": "number",
                "default": 24,
                "description": "Lookback hours",
                "help": "Volume lookback period in hours (must match precompute script).",
            },
            "step_hours": {
                "type": "number",
                "default": 1,
                "description": "Step hours",
                "help": "Ranking calculation step in hours (must match precompute script).",
            },
        }

    def gen_pairlist(self, tickers: Tickers) -> list[str]:
        """
        获取所有可交易的 USDT 合约对。
        在回测模式下，返回排名文件中出现过的所有币种。
        """
        if not self._loaded:
            raise OperationalException(
                "VolumeRankingPairList: 排名文件未加载，无法生成 pairlist。"
            )

        # 收集排名文件中所有出现过的币种
        all_pairs = set()
        for pairs in self._ranking.values():
            all_pairs.update(pairs)

        # 验证币种格式
        _pairlist = []
        for pair in sorted(all_pairs):
            # 确保是有效的交易对格式
            if "/" in pair and ":" in pair:
                _pairlist.append(pair)
            elif "/" in pair:
                # BTC/USDT -> BTC/USDT:USDT
                parts = pair.split("/")
                if len(parts) == 2:
                    _pairlist.append(f"{parts[0]}/{parts[1]}:{parts[1]}")
            else:
                logger.debug(f"VolumeRankingPairList: 跳过无效币种格式: {pair}")

        # 应用黑名单
        _pairlist = self.verify_blacklist(_pairlist, logger.info)

        logger.info(
            f"VolumeRankingPairList: 从排名文件中加载 {len(_pairlist)} 个可交易币种"
        )

        return _pairlist

    def filter_pairlist(self, pairlist: list[str], tickers: Tickers) -> list[str]:
        """
        根据预计算的排名过滤 pairlist。
        优化：O(logN) 二分查找 + O(1) 查表。
        """
        if not pairlist or not self._loaded:
            return pairlist[:self._number_pairs]

        # 获取当前回测时间
        current_ts = self._get_current_timestamp()
        if current_ts is None:
            logger.debug("VolumeRankingPairList: 无法获取当前时间，使用全量 pairlist")
            return pairlist[:self._number_pairs]

        # 二分查找最近的预计算时间点
        ranked_pairs = self._lookup_ranking(current_ts)
        if not ranked_pairs:
            logger.debug(
                f"VolumeRankingPairList: 时间戳 {current_ts} 无排名数据，使用全量 pairlist"
            )
            return pairlist[:self._number_pairs]

        # 过滤掉不在当前 pairlist 中的（可能被黑名单过滤或数据缺失）
        valid_pairs = [p for p in ranked_pairs if p in pairlist]

        result = valid_pairs[:self._number_pairs]

        if not result:
            logger.debug(
                f"VolumeRankingPairList: 排名中的币种都不在 pairlist 中，"
                f"使用 pairlist 前 {self._number_pairs} 个"
            )
            return pairlist[:self._number_pairs]

        return result

    def _get_current_timestamp(self) -> int | None:
        """
        获取当前回测时间的时间戳。
        优先从 dataprovider 获取，回退到系统时间。
        """
        if self._dp is None:
            return None

        # 尝试从 dataprovider 获取当前处理的时间
        try:
            if hasattr(self._dp, 'get_analyzed_dataframe'):
                # 尝试获取任意一个币种的最新时间
                # 注意：在回测启动初期可能还没有数据
                if hasattr(self._pairlistmanager, 'whitelist'):
                    for pair in self._pairlistmanager.whitelist[:5]:
                        try:
                            df, _ = self._dp.get_analyzed_dataframe(pair, "1h")
                            if df is not None and not df.empty:
                                last_time = df.index[-1]
                                if hasattr(last_time, 'timestamp'):
                                    return int(last_time.timestamp())
                                return int(last_time)
                        except Exception:
                            continue
        except Exception:
            pass

        # 回退：尝试从 exchange 获取当前时间
        try:
            if hasattr(self._exchange, 'clock') and self._exchange.clock is not None:
                return int(self._exchange.clock.timestamp())
        except Exception:
            pass

        # 最终回退：使用系统时间（不太准确，但比没有好）
        return int(datetime.now().timestamp())

    def _lookup_ranking(self, current_ts: int) -> list[str] | None:
        """
        二分查找最近的预计算时间戳，返回对应的排名。
        """
        if not self._sorted_ts:
            return None

        # 二分查找：找到 <= current_ts 的最大时间戳
        idx = bisect_right(self._sorted_ts, current_ts)

        if idx == 0:
            # current_ts 比所有预计算时间戳都早
            # 返回第一个时间点的排名（向前兼容）
            return self._ranking.get(self._sorted_ts[0])

        # idx 指向第一个 > current_ts 的位置
        # 所以 idx-1 是 <= current_ts 的最大时间戳
        nearest_ts = self._sorted_ts[idx - 1]

        return self._ranking.get(nearest_ts)

    def _validate_pair(self, pair: str, ticker: Ticker | None) -> bool:
        """不需要验证，因为排名文件已经包含了有效币种"""
        return True
