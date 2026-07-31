"""Generate fictional PlaybookIQ sample data under data/raw/.

Re-runnable and deterministic — regenerates the full synthetic dataset used by the
RAG ingestion pipeline (Phase 5+). No real players, teams, or events are referenced.
"""

import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

TEAMS = [
    "Ironclad City Miners",
    "Bay Harbor Kraken",
    "Northgate Sentinels",
    "Prairie Wolves",
]

PLAYERS = [
    {"player_id": "P001", "name": "Darnell Voss", "position": "QB", "team": "Ironclad City Miners", "season": 2025,
     "stats": {"pass_yards": 4128, "pass_tds": 31, "interceptions": 9, "completion_pct": 66.4}},
    {"player_id": "P002", "name": "Marcus Ehlers", "position": "RB", "team": "Ironclad City Miners", "season": 2025,
     "stats": {"rush_yards": 1187, "rush_tds": 11, "yards_per_carry": 4.6, "fumbles": 2}},
    {"player_id": "P003", "name": "Trevon Ashby", "position": "WR", "team": "Ironclad City Miners", "season": 2025,
     "stats": {"receptions": 88, "rec_yards": 1310, "rec_tds": 9, "yards_after_catch": 412}},
    {"player_id": "P004", "name": "Colton Reyes", "position": "LB", "team": "Bay Harbor Kraken", "season": 2025,
     "stats": {"tackles": 121, "sacks": 6.5, "forced_fumbles": 3, "interceptions": 1}},
    {"player_id": "P005", "name": "Isaiah Whitfield", "position": "CB", "team": "Bay Harbor Kraken", "season": 2025,
     "stats": {"tackles": 54, "interceptions": 5, "passes_defended": 14, "penalties": 4}},
    {"player_id": "P006", "name": "Grant Okafor", "position": "S", "team": "Bay Harbor Kraken", "season": 2025,
     "stats": {"tackles": 78, "interceptions": 2, "passes_defended": 9, "sacks": 1.0}},
    {"player_id": "P007", "name": "Aiden Kowalski", "position": "QB", "team": "Northgate Sentinels", "season": 2025,
     "stats": {"pass_yards": 3654, "pass_tds": 24, "interceptions": 13, "completion_pct": 61.2}},
    {"player_id": "P008", "name": "DeShawn Pruitt", "position": "WR", "team": "Northgate Sentinels", "season": 2025,
     "stats": {"receptions": 71, "rec_yards": 1042, "rec_tds": 7, "yards_after_catch": 298}},
    {"player_id": "P009", "name": "Nolan Vasquez", "position": "TE", "team": "Northgate Sentinels", "season": 2025,
     "stats": {"receptions": 52, "rec_yards": 611, "rec_tds": 5, "blocking_grade": 78.2}},
    {"player_id": "P010", "name": "Jaylen Fitch", "position": "DL", "team": "Prairie Wolves", "season": 2025,
     "stats": {"tackles": 45, "sacks": 10.5, "tackles_for_loss": 14, "qb_hits": 22}},
    {"player_id": "P011", "name": "Bryce Talmadge", "position": "OL", "team": "Prairie Wolves", "season": 2025,
     "stats": {"games_started": 17, "sacks_allowed": 2, "penalties": 5, "pass_block_grade": 82.4}},
    {"player_id": "P012", "name": "Rico Delvecchio", "position": "K", "team": "Prairie Wolves", "season": 2025,
     "stats": {"fg_made": 27, "fg_attempted": 31, "long": 54, "touchbacks": 38}},
]

INJURY_LOGS = [
    {"player_id": "P002", "player_name": "Marcus Ehlers", "date": "2025-10-12", "injury_type": "Grade 1 hamstring strain",
     "body_part": "left hamstring", "status": "questionable", "expected_return": "2025-10-26",
     "notes": "Sustained during third-quarter cutback run; limited in practice reps since."},
    {"player_id": "P005", "player_name": "Isaiah Whitfield", "date": "2025-09-30", "injury_type": "High ankle sprain",
     "body_part": "right ankle", "status": "injured_reserve", "expected_return": "2025-11-09",
     "notes": "Non-contact injury during backpedal in coverage drill; walking boot for 2 weeks."},
    {"player_id": "P007", "player_name": "Aiden Kowalski", "date": "2025-11-02", "injury_type": "AC joint sprain",
     "body_part": "left shoulder (non-throwing)", "status": "probable", "expected_return": "2025-11-09",
     "notes": "Landed on shoulder after a scramble; no impact expected on throwing mechanics."},
    {"player_id": "P010", "player_name": "Jaylen Fitch", "date": "2025-08-20", "injury_type": "Turf toe",
     "body_part": "right big toe", "status": "active", "expected_return": "2025-08-20",
     "notes": "Managed with a stiffer insole and taping; has not missed a snap since diagnosis."},
]

SCOUTING_REPORT = """SCOUTING REPORT — Isaiah Whitfield (CB, Bay Harbor Kraken)
Prepared for: Sportsnexa Advance Scouting Unit
Season: 2025 | Games Charted: 9

Summary:
Whitfield is a press-man corner who wins primarily with footwork and hand-fighting at the
line rather than long speed. His 5 interceptions this season lead the Kraken secondary, but
4 of the 5 came against teams that threw predominantly short/intermediate routes into his
side, suggesting some of the production is scheme-driven rather than purely man-coverage
dominance.

Strengths:
- Elite click-and-close quickness on out-breaking routes (comebacks, curls, outs).
- Physical at the catch point; willing to contest 50/50 balls despite giving up 2-3 inches
  to bigger receivers.
- Rarely beaten deep when aligned with safety help over the top (0 touchdowns allowed on
  routes over 20 air yards this season).

Exploitable tendencies:
- Struggles versus double moves and hesitation releases — bit on a stutter-go for a
  touchdown in Week 6 and was flagged for a step-late recovery on a similar concept in
  Week 8.
- When aligned in off-man (7+ yards cushion), he opens his hips early on in-breaking routes,
  creating a window for slants and dig routes right after the break point.
- On third-and-long snaps specifically, Whitfield has shown a pattern of peeking into the
  backfield on play-action, which has produced two separate explosive completions against
  him on third-down blitz packages when the offense sold run action first.

Recommendation: Attack with double moves and hesitation releases when he plays press;
target in-breaking routes when he plays off-man with a deep cushion. Avoid predictable
third-down deep shots unless disguised with play-action, since he recovers well against
straightforward vertical routes but is vulnerable to misdirection specifically on
third-down blitz-package downs.
"""

GAME_TRANSCRIPT = """GAME TRANSCRIPT (PARTIAL) — Ironclad City Miners at Bay Harbor Kraken
Week 11, 2025 Season | Third Quarter, Third-Down Package Focus

[Q3 14:02] 3rd & 8, Miners ball at BHK 41. Miners come out in 11 personnel, trips right.
Kraken show double-A-gap pressure look with Colton Reyes walked down. Snap: play-action
fake to Ehlers, Voss rolls right, hits Ashby on a deep dig route behind Whitfield, who
bit hard on the run fake and was still squared to the line of scrimmage at the snap.
Gain of 27. Analyst note: this is the third time this season the Kraken have shown
double-A-gap pressure on 3rd-and-long and then bailed into a zone blitz with the corner
peeking the backfield — a repeatable tell on early-down and long-yardage snaps.

[Q3 09:41] 3rd & 6, Kraken ball at own 33. Kowalski under center, single-back look.
Miners rush four, drop seven into a soft zone. Kowalski checks down to Vasquez underneath
for 5, forcing a punt. Analyst note: Kraken offense has not shown a designed third-down
conversion concept versus soft zone all game — they default to the checkdown almost every
time zone coverage is shown pre-snap on 3rd-and-medium.

[Q3 04:15] 3rd & 3, Miners ball at own 48. Reyes reads the run action pre-snap and fills
the B-gap immediately, stopping Ehlers for no gain. Miners punt. Analyst note: Reyes is
consistently the first defender to diagnose inside zone on short-yardage downs — his
average time-to-contact on stuffed runs this season is a full quarter-second faster than
the Kraken's other two linebackers.

[Q3 01:58] 3rd & 8, Kraken ball at own 22. Whitfield's earlier tendency shows up again on
defense-independent charting: Kowalski targets Pruitt on a comeback route away from
Whitfield's side entirely, an 11-yard gain, suggesting the Kraken staff may already be
aware of and scripting around their own corner's third-down vulnerability rather than
correcting the technique itself.
"""

PLAYBOOKS = {
    "trips_right_smash.txt": """FORMATION: Trips Right, Slot Motion
CONCEPT: Smash (Hitch/Corner Combo)
Personnel: 11 (1 RB, 1 TE, 3 WR)

Pre-snap: Trips receivers to the right, single receiver (X) to the left. Slot motion
across the formation to check man vs. zone leverage before the snap.

Read progression: Outside receiver runs a hard hitch at 5 yards; slot receiver runs a
corner route to the same side. Versus off-man coverage with a deep cushion, the hitch
is the immediate answer. Versus zone with a flat defender sitting under the hitch,
progress to the corner route behind him.

Best matchup: off-man corners who open their hips early on in-breaking stems — the
hitch/corner combo isolates a single defender in a high-low leverage conflict.
""",
    "cover3_buzz_blitz.txt": """PACKAGE: Cover 3 Buzz, Zone Blitz
Personnel: Sub package (4-2-5)

Pre-snap look: double-A-gap walk-up from both inside linebackers, simulating A-gap
pressure from both sides. Strong safety rotates down late to disguise the coverage shell.

Post-snap: one A-gap defender drops into a hook/curl zone (buzz technique) while the
other rushes; corners play off-man technique with the safety rotating to a single-high
shell (Cover 3). Designed to bait the quarterback into a hot/sight-adjust read against
what looks like a 5-man pressure but is actually a 4-man rush with 7 in coverage.

Coaching point: corners in off-man on this call must stay square through the route stem
and avoid peeking into the backfield at the run/play-action fake, since the entire
disguise is built around the offense believing pressure is coming and throwing hot —
if the corner bites on the fake, the defense loses its leverage advantage in coverage.
""",
    "inside_zone_read.txt": """RUN CONCEPT: Inside Zone (Read)
Personnel: 11 (1 RB, 1 TE, 3 WR)

Blocking scheme: zone step playside from the entire offensive line, running back reads
the first down lineman past the center. Quarterback reads the backside defensive end
for a potential keep.

Defensive keys: linebackers who diagnose zone quickly by reading the offensive line's
zone-step footwork (rather than the running back) get to the point of attack fastest —
look for backside linebacker fill speed as the key indicator of run recognition ability.
""",
}


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "playbooks").mkdir(parents=True, exist_ok=True)

    write_json(DATA_DIR / "players.json", {"generated": str(date.today()), "teams": TEAMS, "players": PLAYERS})
    write_json(DATA_DIR / "injury_logs.json", {"generated": str(date.today()), "injuries": INJURY_LOGS})

    (DATA_DIR / "sample_scouting_report.txt").write_text(SCOUTING_REPORT, encoding="utf-8")
    (DATA_DIR / "sample_game_transcript.txt").write_text(GAME_TRANSCRIPT, encoding="utf-8")

    for filename, content in PLAYBOOKS.items():
        (DATA_DIR / "playbooks" / filename).write_text(content, encoding="utf-8")

    manifest = [
        {"path": "players.json", "document_type": "player_profile", "player_id": None},
        {"path": "injury_logs.json", "document_type": "injury_log", "player_id": None},
        {"path": "sample_scouting_report.txt", "document_type": "scouting_report", "player_id": "P005"},
        {"path": "sample_game_transcript.txt", "document_type": "game_transcript", "player_id": None},
        *[
            {"path": f"playbooks/{name}", "document_type": "playbook", "player_id": None}
            for name in PLAYBOOKS
        ],
    ]
    write_json(DATA_DIR / "manifest.json", {"generated": str(date.today()), "documents": manifest})

    print(f"Synthetic data written to {DATA_DIR}")


if __name__ == "__main__":
    main()
