module.exports = {
  apps : [
    {
      name: "FT_MomentumFusion",
      script: "E:\\app\\miniconda\\envs\\freqAi\\Scripts\\freqtrade.exe",
      args: "trade --strategy StabilityMasterV4_MomentumFusion --config user_data/config_momentum_local_bt_static.json --logfile user_data/logs/freqtrade.log",
      interpreter: "none",
      cwd: "D:\\workspace\\freqtrade-reference",
      env: {
        "PYTHONPATH": "."
      }
    }]
}
