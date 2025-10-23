"""
Funciones para extraer boxscores de juegos NBA.
"""

import re
import pandas as pd
from datetime import date  # ✅ AGREGADO
from json import JSONDecodeError
from nba_api.live.nba.endpoints import boxscore as live_boxscore
from nba_api.stats.endpoints import boxscoretraditionalv2 as stats_box


_iso_pat = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")


def iso_to_minutes(iso_str):
    """Convierte duraciones ISO como 'PT25M01.00S' a minutos float."""
    if not iso_str or not isinstance(iso_str, str):
        return None
    m = _iso_pat.fullmatch(iso_str)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mm = int(m.group(2) or 0)
    ss = float(m.group(3) or 0.0)
    return h*60 + mm + ss/60.0


def mins_mmss_to_float(s):
    """Convierte 'MM:SS' a minutos float."""
    if pd.isna(s):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str) and ":" in s:
        mm, ss = s.split(":")
        return float(mm) + float(ss)/60.0
    try:
        return float(s)
    except:
        return None


def safe_pct(n, d):
    if pd.isna(n) or pd.isna(d) or float(d) == 0.0:
        return None
    return float(n) / float(d)


def boxscore_players_df(game_id: str) -> pd.DataFrame:
    """
    Extrae boxscore de un juego. Intenta LIVE primero, fallback a STATS.
    """
    # Intentar LIVE API
    try:
        bx = live_boxscore.BoxScore(game_id)
        game = bx.game.get_dict()
        rows = []
        for side in ("homeTeam", "awayTeam"):
            team = game.get(side, {})
            tri = team.get("teamTricode")
            for p in team.get("players", []):
                st = p.get("statistics") or {}
                rows.append({
                    "game_id": game.get("gameId"),
                    "NBA_TEAM": tri,
                    "nba_player_id": pd.to_numeric(p.get("personId"), errors="coerce"),
                    "player_name": p.get("name"),
                    "FGM": st.get("fieldGoalsMade"),
                    "FGA": st.get("fieldGoalsAttempted"),
                    "FG%": st.get("fieldGoalsPercentage"),
                    "FTM": st.get("freeThrowsMade"),
                    "FTA": st.get("freeThrowsAttempted"),
                    "FT%": st.get("freeThrowsPercentage"),
                    "3PM": st.get("threePointersMade"),
                    "3PA": st.get("threePointersAttempted"),
                    "3P%": st.get("threePointersPercentage"),
                    "OREB": st.get("reboundsOffensive"),
                    "DREB": st.get("reboundsDefensive"),
                    "REB": st.get("reboundsTotal"),
                    "AST": st.get("assists"),
                    "STL": st.get("steals"),
                    "BLK": st.get("blocks"),
                    "PTS": st.get("points"),
                    "PIP": st.get("pointsInThePaint"),
                    "MIN_iso_calc": st.get("minutesCalculated"),
                    "MIN_iso": st.get("minutes"),
                })
        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("Live boxscore vacío")

        df["MIN"] = df["MIN_iso_calc"].apply(iso_to_minutes).fillna(df["MIN_iso"].apply(iso_to_minutes))
        df = df.drop(columns=[c for c in ("MIN_iso", "MIN_iso_calc") if c in df.columns])

        num_cols = ["FGM", "FGA", "FTM", "FTA", "3PM", "3PA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS", "PIP", "MIN"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        df["FG%"] = df.apply(lambda r: r["FG%"] if pd.notna(r.get("FG%")) else safe_pct(r.get("FGM"), r.get("FGA")), axis=1)
        df["FT%"] = df.apply(lambda r: r["FT%"] if pd.notna(r.get("FT%")) else safe_pct(r.get("FTM"), r.get("FTA")), axis=1)
        df["3P%"] = df.apply(lambda r: r["3P%"] if pd.notna(r.get("3P%")) else safe_pct(r.get("3PM"), r.get("3PA")), axis=1)
        df["PPM"] = df.apply(lambda r: (r["PTS"]/r["MIN"]) if pd.notna(r.get("PTS")) and pd.notna(r.get("MIN")) and r["MIN"]>0 else None, axis=1)

        df["nba_player_id"] = df["nba_player_id"].astype("Int64")
        keep = ["game_id", "NBA_TEAM", "nba_player_id", "player_name",
                "FGM", "FGA", "FG%", "FTM", "FTA", "FT%", "3PM", "3PA", "3P%",
                "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS", "PIP", "PPM", "MIN"]
        return df[[c for c in keep if c in df.columns]]

    except (JSONDecodeError, ValueError):
        pass

    # Fallback: STATS API
    box = stats_box.BoxScoreTraditionalV2(game_id=game_id).player_stats.get_data_frame()
    if box.empty:
        return pd.DataFrame()

    box = box.rename(columns={
        "PLAYER_ID": "nba_player_id",
        "PLAYER_NAME": "player_name",
        "TEAM_ABBREVIATION": "NBA_TEAM",
    })

    keep = ["nba_player_id", "player_name", "NBA_TEAM",
            "MIN", "FGM", "FGA", "FTM", "FTA", "FG3M", "FG3A",
            "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS"]
    box = box[[c for c in keep if c in box.columns]].copy()

    for c in ["FGM", "FGA", "FTM", "FTA", "FG3M", "FG3A", "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS"]:
        if c in box.columns:
            box[c] = pd.to_numeric(box[c], errors="coerce")

    if "MIN" in box.columns:
        box["MIN"] = box["MIN"].apply(mins_mmss_to_float)

    box["FG%"] = box.apply(lambda r: safe_pct(r.get("FGM"), r.get("FGA")), axis=1)
    box["FT%"] = box.apply(lambda r: safe_pct(r.get("FTM"), r.get("FTA")), axis=1)
    box["3PM"] = box.get("FG3M", pd.Series([None]*len(box)))
    box["3PA"] = box.get("FG3A", pd.Series([None]*len(box)))
    box["3P%"] = box.apply(lambda r: safe_pct(r.get("FG3M"), r.get("FG3A")), axis=1)
    box["PIP"] = None
    box["PPM"] = box.apply(lambda r: (r["PTS"]/r["MIN"]) if pd.notna(r.get("PTS")) and pd.notna(r.get("MIN")) and r["MIN"]>0 else None, axis=1)
    box["nba_player_id"] = pd.to_numeric(box["nba_player_id"], errors="coerce").astype("Int64")
    box["game_id"] = game_id

    keep_final = ["game_id", "NBA_TEAM", "nba_player_id", "player_name",
                  "FGM", "FGA", "FG%", "FTM", "FTA", "FT%", "3PM", "3PA", "3P%",
                  "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS", "PIP", "PPM", "MIN"]
    return box[[c for c in keep_final if c in box.columns]]


def daily_stats_by_date(day: date, filter_ids: pd.Series | None = None) -> pd.DataFrame:
    """
    Extrae stats de todos los juegos de un día específico.
    
    Args:
        day: Fecha de los juegos
        filter_ids: IDs de jugadores a filtrar (opcional)
        
    Returns:
        DataFrame con stats de los jugadores
    """
    from fantasyxi.utils.schedule import get_game_ids_for_date
    
    # Obtener juegos del día directamente de la API
    game_ids = get_game_ids_for_date(day)
    
    if not game_ids:
        print(f"⚠️ No hay juegos para {day}")
        return pd.DataFrame()
    
    frames = []
    for gid in game_ids:
        print(f"📥 Extrayendo stats del juego {gid}...")
        df_g = boxscore_players_df(gid)
        if df_g is not None and not df_g.empty:
            frames.append(df_g)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    if "nba_player_id" in df.columns:
        df["nba_player_id"] = pd.to_numeric(df["nba_player_id"], errors="coerce").astype("Int64")

    if filter_ids is not None:
        ids = pd.to_numeric(pd.Series(filter_ids), errors="coerce").astype("Int64").dropna().unique()
        df = df[df["nba_player_id"].isin(ids)]

    keep = ["game_id", "NBA_TEAM", "nba_player_id", "player_name",
            "FGM", "FGA", "FG%", "FTM", "FTA", "FT%", "3PM", "3PA", "3P%",
            "OREB", "DREB", "REB", "AST", "STL", "BLK", "PTS", "PIP", "PPM", "MIN"]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()

    sort_cols = [c for c in ["PTS", "REB", "AST"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=[False]*len(sort_cols))

    return df.reset_index(drop=True)