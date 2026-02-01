#!/usr/bin/env python3
"""
Test all strategies on 4h timeframe
"""
import subprocess
import sys
from datetime import datetime

strategies = [
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
]

config = "user_data/config/config_backtest.json"
timerange = "20210202-20220201"
timeframe = "4h"
results_file = "backtest_results_4h.txt"

print(f"Testing {len(strategies)} strategies on {timeframe} timeframe...")
print(f"Results will be saved to: {results_file}\n")

with open(results_file, 'w', encoding='utf-8') as f:
    f.write("=== BACKTEST RESULTS - 4H TIMEFRAME ===\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Timerange: {timerange}\n")
    f.write(f"Timeframe: {timeframe}\n\n")

for i, strategy in enumerate(strategies, 1):
    print(f"[{i}/{len(strategies)}] Testing: {strategy}")
    
    try:
        cmd = [
            sys.executable, '-m', 'freqtrade', 'backtesting',
            '-c', config,
            '--strategy', strategy,
            '--timerange', timerange,
            '--timeframe', timeframe
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout per strategy
        )
        
        # Extract key results
        output_lines = result.stdout.split('\n') + result.stderr.split('\n')
        key_lines = [line for line in output_lines 
                    if any(keyword in line for keyword in ['TOTAL', 'Trades', 'Profit', 'Win%', 'No trades'])]
        
        with open(results_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {strategy} ---\n")
            if key_lines:
                for line in key_lines[:5]:  # First 5 relevant lines
                    f.write(f"{line}\n")
            else:
                f.write("No results found\n")
            f.write("\n")
        
        # Print summary
        if key_lines:
            print(f"  {key_lines[0] if key_lines else 'No results'}")
        else:
            print(f"  No results found")
            
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after 5 minutes")
        with open(results_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {strategy} ---\n")
            f.write("TIMEOUT (exceeded 5 minutes)\n\n")
    except Exception as e:
        print(f"  ERROR: {e}")
        with open(results_file, 'a', encoding='utf-8') as f:
            f.write(f"--- {strategy} ---\n")
            f.write(f"ERROR: {e}\n\n")

print(f"\nAll tests completed! Results saved to: {results_file}")
