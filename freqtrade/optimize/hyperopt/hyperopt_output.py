import sys
from os import get_terminal_size
from typing import Any

from rich.align import Align
from rich.console import Console
from rich.table import Table
from rich.text import Text

from freqtrade.constants import Config
from freqtrade.optimize.optimize_reports import generate_wins_draws_losses
from freqtrade.util import fmt_coin


class HyperoptOutput:
    def __init__(self, streaming=False) -> None:
        self._results: list[Any] = []
        self._streaming = streaming
        self.__init_table()

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return Align.center(self.table)

    def __init_table(self) -> None:
        """Initialize table"""
        self.table = Table(
            title="参数优化结果 (Hyperopt Results)",
        )
        # Headers
        self.table.add_column("最佳", justify="left")
        self.table.add_column("轮次", justify="right")
        self.table.add_column("交易数", justify="right")
        self.table.add_column("胜  平  负  胜率%", justify="right")
        self.table.add_column("平均利润", justify="right")
        self.table.add_column("总利润", justify="right")
        self.table.add_column("平均持仓时间", justify="right")
        self.table.add_column("目标值", justify="right")
        self.table.add_column("最大回撤", justify="right")

    def print(self, console: Console | None = None, *, print_colorized=True):
        if not console:
            console = Console(
                color_system="auto" if print_colorized else None,
                width=200 if "pytest" in sys.modules else None,
            )

        console.print(self.table)

    def add_data(
        self,
        config: Config,
        results: list,
        total_epochs: int,
        highlight_best: bool,
    ) -> None:
        """Format one or multiple rows and add them"""
        stake_currency = config["stake_currency"]
        self._results.extend(results)

        max_rows: int | None = None

        if self._streaming:
            try:
                ts = get_terminal_size()
                # Get terminal size.
                # Account for header, borders, and for the progress bar.
                # This assumes that lines don't wrap.
                if ts.columns < 148:
                    # If the terminal is too small, we can't display the table properly.
                    # We will halve the number of rows to display.
                    max_rows = -(int(ts.lines / 2) - 6)
                else:
                    max_rows = -(ts.lines - 6)
            except OSError:
                # If we can't get the terminal size, we will just display the last 10 rows.
                pass

        self.__init_table()
        for r in self._results[max_rows:]:
            self.table.add_row(
                *[
                    # "Best":
                    (
                        ("*" if r["is_initial_point"] or r["is_random"] else "")
                        + (" 最佳" if r["is_best"] else "")
                    ).lstrip(),
                    # "Epoch":
                    f"{r['current_epoch']}/{total_epochs}",
                    # "Trades":
                    str(r["results_metrics"]["total_trades"]),
                    # "Win  Draw  Loss  Win%":
                    generate_wins_draws_losses(
                        r["results_metrics"]["wins"],
                        r["results_metrics"]["draws"],
                        r["results_metrics"]["losses"],
                    ),
                    # "Avg profit":
                    f"{r['results_metrics']['profit_mean']:.2%}"
                    if r["results_metrics"]["profit_mean"] is not None
                    else "--",
                    # "Profit":
                    Text(
                        "{} {}".format(
                            fmt_coin(
                                r["results_metrics"]["profit_total_abs"],
                                stake_currency,
                                keep_trailing_zeros=True,
                            ),
                            f"({r['results_metrics']['profit_total']:,.2%})".rjust(10, " "),
                        )
                        if r["results_metrics"].get("profit_total_abs", 0) != 0.0
                        else "--",
                        style=(
                            "green"
                            if r["results_metrics"].get("profit_total_abs", 0) > 0
                            else "red"
                        )
                        if not r["is_best"]
                        else "",
                    ),
                    # "Avg duration":
                    str(r["results_metrics"]["holding_avg"]),
                    # "Objective":
                    f"{r['loss']:,.5f}" if r["loss"] != 100000 else "N/A",
                    # "Max Drawdown (Acct)":
                    "{} {}".format(
                        fmt_coin(
                            r["results_metrics"]["max_drawdown_abs"],
                            stake_currency,
                            keep_trailing_zeros=True,
                        ),
                        (f"({r['results_metrics']['max_drawdown_account']:,.2%})").rjust(10, " "),
                    )
                    if r["results_metrics"]["max_drawdown_account"] != 0.0
                    else "--",
                ],
                style=" ".join(
                    [
                        "bold gold1" if r["is_best"] and highlight_best else "",
                        "italic " if r["is_initial_point"] else "",
                    ]
                ),
            )
