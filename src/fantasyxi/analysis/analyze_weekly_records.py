"""
Analyze weekly fantasy basketball records.
Compares current week stats against historical data to identify records.
"""

import pandas as pd
import logging

logging.basicConfig(level=logging.DEBUG, format='📊 %(message)s')

# NBA Categories
VALID_CATEGORIES = ['FGM', 'FG%', 'FTM', 'FT%', '3PM', '3PT%', 'REB', 'AST', 'STL', 'BLK', 'PTS', 'PPM']

# Lower is better (none for NBA in this setup, but keeping structure)
INVERSE_CATEGORIES = []


def analyze_weekly_records(latest_df: pd.DataFrame, 
                          history_df: pd.DataFrame, 
                          return_status: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Analyzes weekly fantasy basketball records by comparing current week to history.
    
    Args:
        latest_df: Current week's team statistics
        history_df: Historical team statistics
        return_status: Whether to include record status indicators
        
    Returns:
        tuple: (top_performers_df, worst_performers_df)
    """
    top_rows = []
    worst_rows = []

    for cat in VALID_CATEGORIES:
        if cat not in latest_df.columns:
            logging.warning(f"Category {cat} not found in data")
            continue
            
        is_inverse = cat in INVERSE_CATEGORIES
        
        # Find best and worst
        if is_inverse:
            best_val = latest_df[cat].min()
            worst_val = latest_df[cat].max()
            best_team = latest_df.loc[latest_df[cat].idxmin(), 'team_abbrev']
            worst_team = latest_df.loc[latest_df[cat].idxmax(), 'team_abbrev']
        else:
            best_val = latest_df[cat].max()
            worst_val = latest_df[cat].min()
            best_team = latest_df.loc[latest_df[cat].idxmax(), 'team_abbrev']
            worst_team = latest_df.loc[latest_df[cat].idxmin(), 'team_abbrev']

        status_best = ''
        status_worst = ''
        
        # Compare against history
        if return_status and not history_df.empty:
            if is_inverse:
                hist_best = history_df[cat].min()
                hist_worst = history_df[cat].max()
                
                if best_val < hist_best:
                    status_best = 'RECORD'
                elif best_val == hist_best:
                    status_best = 'TIED RECORD'
                    
                if worst_val > hist_worst:
                    status_worst = 'WORST RECORD'
                elif worst_val == hist_worst:
                    status_worst = 'TIED WORST RECORD'
            else:
                hist_best = history_df[cat].max()
                hist_worst = history_df[cat].min()
                
                if best_val > hist_best:
                    status_best = 'RECORD'
                elif best_val == hist_best:
                    status_best = 'TIED RECORD'
                    
                if worst_val < hist_worst:
                    status_worst = 'WORST RECORD'
                elif worst_val == hist_worst:
                    status_worst = 'TIED WORST RECORD'

        top_rows.append({
            "Category": cat,
            "Team": best_team,
            "Value": best_val,
            "Status": status_best
        })
        
        worst_rows.append({
            "Category": cat,
            "Team": worst_team,
            "Value": worst_val,
            "Status": status_worst
        })

    df_top = pd.DataFrame(top_rows)
    df_worst = pd.DataFrame(worst_rows)

    if return_status:
        return df_top, df_worst
    else:
        return df_top.drop(columns=["Status"]), df_worst.drop(columns=["Status"])