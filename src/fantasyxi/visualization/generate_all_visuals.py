"""
Master Visualization Generator - NBA Fantasy Basketball
Generates ALL weekly visualizations in one execution.

Outputs (all in data/weekly_outputs/week_XX/outputs/):
  - weekly_recap.png
  - weekly_barplots.png
  - cumulative_summary.png
  - top_players.png
  - top_players.txt (WhatsApp format)
  - top_players.csv
  - weekly_summary.md
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from matplotlib.table import Table
from matplotlib.patches import Rectangle
from fantasyxi.analysis.analyze_weekly_records import analyze_weekly_records

import requests
from io import BytesIO
from PIL import Image
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from thefuzz import fuzz
# ============================================================

# Mallitalytics Colors
FIGURE_BG_COLOR = "#F2EFE9"
TEXT_COLOR = "#2E3A43"
MALLITALYTICS_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "mallitalytics_soft_green", ["#F2EFE9", "#A5B884", "#4E7B62"]
)

# Configuration
BASE_DIR = "/Users/gilrojasb/Desktop/FantasyXI_NBA/data/weekly_outputs"
CATEGORIES = ['FGM', 'FG%', 'FTM', 'FT%', '3PM', '3PT%', 'REB', 'AST', 'STL', 'BLK', 'PTS', 'PPM']
SUM_CATEGORIES = ['FGM', 'FTM', '3PM', 'REB', 'AST', 'STL', 'BLK', 'PTS']
AVG_CATEGORIES = ['FG%', 'FT%', '3PT%', 'PPM']
ALL_CATEGORIES = SUM_CATEGORIES + AVG_CATEGORIES

CATEGORY_WEIGHTS = {
    'PTS': 1.0, 'REB': 1.2, 'AST': 1.3, 'STL': 2.0,
    'BLK': 2.0, '3PM': 1.5, 'FG%': 1.8, 'FT%': 1.5,
}


# ============================================================
# PLAYER PHOTO HELPERS
# ============================================================

def get_player_photo_url(player_id: int, width: int = 350, height: int = 254) -> str:
    """
    Construye la URL de la foto del jugador usando ESPN player ID.
    
    Args:
        player_id: ESPN player ID
        width: Ancho de la imagen
        height: Alto de la imagen
    
    Returns:
        URL completa de la imagen
    """
    if not player_id:
        return None
    return f"https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/{player_id}.png&w={width}&h={height}"


def build_player_id_map(league, matchup_period: int) -> dict:
    """
    Construye un diccionario {player_name: player_id} desde el API.
    
    Args:
        league: ESPN League object
        matchup_period: Semana a extraer
    
    Returns:
        dict con mapeo nombre -> ID
    """
    from fantasyxi.api.espn_client import connect_to_league
    
    if league is None:
        league = connect_to_league()
    
    box_scores = league.box_scores(matchup_period=matchup_period)
    player_map = {}
    
    for game in box_scores:
        for side, team_obj, lineup in [
            ("HOME", getattr(game, "home_team", None), getattr(game, "home_lineup", []) or []),
            ("AWAY", getattr(game, "away_team", None), getattr(game, "away_lineup", []) or []),
        ]:
            for pl in lineup:
                player_name = getattr(pl, "name", None)
                player_id = getattr(pl, "playerId", None)
                
                if player_name and player_id:
                    player_map[player_name] = player_id
    
    return player_map


def fuzzy_match_player_id(player_name: str, player_map: dict, threshold: int = 85) -> int:
    """
    Busca el player_id usando fuzzy matching.
    
    Args:
        player_name: Nombre del jugador
        player_map: Diccionario {nombre: id}
        threshold: Score mínimo de similitud
    
    Returns:
        player_id o None
    """
    from thefuzz import fuzz
    
    # Match exacto
    if player_name in player_map:
        return player_map[player_name]
    
    # Fuzzy matching
    best_match = None
    best_score = 0
    
    for name, pid in player_map.items():
        score = fuzz.ratio(player_name.lower(), name.lower())
        if score > best_score:
            best_score = score
            best_match = pid
    
    if best_score >= threshold:
        return best_match
    
    return None


def download_player_photo(url: str, size: tuple = (90, 90), timeout: int = 5):
    """
    Descarga y redimensiona la foto del jugador.
    
    Args:
        url: URL de la foto
        size: Tupla (ancho, alto)
        timeout: Timeout en segundos
    
    Returns:
        PIL.Image object o placeholder
    """
    if not url:
        return Image.new('RGB', size, color='#A5B884')
    
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        img = img.resize(size, Image.Resampling.LANCZOS)
        
        return img
    
    except:
        return Image.new('RGB', size, color='#A5B884')

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def setup_output_directory(week: int) -> str:
    """Create and return output directory for the week."""
    output_dir = os.path.join(BASE_DIR, f"week_{week:02d}", "outputs")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def load_week_data(week: int) -> tuple:
    """Load player and team stats for a given week."""
    week_dir = os.path.join(BASE_DIR, f"week_{week:02d}")
    
    player_path = os.path.join(week_dir, "player_stats.csv")
    team_path = os.path.join(week_dir, "team_stats.csv")
    
    if not os.path.exists(player_path) or not os.path.exists(team_path):
        raise FileNotFoundError(f"Data for week {week} not found")
    
    df_players = pd.read_csv(player_path)
    df_team = pd.read_csv(team_path)
    
    return df_players, df_team


def load_all_history(latest_week: int) -> pd.DataFrame:
    """Load all historical team stats up to (not including) latest_week."""
    dfs = []
    for week in range(1, latest_week):
        try:
            _, df_team = load_week_data(week)
            df_team['Week'] = week
            dfs.append(df_team)
        except FileNotFoundError:
            continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# ============================================================
# 1. WEEKLY RECAP
# ============================================================

def generate_weekly_recap(week: int, output_dir: str):
    """Generate weekly recap with top/worst performers."""
    print(f"\n📊 [1/4] Generating Weekly Recap...")
    
    _, df_team = load_week_data(week)
    history_df = load_all_history(week) if week > 1 else pd.DataFrame()
    
    top_df, worst_df = analyze_weekly_records(df_team, history_df, return_status=(week > 1))
    
    # Save markdown
    md_path = os.path.join(output_dir, "weekly_summary.md")
    with open(md_path, "w") as f:
        f.write(f"# 🏀 Weekly Summary – Week {week}\n\n")
        f.write("## 🏆 Top Performers\n\n")
        f.write(top_df.to_markdown(index=False, floatfmt=".3f"))
        f.write("\n\n## 💤 Worst Performers\n\n")
        f.write(worst_df.to_markdown(index=False, floatfmt=".3f"))
    
    # Render image
    def prep_df(df):
        cols = ["Category", "Team", "Value", "Status"] if "Status" in df.columns else ["Category", "Team", "Value"]
        return df[cols].copy()
    
    tdf, wdf = prep_df(top_df), prep_df(worst_df)
    
    row_height = 0.60
    num_rows = max(len(tdf), len(wdf)) + 2
    fig_height = row_height * num_rows
    
    fig, axs = plt.subplots(2, 1, figsize=(10, fig_height), dpi=200,
                            gridspec_kw={"height_ratios": [len(tdf)+2, len(wdf)+2]})
    fig.patch.set_facecolor(FIGURE_BG_COLOR)
    
    fig.suptitle(f"FantasyXI NBA Weekly Recap – Week {week}",
                 fontsize=22, color=TEXT_COLOR, weight="bold", y=0.96)
    fig.text(0.5, 0.925, "Created by: @Mallitalytics | Data: ESPN API",
             ha='center', va='top', fontsize=12, color=TEXT_COLOR)
    
    def draw_table(ax, df, title, title_color):
        ax.axis("off")
        table = Table(ax, bbox=[0, 0, 1, 1])
        FLOAT_CATEGORIES = {"FG%", "FT%", "3PT%", "PPM"}
        ncols = len(df.columns)
        
        for j in range(ncols):
            cell = table.add_cell(0, j, width=1/ncols, height=0.21,
                                  text=title if j == 0 else "", loc="center", facecolor=title_color)
            if j == 0:
                cell.get_text().set_fontsize(14)
                cell.get_text().set_weight("bold")
                cell.get_text().set_color(TEXT_COLOR)
        
        for j, col in enumerate(df.columns):
            cell = table.add_cell(1, j, width=1/ncols, height=0.16,
                                  text=col, loc="center", facecolor="#e8e8e8")
            cell.get_text().set_fontsize(11)
            cell.get_text().set_weight("bold")
            cell.get_text().set_color(TEXT_COLOR)
        
        for i, row in df.iterrows():
            bg_color = "white"
            for j, col in enumerate(df.columns):
                val = row[col]
                if col == "Value":
                    fmt_val = f"{float(val):.3f}" if row["Category"] in FLOAT_CATEGORIES else f"{int(float(val))}"
                else:
                    fmt_val = str(val)
                
                cell = table.add_cell(i + 2, j, width=1/ncols, height=0.14,
                                      text=fmt_val, loc="center", facecolor=bg_color)
                cell.get_text().set_fontsize(10)
                cell.get_text().set_color(TEXT_COLOR)
        
        ax.add_table(table)
    
    draw_table(axs[0], tdf, "Top Performers", "#A5B884")
    draw_table(axs[1], wdf, "Worst Performers", "#F97D34")
    
    plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.05, hspace=0.2)
    
    output_path = os.path.join(output_dir, "weekly_recap.png")
    fig.savefig(output_path, bbox_inches='tight', facecolor=FIGURE_BG_COLOR)
    plt.close(fig)
    
    print(f"  ✅ weekly_recap.png")
    print(f"  ✅ weekly_summary.md")


# ============================================================
# 2. WEEKLY BARPLOTS
# ============================================================

def generate_weekly_barplots(week: int, output_dir: str):
    """Generate barplots for all categories."""
    print(f"\n📊 [2/4] Generating Weekly Barplots...")
    
    _, df_team = load_week_data(week)
    
    fig, axes = plt.subplots(nrows=4, ncols=3, figsize=(20, 22))
    fig.patch.set_facecolor(FIGURE_BG_COLOR)
    axes = axes.flatten()
    
    fig.suptitle(f" Weekly Team Performance - Week {week}", 
                 fontsize=32, color=TEXT_COLOR, y=0.97)
    fig.text(0.5, 0.94, "Created by: @Mallitalytics | Data: ESPN API",
             ha='center', va='top', fontsize=16, color=TEXT_COLOR)
    
    for i, cat in enumerate(CATEGORIES):
        if i >= len(axes):
            break
        ax = axes[i]
        ax.set_facecolor(FIGURE_BG_COLOR)
        
        sorted_df = df_team.sort_values(by=cat)
        mean_val = sorted_df[cat].mean()
        
        bar_colors = ["#4E7B62" if val > mean_val else "#F97D34" for val in sorted_df[cat]]
        
        bars = sns.barplot(x='team_abbrev', y=cat, data=sorted_df, palette=bar_colors, ax=ax)
        
        for p in bars.patches:
            val = p.get_height()
            label = f"{val:.3f}" if cat in ["FG%", "FT%", "3PT%", "PPM"] else f"{val:.0f}"
            ax.annotate(label, (p.get_x() + p.get_width() / 2, val),
                       ha='center', va='bottom', fontsize=8, color=TEXT_COLOR)
        
        ax.axhline(mean_val, color=TEXT_COLOR, linestyle='--', linewidth=1, alpha=0.6)
        ax.set_title(cat, color=TEXT_COLOR, fontsize=14, weight='bold')
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis='x', rotation=45, colors=TEXT_COLOR)
        ax.tick_params(axis='y', colors=TEXT_COLOR)
    
    for j in range(len(CATEGORIES), len(axes)):
        fig.delaxes(axes[j])
    
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    output_path = os.path.join(output_dir, "weekly_barplots.png")
    plt.savefig(output_path, facecolor=FIGURE_BG_COLOR)
    plt.close()
    
    print(f"  ✅ weekly_barplots.png")


# ============================================================
# 3. CUMULATIVE SUMMARY
# ============================================================

def generate_cumulative_summary(week: int, output_dir: str):
    """Generate cumulative team summary."""
    print(f"\n📊 [3/4] Generating Cumulative Summary...")
    
    df_all = load_all_history(week + 1)  # Include current week
    
    sum_df = df_all.groupby("team_abbrev")[SUM_CATEGORIES].sum().reset_index()
    avg_df = df_all.groupby("team_abbrev")[AVG_CATEGORIES].mean().reset_index()
    summary = pd.merge(sum_df, avg_df, on="team_abbrev")
    
    # Compute performance score
    score_df = pd.DataFrame(index=summary.index)
    for cat in ALL_CATEGORIES:
        ranks = summary[cat].rank(pct=True, ascending=True)
        score_df[cat] = pd.cut(ranks, bins=[i/10 for i in range(11)], labels=range(1, 11)).astype(int)
    
    summary["PerformanceScore"] = score_df.sum(axis=1)
    summary["Power Rank"] = summary["PerformanceScore"].rank(method="min", ascending=False).astype(int)
    summary = summary.sort_values("PerformanceScore", ascending=False)
    
    # Render table
    display_df = summary[["Power Rank", "team_abbrev"] + ALL_CATEGORIES].copy()
    
    for col in AVG_CATEGORIES:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}")
    for col in SUM_CATEGORIES:
        display_df[col] = display_df[col].apply(lambda x: f"{int(x)}")
    
    num_rows = len(display_df) + 2
    fig, ax = plt.subplots(figsize=(14, num_rows * 0.5), dpi=200)
    fig.patch.set_facecolor(FIGURE_BG_COLOR)
    ax.axis("off")
    
    fig.suptitle(f"Cumulative Team Summary (Through Week {week})",
                 fontsize=18, color=TEXT_COLOR, weight="bold", y=0.96)
    fig.text(0.5, 0.92, "Created by: @Mallitalytics | Data: ESPN API",
             ha='center', va='top', fontsize=10, color=TEXT_COLOR)
    
    table = Table(ax, bbox=[0, 0, 1, 1])
    ncols = len(display_df.columns)
    
    for j, col in enumerate(display_df.columns):
        cell = table.add_cell(0, j, width=1/ncols, height=0.08,
                             text=col, loc="center", facecolor="#2E3A43")
        cell.get_text().set_fontsize(10)
        cell.get_text().set_weight("bold")
        cell.get_text().set_color("#F2EFE9")
    
    for i, (idx, row) in enumerate(display_df.iterrows()):
        for j, col in enumerate(display_df.columns):
            val = row[col]
            if col in ALL_CATEGORIES:
                numeric_val = summary.loc[idx, col]
                normalized = (numeric_val - summary[col].min()) / (summary[col].max() - summary[col].min())
                bg_color = MALLITALYTICS_CMAP(normalized)
            else:
                bg_color = "white"
            
            cell = table.add_cell(i + 1, j, width=1/ncols, height=0.06,
                                 text=str(val), loc="center", facecolor=bg_color)
            cell.get_text().set_fontsize(9)
            cell.get_text().set_color(TEXT_COLOR)
    
    ax.add_table(table)
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    
    output_path = os.path.join(output_dir, "cumulative_summary.png")
    plt.savefig(output_path, bbox_inches='tight', facecolor=FIGURE_BG_COLOR)
    plt.close()
    
    print(f"  ✅ cumulative_summary.png")


# ============================================================
# 4. TOP PLAYERS
# ============================================================

def generate_top_players(week: int, output_dir: str, league=None):
    """Generate top player performers with photos."""
    print(f"\n📊 [4/4] Generating Top Players...")
    
    df_players, _ = load_week_data(week)
    df_players = df_players[df_players['MIN'] >= 10].copy()
    
    # Build player ID map from API
    print(f"  🔍 Mapping player IDs from API...")
    player_id_map = build_player_id_map(league, matchup_period=week)
    
    # Map player IDs to dataframe
    df_players['player_id'] = df_players['player_name'].apply(
        lambda name: fuzzy_match_player_id(name, player_id_map)
    )
    df_players['photo_url'] = df_players['player_id'].apply(
        lambda pid: get_player_photo_url(int(pid)) if pd.notna(pid) else None
    )
    
    matched = df_players['player_id'].notna().sum()
    print(f"  ✅ Matched {matched}/{len(df_players)} players")
    
    # Calculate weighted score
    df_players['PerformanceScore'] = 0.0
    for cat, weight in CATEGORY_WEIGHTS.items():
        if cat in df_players.columns:
            df_players[cat] = df_players[cat].fillna(0)
            mean = df_players[cat].mean()
            std = df_players[cat].std()
            if std > 0:
                z_score = (df_players[cat] - mean) / std
                df_players['PerformanceScore'] += z_score * weight
    
    df_players['PerformanceScore'] = df_players['PerformanceScore'].round(2)
    top_10 = df_players.nlargest(10, 'PerformanceScore')
    
    # Download photos
    print(f"  📸 Downloading player photos...")
    player_photos = {}
    for idx, player in top_10.iterrows():
        photo = download_player_photo(player['photo_url'], size=(90, 90))
        player_photos[idx] = photo
    
    # Save CSV
    csv_path = os.path.join(output_dir, "top_players.csv")
    top_10.to_csv(csv_path, index=False)
    
    # WhatsApp format
    whatsapp_text = f"🏀 *TOP 10 PLAYERS - WEEK {week}*\n"
    whatsapp_text += f"_(Weighted by scarcity: STL/BLK 2x, FG% 1.8x)_\n\n"
    for i, (idx, p) in enumerate(top_10.iterrows(), 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        whatsapp_text += f"{medal} *{p['player_name']}* ({p['team_abbrev']})\n"
        whatsapp_text += f"   Score: {p['PerformanceScore']} | {int(p['PTS'])} PTS, {int(p['REB'])} REB, {int(p['AST'])} AST\n\n"
    whatsapp_text += f"_Data: ESPN API | @Mallitalytics_"
    
    txt_path = os.path.join(output_dir, "top_players.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(whatsapp_text)
    
    # Render image with photos
    fig, ax = plt.subplots(figsize=(16, 12), dpi=200)
    fig.patch.set_facecolor(FIGURE_BG_COLOR)
    ax.axis('off')
    
    fig.text(0.5, 0.96, f"Top 10 Player Performances - Week {week}",
             ha='center', fontsize=26, weight='bold', color=TEXT_COLOR)
    fig.text(0.5, 0.93, 
             "Weighted Score: STL/BLK (2.0x) | FG% (1.8x) | FT%/3PM (1.5x) | AST (1.3x) | REB (1.2x) | PTS (1.0x)",
             ha='center', fontsize=11, color=TEXT_COLOR, style='italic')
    
    y_start = 0.88
    row_height = 0.082
    
    for i, (idx, player) in enumerate(top_10.iterrows()):
        y_pos = y_start - (i * row_height)
        
        if i == 0:
            bg_color, rank_text = "#FFD700", "1"
        elif i == 1:
            bg_color, rank_text = "#E6BE8A", "2"
        elif i == 2:
            bg_color, rank_text = "#C9A961", "3"
        else:
            bg_color, rank_text = "#FFFFFF", f"{i+1}"
        
        rect = Rectangle((0.04, y_pos - 0.038), 0.92, 0.074,
                         facecolor=bg_color, edgecolor=TEXT_COLOR, linewidth=2, transform=fig.transFigure)
        fig.patches.append(rect)
        
        # Player photo
        if idx in player_photos:
            photo = player_photos[idx]
            imagebox = OffsetImage(photo, zoom=0.45)
            ab = AnnotationBbox(imagebox, (0.085, y_pos), 
                               frameon=False, 
                               xycoords='figure fraction',
                               box_alignment=(0.5, 0.5))
            fig.add_artist(ab)
        
        # Rank number
        fig.text(0.048, y_pos, rank_text, ha='center', va='center', fontsize=14, weight='bold',
                color=TEXT_COLOR, transform=fig.transFigure)
        
        # Player name
        fig.text(0.135, y_pos + 0.017, player['player_name'], ha='left', va='center', fontsize=12,
                weight='bold', color=TEXT_COLOR, transform=fig.transFigure)
        fig.text(0.135, y_pos - 0.014, f"{player['team_abbrev']} | {player['pro_team']}",
                ha='left', va='center', fontsize=9, style='italic', color=TEXT_COLOR, transform=fig.transFigure)
        
        # Score
        fig.text(0.42, y_pos, f"Score: {player['PerformanceScore']}", ha='center', va='center',
                fontsize=11, weight='bold', color=TEXT_COLOR, transform=fig.transFigure)
        
        # Stats
        stats_data = [
            (f"{int(player['PTS'])}", "PTS"), (f"{int(player['REB'])}", "REB"),
            (f"{int(player['AST'])}", "AST"), (f"{int(player['STL'])}", "STL"),
            (f"{int(player['BLK'])}", "BLK"), (f"{int(player['3PM'])}", "3PM"),
            (f"{int(player['FGM'])}", "FGM")
        ]
        
        for j, (value, label) in enumerate(stats_data):
            x_pos = 0.54 + (j * 0.062)
            fig.text(x_pos, y_pos + 0.012, value, ha='center', va='center', fontsize=11,
                    weight='bold', color=TEXT_COLOR, family='monospace', transform=fig.transFigure)
            fig.text(x_pos, y_pos - 0.014, label, ha='center', va='center', fontsize=8,
                    color=TEXT_COLOR, transform=fig.transFigure)
    
    fig.text(0.5, 0.02, "Created by: @Mallitalytics | Data: ESPN API",
             ha='center', fontsize=11, color=TEXT_COLOR)
    
    plt.tight_layout()
    img_path = os.path.join(output_dir, "top_players.png")
    plt.savefig(img_path, facecolor=FIGURE_BG_COLOR, bbox_inches='tight', dpi=200)
    plt.close()
    
    print(f"  ✅ top_players.png (with photos)")
    print(f"  ✅ top_players.csv")
    print(f"  ✅ top_players.txt")

# ============================================================
# MAIN ORCHESTRATOR
# ============================================================

def main(week: int = None, league=None):
    """
    Generate all weekly visualizations.
    
    Args:
        week: Week number (defaults to latest available)
        league: ESPN League object (optional, will connect if None)
    """
    if week is None:
        week_dirs = [d for d in os.listdir(BASE_DIR) if d.startswith('week_')]
        if not week_dirs:
            print("❌ No weekly data found")
            return
        week = max([int(d.split('_')[1]) for d in week_dirs])
    
    # Connect to league if not provided
    if league is None:
        from fantasyxi.api.espn_client import connect_to_league
        league = connect_to_league()
    
    print(f"\n{'='*60}")
    print(f"🎨 GENERATING ALL VISUALIZATIONS - WEEK {week}")
    print(f"{'='*60}")
    
    output_dir = setup_output_directory(week)
    
    try:
        generate_weekly_recap(week, output_dir)
        generate_weekly_barplots(week, output_dir)
        generate_cumulative_summary(week, output_dir)
        generate_top_players(week, output_dir, league)  # ✅ PASS LEAGUE
        
        print(f"\n{'='*60}")
        print(f"✅ ALL VISUALIZATIONS COMPLETE")
        print(f"📁 Output location: {output_dir}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main(week=4)