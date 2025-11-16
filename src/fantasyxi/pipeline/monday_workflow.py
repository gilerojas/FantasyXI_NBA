"""
Monday Fantasy Basketball Pipeline
===================================
Consolidated script that extracts:
  1. Player-level stats (all player lines)
  2. Team-level aggregated stats
  3. Matchup results with category wins

Saves everything into: data/weekly_outputs/week_XX/
Run this every Monday after the previous matchup completes.

Usage:
    from src.pipeline.monday_workflow import run_monday_pipeline
    results = run_monday_pipeline(league, matchup_period=1)
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from fantasyxi.api.espn_client import connect_to_league

# ============================================================
# CONFIGURATION
# ============================================================

CATEGORY_DIRECTION = {
    'FGM': True,
    'FG%': True,
    'FTM': True,
    'FT%': True,
    '3PM': True,
    '3PT%': True,  # Fixed: API uses 3PT% not 3P%
    'REB': True,
    'AST': True,
    'STL': True,
    'BLK': True,
    'PTS': True,
    'PPM': True,
}

VALID_CATEGORIES = list(CATEGORY_DIRECTION.keys())

BASE_DIR = Path("/Users/gilrojasb/Desktop/FantasyXI_NBA/data/weekly_outputs")


# ============================================================
# PLAYER-LEVEL EXTRACTION
# ============================================================

def extract_player_stats(league, matchup_period: int) -> pd.DataFrame:
    """
    Extract all player lines for a specific matchup period.
    Returns raw player-level data with team assignments.
    """
    print(f"\n📥 [1/3] Extracting player stats for week {matchup_period}")
    
    box_scores = league.box_scores(matchup_period=matchup_period)
    rows = []
    
    for game in box_scores:
        for side, team_obj, lineup in [
            ("HOME", getattr(game, "home_team", None), getattr(game, "home_lineup", []) or []),
            ("AWAY", getattr(game, "away_team", None), getattr(game, "away_lineup", []) or []),
        ]:
            for pl in lineup:
                stats_outer = getattr(pl, "stats", {}) or {}
                raw = next(iter(stats_outer.values()), {})
                totals = raw.get("total", {}) or {}
                
                rec = {
                    "matchup_period": matchup_period,
                    "side": side,
                    "team_id": getattr(team_obj, "team_id", None),
                    "team_abbrev": getattr(team_obj, "team_abbrev", None),
                    "player_name": getattr(pl, "name", None),
                    "pro_team": getattr(pl, "proTeam", None),
                    "position": getattr(pl, "position", None),
                }
                rec.update(totals)
                rows.append(rec)
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        print(f"⚠️  No player data found")
        return df
    
    print(f"✅ Extracted {len(df)} player lines from {df['team_abbrev'].nunique()} teams")
    return df


# ============================================================
# TEAM-LEVEL AGGREGATION
# ============================================================

def aggregate_team_stats(df_players: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate player stats to team level.
    Recalculates shooting percentages from makes/attempts.
    """
    print(f"\n📊 [2/3] Aggregating team-level stats")
    
    if df_players.empty:
        return pd.DataFrame()
    
    # Sum counting stats
    df_team = df_players.groupby('team_abbrev')[VALID_CATEGORIES].sum()
    
    # Recalculate percentages from team totals
    fgm_sum = df_players.groupby('team_abbrev')['FGM'].sum()
    fga_sum = df_players.groupby('team_abbrev')['FGA'].sum()
    df_team['FG%'] = (fgm_sum / fga_sum).fillna(0)
    
    ftm_sum = df_players.groupby('team_abbrev')['FTM'].sum()
    fta_sum = df_players.groupby('team_abbrev')['FTA'].sum()
    df_team['FT%'] = (ftm_sum / fta_sum).fillna(0)
    
    pm_sum = df_players.groupby('team_abbrev')['3PM'].sum()
    pa_sum = df_players.groupby('team_abbrev')['3PA'].sum()
    df_team['3PT%'] = (pm_sum / pa_sum).fillna(0)  # Fixed: 3PT% not 3P%
    
    # Calculate PPM (Points Per Minute)
    pts_sum = df_players.groupby('team_abbrev')['PTS'].sum()
    min_sum = df_players.groupby('team_abbrev')['MIN'].sum()
    df_team['PPM'] = (pts_sum / min_sum).fillna(0)
    
    df_team = df_team.reset_index()
    
    print(f"✅ Aggregated stats for {len(df_team)} teams")
    return df_team


# ============================================================
# MATCHUP RESULTS WITH CATEGORY WINS
# ============================================================

def calculate_matchup_results(league, matchup_period: int, df_team: pd.DataFrame) -> pd.DataFrame:
    """
    Compare teams head-to-head across all categories.
    Determines category winners and overall matchup outcomes.
    """
    print(f"\n🏆 [3/3] Calculating matchup results")
    
    box_scores = league.box_scores(matchup_period=matchup_period)
    df_team_indexed = df_team.set_index('team_abbrev')
    
    results = []
    
    for idx, matchup in enumerate(box_scores):
        home_team = matchup.home_team
        away_team = matchup.away_team
        home_abbrev = home_team.team_abbrev
        away_abbrev = away_team.team_abbrev
        
        home_wins = []
        away_wins = []
        ties = []
        stat_values = {}
        
        # Compare each category
        for cat in VALID_CATEGORIES:
            if cat not in df_team_indexed.columns:
                continue
            
            home_val = df_team_indexed.loc[home_abbrev, cat] if home_abbrev in df_team_indexed.index else None
            away_val = df_team_indexed.loc[away_abbrev, cat] if away_abbrev in df_team_indexed.index else None
            
            stat_values[f"{cat}_HOME"] = home_val
            stat_values[f"{cat}_AWAY"] = away_val
            
            if home_val is None or away_val is None:
                continue
            
            try:
                if CATEGORY_DIRECTION[cat]:
                    # Higher is better
                    if home_val > away_val:
                        home_wins.append(cat)
                    elif away_val > home_val:
                        away_wins.append(cat)
                    else:
                        ties.append(cat)
                else:
                    # Lower is better
                    if home_val < away_val:
                        home_wins.append(cat)
                    elif away_val < home_val:
                        away_wins.append(cat)
                    else:
                        ties.append(cat)
            except Exception as e:
                print(f"⚠️  Error comparing {cat}: {e}")
        
        # Determine outcome
        score = f"{len(home_wins)}-{len(away_wins)}-{len(ties)}"
        if len(home_wins) > len(away_wins):
            result = "Home Win"
        elif len(away_wins) > len(home_wins):
            result = "Away Win"
        else:
            result = "Tie"
        
        results.append({
            "Week": matchup_period,
            "Matchup": idx + 1,
            "Home Team": home_abbrev,
            "Away Team": away_abbrev,
            "Score": score,
            "Result": result,
            "Home Wins": len(home_wins),
            "Away Wins": len(away_wins),
            "Home Win Categories": ", ".join(home_wins),
            "Away Win Categories": ", ".join(away_wins),
            **stat_values
        })
    
    df_results = pd.DataFrame(results)
    print(f"✅ Processed {len(df_results)} matchup(s)")
    
    return df_results


# ============================================================
# MAIN PIPELINE ORCHESTRATOR
# ============================================================

def run_monday_pipeline(league, matchup_period: int = None):
    """
    Master function that executes the full Monday workflow.
    
    Steps:
      1. Extract player-level stats
      2. Aggregate to team-level stats
      3. Calculate matchup results with category wins
      4. Save all outputs to weekly folder
    
    Args:
        league: ESPN League object
        matchup_period: Week to process (defaults to last completed week)
    
    Outputs:
        data/weekly_outputs/week_XX/
          ├── player_stats.csv
          ├── team_stats.csv
          └── matchup_results.csv
    """
    # Default to last completed matchup
    if matchup_period is None:
        matchup_period = league.currentMatchupPeriod - 1
    
    print(f"\n{'='*60}")
    print(f"🚀 MONDAY PIPELINE - Week {matchup_period}")
    print(f"{'='*60}")
    print(f"📅 Run timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create output directory
    week_dir = BASE_DIR / f"week_{matchup_period:02d}"
    week_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract player stats
    df_players = extract_player_stats(league, matchup_period)
    if df_players.empty:
        print("\n❌ Pipeline aborted: No player data")
        return
    
    # Step 2: Aggregate team stats
    df_team = aggregate_team_stats(df_players)
    
    # Step 3: Calculate matchup results
    df_matchups = calculate_matchup_results(league, matchup_period, df_team)
    
    # Step 4: Save all outputs
    print(f"\n💾 Saving outputs to: {week_dir}")
    
    player_path = week_dir / "player_stats.csv"
    team_path = week_dir / "team_stats.csv"
    matchup_path = week_dir / "matchup_results.csv"
    
    df_players.to_csv(player_path, index=False)
    df_team.to_csv(team_path, index=False)
    df_matchups.to_csv(matchup_path, index=False)
    
    print(f"  ✅ {player_path.name} ({len(df_players)} rows)")
    print(f"  ✅ {team_path.name} ({len(df_team)} rows)")
    print(f"  ✅ {matchup_path.name} ({len(df_matchups)} rows)")
    
    print(f"\n{'='*60}")
    print(f"✅ PIPELINE COMPLETE")
    print(f"{'='*60}\n")
    
    return {
        'players': df_players,
        'teams': df_team,
        'matchups': df_matchups
    }


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    """
    Run this script every Monday to process the completed matchup.
    Configure MATCHUP_PERIOD or let it auto-detect the last completed week.
    """
    # Connect to league
    league = connect_to_league()
    
    # Option 1: Auto-detect last completed week
    results = run_monday_pipeline(league)
    
    # Option 2: Specify exact week
    # results = run_monday_pipeline(league, matchup_period=1)
    
    # Option 3: Batch process multiple weeks
    # for week in range(1, 4):
    #     run_monday_pipeline(league, matchup_period=week)