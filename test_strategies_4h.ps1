# Test all strategies on 4h timeframe
$strategies = @(
    'Bandtastic',
    'BreakEven',
    'CustomStoplossWithPSAR',
    'Diamond',
    'FixedRiskRewardLoss',
    'GodStra',
    'Heracles',
    'hlhb',
    'HourBasedStrategy',
    'InformativeSample',
    'mabStra',
    'multi_tf',
    'MultiMa',
    'PatternRecognition',
    'PowerTower',
    'Strategy001',
    'Strategy001_custom_exit',
    'Strategy002',
    'Strategy003',
    'Strategy004',
    'Strategy005',
    'Supertrend',
    'SwingHighToSky',
    'UniversalMACD'
)

$config = "user_data/config/config_backtest.json"
$timerange = "20210202-20220201"
$timeframe = "4h"
$resultsFile = "backtest_results_4h.txt"

Write-Host "Testing $($strategies.Count) strategies on 4h timeframe..." -ForegroundColor Green
Write-Host "Results will be saved to: $resultsFile" -ForegroundColor Yellow
"=== BACKTEST RESULTS - 4H TIMEFRAME ===" | Out-File $resultsFile
"Date: $(Get-Date)" | Out-File -Append $resultsFile
"" | Out-File -Append $resultsFile

foreach ($strategy in $strategies) {
    Write-Host "`nTesting: $strategy" -ForegroundColor Cyan
    try {
        $output = python -m freqtrade backtesting -c $config --strategy $strategy --timerange $timerange --timeframe $timeframe 2>&1
        $result = $output | Select-String -Pattern '(TOTAL|Trades|Profit|Win%|No trades)' | Select-Object -First 3
        "--- $strategy ---" | Out-File -Append $resultsFile
        $result | Out-File -Append $resultsFile
        "" | Out-File -Append $resultsFile
        Write-Host "  $result" -ForegroundColor White
    } catch {
        "--- $strategy --- ERROR: $_" | Out-File -Append $resultsFile
        Write-Host "  ERROR: $_" -ForegroundColor Red
    }
}

Write-Host "`nAll tests completed! Results saved to: $resultsFile" -ForegroundColor Green
