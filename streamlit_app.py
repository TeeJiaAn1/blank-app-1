import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import matplotlib.ticker as ticker

# --- PAGE CONFIG ---
st.set_page_config(page_title="HPSI- Badminton PDF Report", layout="wide")

# --- GLOBAL COLORS ---
col_work = "#F5EDC8"
col_player = "#FFA600"
col_opponent = "#2C3E50"
col_forced = "#2E8B57"


# --- PDF TEXT SANITIZER FOR PYFPDF / LATIN-1 ---
def safe_pdf_text(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("≤", "<=")
        .replace("≥", ">=")
        .replace("–", "-")
        .replace("—", "-")
        .replace("•", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


# --- PDF CLASS DEFINITION ---
class BadmintonReport(FPDF):
    def __init__(self, title_line1, title_line2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title_line1 = safe_pdf_text(title_line1)
        self.title_line2 = safe_pdf_text(title_line2)

    def header(self):
        if self.page_no() == 1:
            self.set_fill_color(44, 62, 80)
            self.rect(0, 0, 210, 40, 'F')
            self.set_text_color(255, 255, 255)

            max_width = 190

            font_size_1 = 15
            self.set_font("Arial", 'B', font_size_1)
            while self.get_string_width(self.title_line1) > max_width and font_size_1 > 6:
                font_size_1 -= 0.5
                self.set_font("Arial", 'B', font_size_1)
            self.cell(0, 10, self.title_line1, ln=True, align='C')

            font_size_2 = 15
            self.set_font("Arial", 'B', font_size_2)
            while self.get_string_width(self.title_line2) > max_width and font_size_2 > 6:
                font_size_2 -= 0.5
                self.set_font("Arial", 'B', font_size_2)
            self.cell(0, 10, self.title_line2, ln=True, align='C')

            self.set_font("Arial", size=11)
            self.cell(0, 5, safe_pdf_text(f"Prepared on: {datetime.now().strftime('%d-%m-%Y')}"), ln=True, align='C')
            self.ln(20)

    def section_title(self, title):
        self.set_x(10)
        self.set_font("Arial", 'B', 15)
        self.set_text_color(44, 62, 80)
        self.cell(0, 10, safe_pdf_text(title.upper()), ln=True)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def quick_table(self, header, data, col_widths):
        base_font_size = 10

        self.set_font("Arial", 'B', base_font_size)
        self.set_fill_color(230, 230, 230)
        for i, h in enumerate(header):
            self.cell(col_widths[i], 7, safe_pdf_text(h), border=1, fill=True, align='C')
        self.ln()

        self.set_text_color(0, 0, 0)
        for row in data:
            for i, item in enumerate(row):
                text = safe_pdf_text(item)
                cell_width = col_widths[i]

                current_font_size = base_font_size
                self.set_font("Arial", size=current_font_size)

                while self.get_string_width(text) > (cell_width - 2) and current_font_size > 5:
                    current_font_size -= 0.5
                    self.set_font("Arial", size=current_font_size)

                self.cell(cell_width, 7, text, border=1, align='C')
                self.set_font("Arial", size=base_font_size)
            self.ln()
        self.ln(5)


# --- ANALYTICS ENGINE ---
def analyze_match(df, p_name, o_name):
    df = df.copy()
    df['Name'] = df['Name'].astype(str).str.replace(r" \(\d+\)", "", regex=True)
    relevant = ["Player Serve", "Opponent Serve", "End Rally"]
    df = df[df['Name'].isin(relevant)].sort_values('Position').reset_index(drop=True)

    rallies = []
    current_p_score = 0
    current_o_score = 0
    current_set_label = ""

    for i in range(len(df)):
        name_i = df.iloc[i]['Name']
        set_i = df.iloc[i]['Period']

        if set_i != current_set_label:
            current_p_score, current_o_score = 0, 0
            current_set_label = set_i

        if "Serve" not in name_i:
            continue

        next_events = df.iloc[i + 1:]
        end_rally_search = next_events[next_events['Name'] == "End Rally"]

        if not end_rally_search.empty:
            end_row_idx = end_rally_search.index[0]
            end_row = df.loc[end_row_idx]

            duration = (end_row['Position'] + 2000 - df.iloc[i]['Position']) / 1000
            server_side = "Player" if "Player" in name_i else "Opponent"

            winner = None
            after_end = df.iloc[end_row_idx + 1:]
            next_serve_search = after_end[after_end['Name'].str.contains("Serve", na=False)]

            if not next_serve_search.empty:
                next_serve_name = next_serve_search.iloc[0]['Name']
                next_server_side = "Player" if "Player" in next_serve_name else "Opponent"

                if server_side == next_server_side:
                    winner = server_side
                else:
                    winner = "Opponent" if server_side == "Player" else "Player"
            else:
                if current_p_score > current_o_score:
                    winner = "Player"
                elif current_o_score > current_p_score:
                    winner = "Opponent"
                else:
                    winner = server_side

            score_diff = abs(current_p_score - current_o_score)
            is_pressure = (score_diff <= 1) or (current_p_score >= 20) or (current_o_score >= 20)

            rallies.append({
                "Set": current_set_label,
                "Rally_Num": len([r for r in rallies if r['Set'] == current_set_label]) + 1,
                "Server": server_side,
                "Winner": winner,
                "Duration": duration,
                "Start_Pos": df.iloc[i]['Position'],
                "End_Pos": end_row['Position'] + 2000,
                "Cat": "Short" if duration < 7 else ("Mid" if duration <= 15 else "Long"),
                "Is_Pressure": is_pressure,
                "P_Score_Before": current_p_score,
                "O_Score_Before": current_o_score,
                "Error_Type": end_row.get('Error Type', None),
                "Landing_Position": end_row.get('Landing Position', None),
                "Landing_Zone": end_row.get('Landing Zone', None),
                "Player_Position": end_row.get('Player Position', None),
                "Player_Zone": end_row.get('Player Zone', None),
                "Racket_Face": end_row.get('Racket Face', None),
                "Shot_Profile": end_row.get('Shot Court Profile', None),
                "Shot_Type": end_row.get('Shot Type', None)
            })

            if winner == "Player":
                current_p_score += 1
            else:
                current_o_score += 1

    rdf = pd.DataFrame(rallies)
    if rdf.empty:
        return rdf

    rdf['Rest'] = (rdf.groupby('Set')['Start_Pos'].shift(-1) - rdf['End_Pos']) / 1000
    rdf['Ratio'] = rdf['Duration'] / rdf['Rest']

    return rdf


def compute_error_stats(rdf):
    err_df = rdf[rdf['Error_Type'].notna()].copy()

    def side_committed_error(row):
        if row['Winner'] == 'Player':
            return 'Opponent'
        elif row['Winner'] == 'Opponent':
            return 'Player'
        return None

    if err_df.empty:
        return {
            'err_counts': pd.DataFrame(columns=['Error_Side', 'Error_Type', 'Count']),
            'shot_type_counts': pd.DataFrame(columns=['Error_Side', 'Error_Type', 'Shot_Type', 'Count']),
            'zone_counts': pd.DataFrame(columns=['Error_Side', 'Error_Type', 'Player_Zone', 'Count']),
            'landing_zone_counts': pd.DataFrame(columns=['Error_Side', 'Error_Type', 'Landing_Zone', 'Count']),
            'crit_counts': pd.DataFrame(columns=['Error_Side', 'Error_Type', 'Count']),
            'streak_df': pd.DataFrame(),
            'max_streaks': None
        }

    err_df['Error_Side'] = err_df.apply(side_committed_error, axis=1)

    err_counts = err_df.groupby(['Error_Side', 'Error_Type']).size().reset_index(name='Count')
    shot_type_counts = err_df.groupby(['Error_Side', 'Error_Type', 'Shot_Type']).size().reset_index(name='Count')
    zone_counts = err_df.groupby(['Error_Side', 'Error_Type', 'Player_Zone']).size().reset_index(name='Count')
    landing_zone_counts = err_df.groupby(['Error_Side', 'Error_Type', 'Landing_Zone']).size().reset_index(name='Count')

    err_df['Score_Diff'] = (err_df['P_Score_Before'] - err_df['O_Score_Before']).abs()
    err_df['Is_Critical'] = (
        (err_df['Score_Diff'] <= 1) |
        (err_df['P_Score_Before'] >= 18) |
        (err_df['O_Score_Before'] >= 18)
    )

    crit_counts = err_df[err_df['Is_Critical']].groupby(['Error_Side', 'Error_Type']).size().reset_index(name='Count')

    streak_rows = []
    for side in ['Player', 'Opponent']:
        side_df = err_df.sort_values(['Set', 'Rally_Num']).copy()
        side_df['Is_Unforced_By_Side'] = (
            (side_df['Error_Side'] == side) &
            (side_df['Error_Type'] == 'Unforced Error')
        )

        current_streak = 0
        last_set = None

        for _, row in side_df.iterrows():
            if row['Set'] != last_set:
                current_streak = 0
                last_set = row['Set']

            if row['Is_Unforced_By_Side']:
                current_streak += 1
                streak_rows.append({
                    'Side': side,
                    'Set': row['Set'],
                    'Rally_Num': row['Rally_Num'],
                    'Streak_Length': current_streak
                })
            else:
                current_streak = 0

    streak_df = pd.DataFrame(streak_rows)
    max_streaks = None
    if not streak_df.empty:
        max_streaks = streak_df.groupby('Side')['Streak_Length'].max().reset_index()

    return {
        'err_counts': err_counts,
        'shot_type_counts': shot_type_counts,
        'zone_counts': zone_counts,
        'landing_zone_counts': landing_zone_counts,
        'crit_counts': crit_counts,
        'streak_df': streak_df,
        'max_streaks': max_streaks
    }

def compute_unforced_point_contribution(rdf):
    if rdf.empty:
        return pd.DataFrame(columns=[
            'Side',
            'Total_Points_Won',
            'Points_From_Opp_Unforced',
            'Own_Points',
            'Pct_From_Opp_Unforced',
            'Pct_Own_Points'
        ])

    total_points = (
        rdf.groupby('Winner')
        .size()
        .reindex(['Player', 'Opponent'], fill_value=0)
        .reset_index(name='Total_Points_Won')
        .rename(columns={'Winner': 'Side'})
    )

    unforced_points = (
        rdf[rdf['Error_Type'] == 'Unforced Error']
        .groupby('Winner')
        .size()
        .reindex(['Player', 'Opponent'], fill_value=0)
        .reset_index(name='Points_From_Opp_Unforced')
        .rename(columns={'Winner': 'Side'})
    )

    summary = total_points.merge(unforced_points, on='Side', how='left')
    summary['Points_From_Opp_Unforced'] = summary['Points_From_Opp_Unforced'].fillna(0).astype(int)

    summary['Own_Points'] = summary['Total_Points_Won'] - summary['Points_From_Opp_Unforced']

    summary['Pct_From_Opp_Unforced'] = np.where(
        summary['Total_Points_Won'] > 0,
        (summary['Points_From_Opp_Unforced'] / summary['Total_Points_Won']) * 100,
        0
    )

    summary['Pct_Own_Points'] = np.where(
        summary['Total_Points_Won'] > 0,
        (summary['Own_Points'] / summary['Total_Points_Won']) * 100,
        0
    )

    return summary

# --- MAIN INTERFACE ---
st.title("HPSI Badminton Analytics- PDF Report Generation")

with st.sidebar:
    st.header("Match Metadata")
    event = st.text_input("Event", "YONEX German Open 2026")
    date_str = st.date_input("Date", datetime(2026, 2, 26))
    venue = st.text_input("Venue", "Germany")
    round_m = st.text_input("Round", "R16")
    p_name = st.text_input("Player Name", "YEO Jia Min")
    o_name = st.text_input("Opponent Name", "HAN Qian Xi")

uploaded_file = st.file_uploader("Upload DartFish CSV", type="csv")

rdf = None
raw_df = None

if uploaded_file:
    try:
        raw_df = pd.read_csv(uploaded_file)
        rdf = analyze_match(raw_df, p_name, o_name)
        if rdf is not None and not rdf.empty:
            st.success("CSV uploaded and rally data processed.")
            st.write(f"Processed rallies: {len(rdf)}")
        else:
            st.warning("CSV uploaded, but no valid rallies were reconstructed. Check tag names and columns.")
    except Exception as e:
        st.error(f"Failed to read/process CSV: {e}")
else:
    st.info("Please upload your DartFish CSV.")

if rdf is not None and not rdf.empty:
    if st.button("Generate Full PDF Report"):
        try:
            date_formatted = date_str.strftime("%d %b %Y")
            line1 = f"{date_formatted} | {event} | {round_m}"
            line2 = f"{p_name} vs {o_name}"

            pdf = BadmintonReport(title_line1=line1, title_line2=line2)
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # --- 1. EVENT SUMMARY ---
            pdf.section_title("Event Summary")
            total_duration_seconds = (rdf['End_Pos'].max() - rdf['Start_Pos'].min()) / 1000
            duration_str = f"{int(total_duration_seconds // 60)} min {int(total_duration_seconds % 60)} sec"

            set_stats = rdf.groupby('Set').agg({
                'P_Score_Before': 'max',
                'O_Score_Before': 'max',
                'Winner': 'last'
            })

            final_scores = []
            for _, row in set_stats.iterrows():
                p_final = int(row['P_Score_Before'] + (1 if row['Winner'] == 'Player' else 0))
                o_final = int(row['O_Score_Before'] + (1 if row['Winner'] == 'Opponent' else 0))
                final_scores.append(f"{p_final}-{o_final}")

            p_sets = sum(1 for s in final_scores if int(s.split('-')[0]) > int(s.split('-')[1]))
            match_winner = p_name if p_sets > (len(final_scores) / 2) else o_name
            match_vs = f"{p_name} vs {o_name}"

            summary_table = [
                ["Date", str(date_str)],
                ["Event", event],
                ["Round", round_m],
                ["Match", match_vs],
                ["Venue", venue],
                ["Winner", match_winner],
                ["Final Score", ", ".join(final_scores)],
                ["Duration", duration_str]
            ]
            pdf.quick_table(["Variable", "Value"], summary_table, [50, 100])

            # --- 2. OVERALL MATCH SUMMARY ---
            pdf.section_title("Overall Match Summary")
            avg_rally = rdf['Duration'].mean()
            valid_rest = rdf[rdf['Rest'] > 0.1]['Rest']
            avg_rest = valid_rest.mean() if not valid_rest.empty else 0
            dist = rdf['Cat'].value_counts(normalize=True) * 100

            overall_table = [
                ["Total Points Played", len(rdf)],
                ["Avg Rally Duration (s)", f"{avg_rally:.1f}"],
                ["Avg Rest Duration (s)", f"{avg_rest:.1f}"],
                ["Work:Rest Ratio", f"1 : {avg_rest / avg_rally:.1f}" if avg_rally > 0 else "N/A"],
                ["Short/Mid/Long %", f"{dist.get('Short', 0):.0f}% / {dist.get('Mid', 0):.0f}% / {dist.get('Long', 0):.0f}%"]
            ]
            pdf.quick_table(["Metric", "Value"], overall_table, [80, 60])

            # --- 3. PLAYER MATCH SUMMARY ---
            pdf.section_title("Player Match Summary")

            def get_p_stats(side):
                win_sub = rdf[rdf['Winner'] == side]
                serve_sub = rdf[rdf['Server'] == side]
                pres_sub = rdf[rdf['Is_Pressure'] == True]
                p_wins = len(win_sub)
                p_rally = win_sub['Duration'].mean() if not win_sub.empty else 0.0
                p_rest = win_sub['Rest'].mean() if not win_sub.empty else 0.0
                s_wins = len(serve_sub[serve_sub['Winner'] == side])
                s_display = f"{(s_wins / len(serve_sub) * 100):.0f}% ({s_wins})" if len(serve_sub) > 0 else "0% (0)"
                pr_wins = len(pres_sub[pres_sub['Winner'] == side])
                pr_display = f"{(pr_wins / len(pres_sub) * 100):.0f}% ({pr_wins})" if len(pres_sub) > 0 else "0% (0)"
                dist_str = "0% / 0% / 0%"
                if not win_sub.empty:
                    d = win_sub['Cat'].value_counts(normalize=True) * 100
                    dist_str = f"{d.get('Short', 0):.0f}% / {d.get('Mid', 0):.0f}% / {d.get('Long', 0):.0f}%"
                return p_wins, p_rally, p_rest, s_display, pr_display, dist_str

            p_v = get_p_stats("Player")
            o_v = get_p_stats("Opponent")

            player_table = [
                ["Total Points Won %", f"{p_v[0] / len(rdf) * 100:.1f}% ({p_v[0]})", f"{o_v[0] / len(rdf) * 100:.1f}% ({o_v[0]})"],
                ["Avg Rally Duration (s)", f"{p_v[1]:.1f}", f"{o_v[1]:.1f}"],
                ["Avg Rest Duration (s)", f"{p_v[2]:.1f}", f"{o_v[2]:.1f}"],
                ["Work:Rest Ratio", f"1 : {p_v[2] / p_v[1]:.1f}" if p_v[1] > 0 else "N/A", f"1 : {o_v[2] / o_v[1]:.1f}" if o_v[1] > 0 else "N/A"],
                ["Serve Win %", p_v[3], o_v[3]],
                ["Pressure Points Won %", p_v[4], o_v[4]],
                ["Short/Mid/Long (%) distribution", p_v[5], o_v[5]]
            ]
            pdf.quick_table(["Metric", p_name, o_name], player_table, [70, 60, 60])

            # --- 4. SERVE STATISTICS SUMMARY ---
            pdf.add_page()
            pdf.section_title("Serve Statistics Summary")

            def get_serve_summary_text(side_label, side_name):
                subset = rdf[rdf['Server'] == side_label]
                total = len(subset)
                if total == 0:
                    return f"{side_name} Serves: 0"
                p_wins = len(subset[subset['Winner'] == 'Player'])
                o_wins = len(subset[subset['Winner'] == 'Opponent'])
                p_pct = (p_wins / total) * 100
                o_pct = (o_wins / total) * 100
                return (
                    f"{side_name} Serves: {total}\n"
                    f"- {p_pct:.0f}% ({p_wins}) won by {p_name}\n"
                    f"- {o_pct:.0f}% ({o_wins}) won by {o_name}"
                )

            pdf.set_font("Arial", 'B', 10)
            pdf.set_x(10)
            pdf.multi_cell(190, 6, safe_pdf_text(get_serve_summary_text("Player", p_name)))
            pdf.ln(3)
            pdf.set_x(10)
            pdf.multi_cell(190, 6, safe_pdf_text(get_serve_summary_text("Opponent", o_name)))
            pdf.ln(5)

            fig_serve, ax_serve = plt.subplots(figsize=(8, 5))
            serve_counts = rdf.groupby(['Server', 'Winner']).size().reset_index(name='counts')
            serve_totals = rdf.groupby('Server').size().reset_index(name='totals')
            serve_plot_data = serve_counts.merge(serve_totals, on='Server')
            serve_plot_data['pct'] = (serve_plot_data['counts'] / serve_plot_data['totals']) * 100

            serve_plot_data['Server'] = serve_plot_data['Server'].map({'Player': p_name, 'Opponent': o_name})
            serve_plot_data['Winner'] = serve_plot_data['Winner'].map({'Player': p_name, 'Opponent': o_name})
            serve_totals['Server'] = serve_totals['Server'].map({'Player': p_name, 'Opponent': o_name})

            server_order = [p_name, o_name]
            color_map = {p_name: '#FFA600', o_name: '#2C3E50'}

            sns.barplot(
                data=serve_plot_data,
                x='Server',
                y='pct',
                hue='Winner',
                hue_order=[o_name, p_name],
                order=server_order,
                ax=ax_serve,
                palette=color_map
            )

            for p in ax_serve.patches:
                height = p.get_height()
                if height > 0:
                    idx = int(round(p.get_x() + p.get_width() / 2.0))
                    if 0 <= idx < len(server_order):
                        server_name = server_order[idx]
                        total = serve_totals[serve_totals['Server'] == server_name]['totals'].values[0]
                        count = int(round((height / 100) * total))
                        ax_serve.text(
                            p.get_x() + p.get_width() / 2.,
                            height / 2,
                            f'{height:.0f}% ({count})',
                            ha='center',
                            va='center',
                            color='white',
                            fontweight='bold',
                            fontsize=9
                        )

            ax_serve.set_title("Serve Outcome Breakdown", fontsize=14)
            ax_serve.set_xlabel("")
            ax_serve.set_ylabel("Percentage of Points Won (%)")
            ax_serve.set_ylim(0, 110)
            ax_serve.legend(title="Won By:", loc='upper right')

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
                pdf.image(tmp.name, x=30, w=150)
                os.remove(tmp.name)
            plt.close()

            # --- 4.1 RALLY STATISTICS SUMMARY ---
            pdf.add_page()
            pdf.section_title("Rally Statistics Summary")

            pdf.set_font("Arial", 'I', 10)
            pdf.set_x(10)
            pdf.cell(190, 10, safe_pdf_text("Rally Categories: Short (<7s), Mid (7-15s), Long (>15s)"), ln=True)
            pdf.ln(5)

            fig_dist, ax_dist = plt.subplots(figsize=(8, 4))
            rdf['Cat'] = pd.Categorical(rdf['Cat'], categories=['Short', 'Mid', 'Long'], ordered=True)
            cat_counts = rdf['Cat'].value_counts(sort=False)
            cat_pcts = (cat_counts / len(rdf)) * 100

            bars = ax_dist.bar(cat_counts.index.astype(str), cat_pcts, color='#2C3E50', width=0.6)
            ax_dist.set_title("Rally Length Distribution", fontweight='bold')
            ax_dist.set_ylabel("Percentage of Rallies (%)")
            ax_dist.set_ylim(0, max(cat_pcts) + 15 if len(cat_pcts) > 0 else 100)

            for i, bar in enumerate(bars):
                height = bar.get_height()
                count = cat_counts.iloc[i]
                ax_dist.text(
                    bar.get_x() + bar.get_width() / 2.,
                    height + 1,
                    f'{height:.0f}% ({count})',
                    ha='center',
                    va='bottom',
                    fontweight='bold'
                )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
                pdf.image(tmp.name, x=30, w=150)
                os.remove(tmp.name)
            plt.close()
            pdf.ln(10)

            fig_win_cat, ax_win_cat = plt.subplots(figsize=(8, 5))
            win_cat_counts = rdf.groupby(['Cat', 'Winner']).size().unstack(fill_value=0)

            for col in ['Opponent', 'Player']:
                if col not in win_cat_counts.columns:
                    win_cat_counts[col] = 0

            win_cat_counts = win_cat_counts[['Opponent', 'Player']]
            win_cat_totals = win_cat_counts.sum(axis=1)
            win_cat_props = win_cat_counts.div(win_cat_totals, axis=0).mul(100)
            win_cat_props = win_cat_props.reindex(['Short', 'Mid', 'Long'])

            win_cat_props.columns = [o_name, p_name]
            win_cat_counts.columns = [o_name, p_name]

            win_cat_props.plot(
                kind='bar',
                stacked=True,
                ax=ax_win_cat,
                color=['#2C3E50', '#FFA600']
            )

            for i, (idx, row) in enumerate(win_cat_props.iterrows()):
                cumulative_height = 0
                for winner in win_cat_props.columns:
                    val = row[winner]
                    if val > 0:
                        count = int(win_cat_counts.loc[idx, winner])
                        ax_win_cat.text(
                            i,
                            cumulative_height + (val / 2),
                            f"{val:.0f}% ({count})",
                            ha='center',
                            va='center',
                            color='white',
                            fontweight='bold',
                            fontsize=8
                        )
                    cumulative_height += val

            ax_win_cat.set_title("Win % by Rally Category", fontweight='bold')
            ax_win_cat.set_ylabel("Win Percentage (%)")
            ax_win_cat.set_xlabel("Rally Category")
            ax_win_cat.legend(title="Won By:", loc='upper right')
            plt.xticks(rotation=0)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
                pdf.image(tmp.name, x=30, w=150)
                os.remove(tmp.name)
            plt.close()

            # --- 4.2 ERROR STATISTICS SUMMARY ---
            pdf.add_page()
            pdf.section_title("Error Statistics Summary")

            error_stats = compute_error_stats(rdf)
            err_counts = error_stats['err_counts']
            shot_type_counts = error_stats['shot_type_counts']
            zone_counts = error_stats['zone_counts']
            crit_counts = error_stats['crit_counts']
            max_streaks = error_stats['max_streaks']

            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Error Type by Side Committing Error"), ln=True)

            def get_error_count(side, etype):
                sub = err_counts[
                    (err_counts['Error_Side'] == side) &
                    (err_counts['Error_Type'] == etype)
                ]
                return int(sub['Count'].iloc[0]) if not sub.empty else 0

            table_data = [
                [
                    "Unforced Error",
                    get_error_count("Player", "Unforced Error"),
                    get_error_count("Opponent", "Unforced Error")
                ],
                [
                    "Forced Error",
                    get_error_count("Player", "Forced Error"),
                    get_error_count("Opponent", "Forced Error")
                ]
            ]

            pdf.quick_table(
                ["Metric", p_name, o_name],
                table_data,
                [55, 42, 42]
            )

            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Unforced Errors in Critical Moments (score diff <=1 or >=18 points)"), ln=True)

            def get_critical_unforced_count(side):
                sub = crit_counts[
                    (crit_counts['Error_Side'] == side) &
                    (crit_counts['Error_Type'] == 'Unforced Error')
                ]
                return int(sub['Count'].iloc[0]) if not sub.empty else 0

            crit_table = [
                [
                    "Unforced Error in Critical Moment",
                    get_critical_unforced_count("Player"),
                    get_critical_unforced_count("Opponent")
                ]
            ]

            pdf.quick_table(
                ["Metric", p_name, o_name],
                crit_table,
                [55, 42, 42]
            )
            
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Points Won from Opponent Unforced Errors"), ln=True)

            unforced_contrib = compute_unforced_point_contribution(rdf)

            contrib_table = []
            for _, row in unforced_contrib.iterrows():
                side_name = p_name if row['Side'] == 'Player' else o_name
                contrib_table.append([
                    side_name,
                    int(row['Total_Points_Won']),
                    int(row['Own_Points']),
                    int(row['Points_From_Opp_Unforced']),
                    f"{row['Pct_Own_Points']:.1f}%",
                    f"{row['Pct_From_Opp_Unforced']:.1f}%"
                ])

            pdf.quick_table(
                ["Player", "Total Points Won", "Own Points", "Points from Opp. UFE", "% Own Points", "% from Opp. UFE"],
                contrib_table,
                [32, 32, 25, 42, 26, 30]
            )

            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Unforced Errors by Shot Type"), ln=True)

            sub_shot = shot_type_counts[shot_type_counts['Error_Type'] == 'Unforced Error'].copy()

            if not sub_shot.empty:
                sub_shot['Shot_Type'] = sub_shot['Shot_Type'].fillna("Unknown")

                shot_pivot = (
                    sub_shot
                    .pivot_table(
                        index='Shot_Type',
                        columns='Error_Side',
                        values='Count',
                        aggfunc='sum',
                        fill_value=0
                    )
                    .reindex(columns=['Player', 'Opponent'], fill_value=0)
                    .reset_index()
                )

                preferred_order = [
                    'Full Smash', 'Serve Won', 'Serve Loss', 'Half Smash',
                    'Drop', 'Net', 'NetKill', 'Drive', 'Block',
                    'Clear', 'Lift', 'Let', 'Unknown'
                ]

                present_types = shot_pivot['Shot_Type'].tolist()
                ordered_types = [x for x in preferred_order if x in present_types]
                remaining_types = [x for x in present_types if x not in ordered_types]
                final_order = ordered_types + sorted(remaining_types)

                shot_pivot['Shot_Type'] = pd.Categorical(
                    shot_pivot['Shot_Type'],
                    categories=final_order,
                    ordered=True
                )
                shot_pivot = shot_pivot.sort_values('Shot_Type')

                shot_table = []
                for _, row in shot_pivot.iterrows():
                    player_val = int(row['Player']) if row['Player'] > 0 else "-"
                    opponent_val = int(row['Opponent']) if row['Opponent'] > 0 else "-"

                    shot_table.append([
                        row['Shot_Type'],
                        player_val,
                        opponent_val
                    ])

                pdf.quick_table(
                    ["Shot Type", p_name, o_name],
                    shot_table,
                    [55, 42, 42]
                )

            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Unforced Errors by Player Court Zone"), ln=True)

            sub_zone = zone_counts[zone_counts['Error_Type'] == 'Unforced Error'].copy()

            if not sub_zone.empty:
                sub_zone['Player_Zone'] = sub_zone['Player_Zone'].fillna("Unknown")

                zone_pivot = (
                    sub_zone
                    .pivot_table(
                        index='Player_Zone',
                        columns='Error_Side',
                        values='Count',
                        aggfunc='sum',
                        fill_value=0
                    )
                    .reindex(columns=['Player', 'Opponent'], fill_value=0)
                    .reset_index()
                )

                zone_table = []
                for _, row in zone_pivot.iterrows():
                    player_val = int(row['Player']) if row['Player'] > 0 else "-"
                    opponent_val = int(row['Opponent']) if row['Opponent'] > 0 else "-"

                    zone_table.append([
                        row['Player_Zone'],
                        player_val,
                        opponent_val
                    ])

                pdf.quick_table(
                    ["Player Zone", p_name, o_name],
                    zone_table,
                    [55, 42, 42]
                )

            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, safe_pdf_text("Longest Streaks of Consecutive Unforced Errors"), ln=True)
            streak_table = []
            if max_streaks is not None:
                for _, row in max_streaks.iterrows():
                    streak_table.append([row['Side'], int(row['Streak_Length'])])
            if streak_table:
                pdf.quick_table(["Side", "Max Consecutive Unforced Errors"], streak_table, [70, 60])

            fig_err, ax_err = plt.subplots(figsize=(4, 3))
            unforced_by_side = err_counts[err_counts['Error_Type'] == 'Unforced Error']
            if not unforced_by_side.empty:
                colors = [col_player if side == "Player" else col_opponent for side in unforced_by_side['Error_Side']]
                ax_err.bar(unforced_by_side['Error_Side'], unforced_by_side['Count'], color=colors)
                ax_err.set_title("Total Unforced Errors by Side")
                ax_err.set_ylabel("Count")
                for i, v in enumerate(unforced_by_side['Count']):
                    ax_err.text(i, v + 0.2, str(int(v)), ha='center', va='bottom')

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
                    pdf.image(tmp.name, x=40, w=120)
                    os.remove(tmp.name)
            plt.close()

            # --- 5. POINT PROGRESSION & LOAD PER SET ---
            pdf.add_page()
            pdf.section_title("Point Progression & Load per Set")

            set_list = list(rdf['Set'].unique())

            for idx_set, s_name in enumerate(set_list):
                if idx_set != 0:
                    pdf.add_page()

                digits = ''.join(filter(str.isdigit, str(s_name)))
                clean_set_title = f"Set {digits}" if digits else safe_pdf_text(str(s_name))
                s_df = rdf[rdf['Set'] == s_name].copy().sort_values('Start_Pos')

                stats_data = s_df[(s_df['Rest'] > 0.1) & (s_df['Rest'] < 45)].copy()

                if not stats_data.empty:
                    load_rows = [
                        ["Work Duration (s)", f"{stats_data['Duration'].max():.1f}", f"{stats_data['Duration'].min():.1f}", f"{stats_data['Duration'].mean():.1f}"],
                        ["Rest Duration (s)", f"{stats_data['Rest'].max():.1f}", f"{stats_data['Rest'].min():.1f}", f"{stats_data['Rest'].mean():.1f}"],
                        ["Work:Rest Ratio (1:X)", f"1 : {stats_data['Ratio'].min():.1f}", f"1 : {stats_data['Ratio'].max():.1f}", f"1 : {stats_data['Ratio'].mean():.1f}"]
                    ]
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 10, safe_pdf_text(f"Load Statistics (Rest Intervals Excluded) - {clean_set_title}"), ln=True)
                    pdf.quick_table(["Metric", "Max", "Min", "Mean"], load_rows, [50, 35, 35, 30])

                set_start_ms = s_df['Start_Pos'].min()
                s_df['Start_Rel'] = (s_df['Start_Pos'] - set_start_ms) / 1000
                s_df['End_Rel'] = (s_df['End_Pos'] - set_start_ms) / 1000
                s_df['P_Cum'] = (s_df['Winner'] == 'Player').cumsum()
                s_df['O_Cum'] = (s_df['Winner'] == 'Opponent').cumsum()

                fig, ax = plt.subplots(figsize=(10, 5))

                for _, rally in s_df.iterrows():
                    ax.axvspan(rally['Start_Rel'], rally['End_Rel'], color=col_work, alpha=0.5)

                x_steps = [0] + list(s_df['End_Rel'])
                p_steps = [0] + list(s_df['P_Cum'])
                o_steps = [0] + list(s_df['O_Cum'])

                ax.step(x_steps, p_steps, where='post', color=col_player, linewidth=2, label=p_name)
                ax.step(x_steps, o_steps, where='post', color=col_opponent, linewidth=2, label=o_name)

                # Always show the actual gained point.
                # Forced error -> winner point label green.
                # Unforced error -> winner point label remains visible, plus a red "x" on loser side.
                for _, row in s_df.iterrows():
                    x_pos = row['End_Rel']
                    winner = row['Winner']
                    error_type = row.get('Error_Type', None)

                    if winner == 'Player':
                        winner_score_val = int(row['P_Score_Before'] + 1)
                        loser_score_val = int(row['O_Score_Before'])
                        winner_color_default = col_player
                    else:
                        winner_score_val = int(row['O_Score_Before'] + 1)
                        loser_score_val = int(row['P_Score_Before'])
                        winner_color_default = col_opponent

                    if error_type == 'Forced Error':
                        winner_label_color = col_forced
                    else:
                        winner_label_color = winner_color_default

                    ax.text(
                        x_pos,
                        winner_score_val + 0.6,
                        str(winner_score_val),
                        color=winner_label_color,
                        fontsize=7,
                        fontweight='bold',
                        ha='center'
                    )

                    if error_type == 'Unforced Error':
                        ax.text(
                            x_pos,
                            loser_score_val + 0.2,
                            "x",
                            color='red',
                            fontsize=9,
                            fontweight='bold',
                            ha='center'
                        )

                ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{int(x//60):02d}:{int(x%60):02d}"))
                ax.set_title(f"Point Progression Timeline - {clean_set_title}", fontsize=12, fontweight='bold')
                ax.set_xlabel("Time in Set (mm:ss)")
                ax.set_ylabel("Points")
                ax.legend(loc='lower right', fontsize=9)
                ax.grid(axis='y', alpha=0.3)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
                    pdf.image(tmp.name, x=10, w=190)
                    os.remove(tmp.name)
                plt.close()
                pdf.ln(10)

            # --- 6. TOP 10 TOUGHEST RALLIES ---
            pdf.add_page()
            pdf.section_title("Top 10 Toughest Rallies (by Work:Rest Ratio)")
            set_totals = rdf.groupby('Set').size().to_dict()
            toughest_df = rdf[rdf['Ratio'].notna()].copy()
            top_10 = toughest_df.sort_values('Ratio', ascending=False).head(10).reset_index(drop=True)

            toughest_table_data = []
            for i, row in top_10.iterrows():
                digits = ''.join(filter(str.isdigit, str(row['Set'])))
                set_label = f"Set {digits}" if digits else safe_pdf_text(str(row['Set']))
                rally_label = f"{int(row['Rally_Num'])}/{set_totals.get(row['Set'], 0)}"
                score_before = f"{int(row['P_Score_Before'])}-{int(row['O_Score_Before'])}"
                toughest_table_data.append([
                    i + 1,
                    set_label,
                    rally_label,
                    f"{row['Ratio']:.2f}",
                    f"{row['Duration']:.1f}",
                    f"{row['Rest']:.1f}",
                    score_before
                ])

            pdf.quick_table(
                ["No.", "Set #", "Rally #", "W:R Ratio", "Work (s)", "Rest (s)", "Score Before"],
                toughest_table_data,
                [10, 25, 25, 30, 25, 25, 50]
            )
            pdf.set_font("Arial", 'I', 9)
            pdf.multi_cell(0, 5, safe_pdf_text("Note: A larger W:R ratio represents a higher intensity rally (more work per unit of rest)."))
            pdf.ln(10)

            # --- 7. NOTES ---
            pdf.section_title("NOTES: Methodology & Data Assumptions")
            pdf.set_font("Arial", size=10)

            methodology_text = (
                "Rally Construction: Rallies were reconstructed using the time stamp (Position) of the Serve and End Rally tags. "
                "A 2000ms (2-second) buffer was added to the End Rally time stamp to account for the shuttle being in play "
                "before the tag was registered.\n\n"
                "Winner Logic: The winner of each rally was inferred based on the service flow. If the server retained the "
                "service for the subsequent point, they were deemed the winner; if the service changed hands, the receiver "
                "was deemed the winner.\n\n"
                "Rest Time: Defined as the duration between the end of one rally (including the buffer) and the start of the "
                "next serve. Calculations exclude values of zero or technical intervals (>45s) to prevent skewed statistics.\n\n"
                "Pressure Points: Defined as rallies where the score difference was <=1 point, or where the score of either "
                "player exceeded 20 points."
            )
            pdf.multi_cell(0, 8, safe_pdf_text(methodology_text))

            # --- FINALIZE ---
            date_file = date_str.strftime("%Y%m%d")

            p_sets_won = 0
            o_sets_won = 0
            for s in final_scores:
                p_final = int(s.split('-')[0])
                o_final = int(s.split('-')[1])
                if p_final > o_final:
                    p_sets_won += 1
                else:
                    o_sets_won += 1

            match_score_str = f"{p_sets_won}-{o_sets_won}"
            filename = f"{date_file} {event} {round_m} {p_name} {match_score_str} {o_name}.pdf"

            pdf_bytes = pdf.output(dest='S').encode('latin-1')

            st.success("PDF generated successfully.")
            st.download_button(
                label="Download Full PDF Match Report",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"PDF generation failed: {e}")
else:
    st.warning("Upload a valid DartFish CSV first.")
