"""
GMGN PairList Provider

Provides dynamic pair list based on GMGN on-chain data:
- Trending tokens from GMGN market
- Smart money tracked tokens from GMGN track
- Safety filtering via GMGN token security
"""

import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from freqtrade.exceptions import OperationalException
from freqtrade.exchange.exchange_types import Tickers
from freqtrade.plugins.pairlist.IPairList import (
    IPairList,
    PairlistParameter,
    SupportsBacktesting,
)


logger = logging.getLogger(__name__)


class GMGNPairList(IPairList):
    """
    GMGN 动态选币插件

    从 GMGN 获取热门代币 + 聪明钱动向，经过安全过滤后返回高质量交易对。
    调用 gmgn-cli 获取数据，支持 Solana/BSC/Base/Eth 链。
    """

    is_pairlist_generator = True
    supports_backtesting = SupportsBacktesting.NO

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if "number_assets" not in self._pairlistconfig:
            raise OperationalException(
                "`number_assets` not specified. Please check your configuration "
                'for "pairlist.config.number_assets"'
            )

        self._number_pairs: int = self._pairlistconfig["number_assets"]
        self._chain: str = self._pairlistconfig.get("chain", "sol")
        self._stake_currency: str = self._config.get("stake_currency", "USDT")
        self._trending_limit: int = self._pairlistconfig.get("trending_limit", 30)
        self._smartmoney_limit: int = self._pairlistconfig.get("smartmoney_limit", 20)
        self._max_workers: int = self._pairlistconfig.get("max_workers", 3)
        self._gmgn_cli: str = self._pairlistconfig.get("gmgn_cli", "gmgn-cli")

        # 安全过滤阈值
        self._max_rug_ratio: float = self._pairlistconfig.get("max_rug_ratio", 0.3)
        self._max_bundler_rate: float = self._pairlistconfig.get("max_bundler_rate", 0.2)
        self._max_rat_trader_rate: float = self._pairlistconfig.get("max_rat_trader_rate", 0.15)
        self._min_liquidity: float = self._pairlistconfig.get("min_liquidity", 50000)

        # 缓存
        self._cache: dict[str, Any] = {}
        self._cache_ttl: int = self._pairlistconfig.get("refresh_period", 3600)

        # 代币地址缓存（symbol → address），写入文件供策略使用
        self._address_cache_path: str = self._pairlistconfig.get(
            "address_cache_path", "user_data/gmgn_address_cache.json"
        )
        self._address_cache: dict[str, str] = self._load_address_cache()

        # 安全数据缓存（address → security data），写入文件供策略使用
        self._security_cache_path: str = self._pairlistconfig.get(
            "security_cache_path", "user_data/gmgn_security_cache.json"
        )

    @property
    def needstickers(self) -> bool:
        return False

    @staticmethod
    def description() -> str:
        return "Provides dynamic pair list based on GMGN on-chain data (trending + smart money)."

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        return {
            "number_assets": {
                "type": "number",
                "default": 20,
                "description": "Number of assets",
                "help": "Maximum number of pairs to return",
            },
            "chain": {
                "type": "option",
                "default": "sol",
                "options": ["sol", "bsc", "base", "eth"],
                "description": "Blockchain network",
                "help": "Which chain to scan for tokens",
            },
            "trending_limit": {
                "type": "number",
                "default": 30,
                "description": "Trending limit",
                "help": "Number of trending tokens to fetch from GMGN",
            },
            "smartmoney_limit": {
                "type": "number",
                "default": 20,
                "description": "Smart money limit",
                "help": "Number of smart money tokens to fetch from GMGN",
            },
            "max_workers": {
                "type": "number",
                "default": 10,
                "description": "Max concurrent workers",
                "help": "Max concurrent gmgn-cli calls for security checks",
            },
            "max_rug_ratio": {
                "type": "number",
                "default": 0.3,
                "description": "Max rug ratio",
                "help": "Maximum rug pull risk score (0-1) to pass safety filter",
            },
            "max_bundler_rate": {
                "type": "number",
                "default": 0.2,
                "description": "Max bundler rate",
                "help": "Maximum bundle bot trading ratio (0-1)",
            },
            "max_rat_trader_rate": {
                "type": "number",
                "default": 0.15,
                "description": "Max rat trader rate",
                "help": "Maximum insider/sneak trading ratio (0-1)",
            },
            "min_liquidity": {
                "type": "number",
                "default": 50000,
                "description": "Minimum liquidity (USD)",
                "help": "Minimum liquidity in USD to pass safety filter",
            },
            **IPairList.refresh_period_parameter(),
        }

    def short_desc(self) -> str:
        return (
            f"{self.name} - top {self._number_pairs} pairs from GMGN "
            f"(chain={self._chain}, trending={self._trending_limit}, "
            f"smartmoney={self._smartmoney_limit})"
        )

    def gen_pairlist(self, tickers: Tickers) -> list[str]:
        """
        生成交易对列表

        流程:
        1. 从 GMGN 获取热门代币 (market trending)
        2. 从 GMGN 获取聪明钱动向 (track smartmoney)
        3. 合并去重
        4. 并发安全过滤 (token security)
        5. 返回干净的交易对列表
        """
        cache_key = "pairlist"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached.copy()

        # Step 1 & 2: 并发获取 trending + smartmoney
        trending_tokens, smartmoney_tokens = self._fetch_discovery_data()

        # Step 3: 合并去重
        candidates = self._merge_and_dedupe(trending_tokens, smartmoney_tokens)

        if not candidates:
            logger.warning("GMGNPairList: No candidates found from GMGN")
            return []

        logger.info(f"GMGNPairList: {len(candidates)} candidates after merge")

        # Step 4: 并发安全过滤
        safe_tokens = self._safety_filter(candidates)

        logger.info(f"GMGNPairList: {len(safe_tokens)} tokens passed safety filter")

        # Step 5: 转换为交易对格式并限制数量
        pairs = self._build_pairs(safe_tokens)
        pairs = pairs[: self._number_pairs]

        # 缓存结果
        self._set_cache(cache_key, pairs)

        # 保存地址缓存到文件（供策略使用）
        if self._address_cache:
            self._save_address_cache()
            logger.info(f"GMGNPairList: Saved {len(self._address_cache)} address mappings")

        return pairs.copy()

    def _fetch_discovery_data(self) -> tuple[list[dict], list[dict]]:
        """并发获取 trending 和 smartmoney 数据"""
        trending_tokens: list[dict] = []
        smartmoney_tokens: list[dict] = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_trending = executor.submit(self._fetch_trending)
            future_smartmoney = executor.submit(self._fetch_smartmoney)

            try:
                trending_tokens = future_trending.result(timeout=15)
            except Exception as e:
                logger.error(f"GMGNPairList: Failed to fetch trending: {e}")

            try:
                smartmoney_tokens = future_smartmoney.result(timeout=15)
            except Exception as e:
                logger.error(f"GMGNPairList: Failed to fetch smartmoney: {e}")

        return trending_tokens, smartmoney_tokens

    def _fetch_trending(self) -> list[dict]:
        """获取热门代币"""
        result = self._call_gmgn(
            "market", "trending",
            "--chain", self._chain,
            "--interval", "1h",
            "--limit", str(self._trending_limit),
            "--raw",
        )
        if not result:
            return []

        data = result.get("data", {})
        rank_list = data.get("rank", [])
        return [self._extract_token_info(t) for t in rank_list if t.get("address")]

    def _fetch_smartmoney(self) -> list[dict]:
        """获取聪明钱最近在买的代币"""
        result = self._call_gmgn(
            "track", "smartmoney",
            "--chain", self._chain,
            "--limit", str(self._smartmoney_limit),
            "--raw",
        )
        if not result:
            return []

        data = result.get("data", {})
        trades = data.get("trades", data.get("list", []))

        # 从聪明钱交易中提取唯一的代币
        seen = set()
        tokens = []
        for trade in trades:
            base_addr = trade.get("base_address", "")
            base_symbol = trade.get("base_symbol", "").upper().strip()
            if base_addr and base_addr not in seen:
                seen.add(base_addr)

                # 缓存 symbol → address 映射
                if base_symbol and base_addr:
                    self._address_cache[base_symbol] = base_addr

                tokens.append({
                    "address": base_addr,
                    "symbol": base_symbol,
                    "name": trade.get("base_name", ""),
                    "smart_degen_count": 1,
                    "source": "smartmoney",
                })

        return tokens

    def _extract_token_info(self, token: dict) -> dict:
        """从 trending 响应中提取标准化的代币信息，并缓存地址映射"""
        symbol = token.get("symbol", "").upper().strip()
        address = token.get("address", "")

        # 缓存 symbol → address 映射
        if symbol and address:
            self._address_cache[symbol] = address

        return {
            "address": address,
            "symbol": symbol,
            "name": token.get("name", ""),
            "price": token.get("price"),
            "market_cap": token.get("market_cap"),
            "liquidity": token.get("liquidity"),
            "volume": token.get("volume"),
            "smart_degen_count": token.get("smart_degen_count", 0),
            "renowned_count": token.get("renowned_count", 0),
            "rug_ratio": token.get("rug_ratio"),
            "is_wash_trading": token.get("is_wash_trading"),
            "sniper_count": token.get("sniper_count"),
            "source": "trending",
        }

    def _merge_and_dedupe(
        self, trending: list[dict], smartmoney: list[dict]
    ) -> list[dict]:
        """合并并去重，优先保留信息更丰富的记录"""
        merged: dict[str, dict] = {}

        # trending 先进（信息更丰富）
        for t in trending:
            addr = t.get("address", "")
            if addr:
                merged[addr] = t

        # smartmoney 补充（如果 trending 没有，或补充 smart_degen_count）
        for t in smartmoney:
            addr = t.get("address", "")
            if not addr:
                continue
            if addr in merged:
                # 合并 smart_degen_count
                existing_count = merged[addr].get("smart_degen_count", 0)
                new_count = t.get("smart_degen_count", 0)
                merged[addr]["smart_degen_count"] = max(existing_count, new_count)
            else:
                merged[addr] = t

        return list(merged.values())

    def _safety_filter(self, candidates: list[dict]) -> list[dict]:
        """
        并发安全过滤

        对每个候选代币调用 gmgn-cli token security 检查安全性。
        已有足够信息（来自 trending）的代币直接用本地数据过滤，
        只对信息不足的代币发起 API 调用。
        """
        safe: list[dict] = []
        need_api_check: list[dict] = []

        # 第一轮：本地快速过滤（trending 数据已经包含部分安全字段）
        for token in candidates:
            if self._quick_local_filter(token):
                # 有足够信息做判断的，直接通过
                safe.append(token)
            else:
                # 需要查 API 的
                need_api_check.append(token)

        if not need_api_check:
            return safe

        # token security API 不稳定，跳过 API 检查
        # 策略层 populate_indicators() 会独立做安全检查
        logger.info(
            f"GMGNPairList: {len(need_api_check)} tokens skipped API check "
            f"(strategy will verify security)"
        )
        safe.extend(need_api_check)

        return safe

    def _quick_local_filter(self, token: dict) -> bool:
        """
        基于已有数据的快速本地过滤

        如果 trending 返回的数据已经包含安全字段，直接用本地判断。
        返回 True 表示通过过滤（或需要进一步 API 检查），False 表示直接淘汰。
        """
        rug_ratio = token.get("rug_ratio")
        is_wash_trading = token.get("is_wash_trading")
        liquidity = token.get("liquidity")

        # rug_ratio 有值就能本地判断，不需要 API
        if rug_ratio is None:
            return False  # 缺 rug_ratio，需要 API 补查

        # 快速淘汰
        if is_wash_trading is True or is_wash_trading == "true":
            return False
        if rug_ratio > self._max_rug_ratio:
            return False
        if liquidity is not None and liquidity < self._min_liquidity:
            return False

        return True  # rug_ratio 正常 + 流动性够 → 直接通过，无需 API

    def _check_token_security(self, token: dict) -> dict | None:
        """
        调用 gmgn-cli token security 检查代币安全性

        通过安全检查返回代币信息，否则返回 None。
        """
        address = token.get("address", "")
        if not address:
            return None

        result = self._call_gmgn(
            "token", "security",
            "--chain", self._chain,
            "--address", address,
            "--raw",
        )

        if not result:
            return None

        data = result.get("data", result)

        # 安全检查
        rug_ratio = data.get("rug_ratio", 1)
        if isinstance(rug_ratio, str):
            try:
                rug_ratio = float(rug_ratio)
            except ValueError:
                rug_ratio = 1

        if rug_ratio > self._max_rug_ratio:
            logger.debug(f"GMGNPairList: {token.get('symbol')} rejected: rug_ratio={rug_ratio}")
            return None

        # 貔貅检测（EVM 链）
        is_honeypot = data.get("is_honeypot", False)
        if is_honeypot and is_honeypot not in (False, "false", "no", 0, ""):
            logger.debug(f"GMGNPairList: {token.get('symbol')} rejected: honeypot")
            return None

        # bundler 检测
        bundler_rate = data.get("bundler_trader_amount_rate", 0)
        if isinstance(bundler_rate, str):
            try:
                bundler_rate = float(bundler_rate)
            except ValueError:
                bundler_rate = 0
        if bundler_rate > self._max_bundler_rate:
            logger.debug(f"GMGNPairList: {token.get('symbol')} rejected: bundler_rate={bundler_rate}")
            return None

        # 老鼠仓检测
        rat_rate = data.get("rat_trader_amount_rate", 0)
        if isinstance(rat_rate, str):
            try:
                rat_rate = float(rat_rate)
            except ValueError:
                rat_rate = 0
        if rat_rate > self._max_rat_trader_rate:
            logger.debug(f"GMGNPairList: {token.get('symbol')} rejected: rat_trader_rate={rat_rate}")
            return None

        # 流动性检测
        liquidity = data.get("liquidity")
        if liquidity is not None:
            if isinstance(liquidity, str):
                try:
                    liquidity = float(liquidity)
                except ValueError:
                    liquidity = None
            if liquidity is not None and liquidity < self._min_liquidity:
                logger.debug(f"GMGNPairList: {token.get('symbol')} rejected: liquidity={liquidity}")
                return None

        # 更新代币信息
        token["rug_ratio"] = rug_ratio
        token["bundler_rate"] = bundler_rate
        token["rat_trader_rate"] = rat_rate
        token["security_checked"] = True

        logger.info(
            f"GMGNPairList: ✅ {token.get('symbol')} passed safety check "
            f"(rug={rug_ratio:.2f}, bundler={bundler_rate:.2f}, rat={rat_rate:.2f})"
        )

        # 缓存安全数据到文件，供策略复用
        self._save_security_cache(address, {
            "rug_ratio": rug_ratio,
            "is_honeypot": 1 if is_honeypot not in (False, "false", "no", 0, "") else 0,
            "bundler_rate": bundler_rate,
            "rat_trader_rate": rat_rate,
            "liquidity": liquidity,
            "smart_degen_count": token.get("smart_degen_count", 0),
            "renowned_count": token.get("renowned_count", 0),
            "sniper_count": token.get("sniper_count", 0),
        })

        return token

    def _build_pairs(self, tokens: list[dict]) -> list[str]:
        """将通过过滤的代币转换为 Freqtrade 交易对格式，并验证交易所是否有该交易对"""
        pairs = []
        seen = set()

        # 获取交易所可用市场（用于验证）
        try:
            markets = self._exchange.markets
            available_symbols = set(markets.keys()) if markets else set()
        except Exception:
            available_symbols = set()

        trading_mode = self._config.get("trading_mode", "spot")

        for token in tokens:
            symbol = token.get("symbol", "").upper().strip()
            if not symbol or symbol in seen:
                continue

            # 跳过稳定币
            if symbol in ("USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD"):
                continue

            # 根据交易模式生成交易对格式
            if trading_mode == "futures":
                pair = f"{symbol}/{self._stake_currency}:{self._stake_currency}"
            else:
                pair = f"{symbol}/{self._stake_currency}"

            if pair in seen:
                continue

            # 验证交易所是否有该交易对
            if available_symbols and pair not in available_symbols:
                logger.debug(f"GMGNPairList: {pair} not available on exchange, skipping")
                continue

            seen.add(pair)
            pairs.append(pair)

        return pairs

    def _get_proxy_env(self) -> dict[str, str]:
        """
        从 ccxt_config 中提取代理设置，构建子进程可用的环境变量。

        gmgn-cli 通过 subprocess 调用，不会读取 ccxt 的代理配置。
        需要将代理转为 HTTP_PROXY/HTTPS_PROXY 环境变量传递给子进程。
        """
        env = {}
        try:
            ccxt_config = self._config.get("exchange", {}).get("ccxt_config", {})
            proxies = ccxt_config.get("proxies", {})
            http_proxy = proxies.get("http", "")
            https_proxy = proxies.get("https", "")
            if http_proxy:
                env["HTTP_PROXY"] = http_proxy
                env["http_proxy"] = http_proxy
            if https_proxy:
                env["HTTPS_PROXY"] = https_proxy
                env["https_proxy"] = https_proxy
            # ALL_PROXY 兜底（部分 HTTP 库读这个）
            if https_proxy:
                env["ALL_PROXY"] = https_proxy
                env["all_proxy"] = https_proxy
        except Exception:
            pass
        return env

    def _call_gmgn(self, *args) -> dict | None:
        """
        调用 gmgn-cli 并返回解析后的 JSON

        :param args: gmgn-cli 子命令和参数
        :return: 解析后的 JSON dict，失败返回 None
        """
        cmd = [self._gmgn_cli] + list(args)

        # 合并系统环境变量 + 代理变量
        import os
        proc_env = os.environ.copy()
        proc_env.update(self._get_proxy_env())

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=proc_env,
                shell=True,
            )

            if result.returncode != 0:
                logger.warning(
                    f"GMGNPairList: gmgn-cli returned code {result.returncode}: "
                    f"CMD: {' '.join(cmd[:5])}... "
                    f"STDERR: {result.stderr[:300]}"
                )
                return None

            output = result.stdout.strip()
            if not output:
                return None

            return json.loads(output)

        except subprocess.TimeoutExpired:
            logger.warning(f"GMGNPairList: gmgn-cli timeout: {' '.join(cmd[:3])}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"GMGNPairList: Invalid JSON from gmgn-cli: {e}")
            return None
        except FileNotFoundError:
            raise OperationalException(
                "gmgn-cli not found. Please install it: npm install -g gmgn-cli"
            )
        except Exception as e:
            logger.warning(f"GMGNPairList: gmgn-cli error: {e}")
            return None

    def _load_address_cache(self) -> dict[str, str]:
        """从文件加载代币地址缓存"""
        try:
            path = Path(self._address_cache_path)
            if path.exists():
                with open(path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"GMGNPairList: Failed to load address cache: {e}")
        return {}

    def _save_address_cache(self) -> None:
        """保存代币地址缓存到文件"""
        try:
            path = Path(self._address_cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(self._address_cache, f, indent=2)
        except Exception as e:
            logger.debug(f"GMGNPairList: Failed to save address cache: {e}")

    def _save_security_cache(self, address: str, data: dict) -> None:
        """保存安全数据缓存到文件，供策略复用"""
        try:
            path = Path(self._security_cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            cache = {}
            if path.exists():
                with open(path, "r") as f:
                    cache = json.load(f)

            cache[address] = data

            with open(path, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.debug(f"GMGNPairList: Failed to save security cache: {e}")

    def _get_cache(self, key: str) -> Any:
        """获取缓存"""
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        """设置缓存"""
        self._cache[key] = (data, time.time())
