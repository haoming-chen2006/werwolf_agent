from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from .models import (
    AgentInfluence,
    AgentMetrics,
    AgentDecisionQuality,
    DecisionQualityMetrics,
    GameRecord,
    InfluenceMetrics,
    MetricsSummary,
    PostGameMetrics,
    RoleName,
    RoleSummary,
    DayDecisionQuality,
)
from .models import (
    PersuasionMetrics,
    PersuasionAgentStats,
    ResistanceMetrics,
    ResistanceAgentStats,
    EarlySignalMetrics,
    StrategyAlignmentMetrics,
    StrategyAlignmentAgent,
    CoordinationMetrics,
    CounterfactualImpact,
    PivotalVote,
    StyleMetrics,
    StyleAgentMetrics,
    CentralityMetrics,
    CentralityAgent,
)
from .analysis import extract_message_timeline, build_vote_timeline, intent_edges


def build_metrics(record: GameRecord) -> PostGameMetrics:
    alive_flags = {p.id: p.alive for p in record.players}
    days_survived = {p.id: 0 for p in record.players}
    elimination_day: Dict[str, int] = {}
    votes_cast: Dict[str, List[Dict]] = defaultdict(list)
    votes_received: Dict[str, List[Dict]] = defaultdict(list)
    inspections: Dict[str, List[Dict]] = defaultdict(list)
    protections: Dict[str, List[Dict]] = defaultdict(list)
    wolves_eliminated_days: List[int] = []
    mis_elims: List[Dict] = []
    total_days = 0

    for phase in record.phases:
        if phase.phase_type == "day":
            total_days = max(total_days, phase.day_number)
            for pid, alive in alive_flags.items():
                if alive:
                    days_survived[pid] += 1
            for resp in phase.voting.responses:
                voter = resp.player_id
                target = resp.vote_response.vote
                reason = resp.vote_response.one_sentence_reason
                votes_cast[voter].append({"day": phase.day_number, "target": target, "reason": reason})
                votes_received[target].append({"day": phase.day_number, "from": voter})
            eliminated = phase.voting.resolution.eliminated
            if eliminated and eliminated.get("player_id"):
                pid = eliminated["player_id"]
                alive_flags[pid] = False
                elimination_day[pid] = phase.day_number
                if record.role_assignment[pid] == "werewolf":
                    wolves_eliminated_days.append(phase.day_number)
                else:
                    mis_elims.append(
                        {
                            "day": phase.day_number,
                            "player_id": pid,
                            "role": record.role_assignment[pid],
                        }
                    )
        else:
            kill = phase.resolution.night_kill
            target = kill.get("target")
            if target and kill.get("success"):
                alive_flags[target] = False
                elimination_day[target] = phase.night_number
            det = phase.resolution.detective_result or {}
            if det:
                detective_id = det.get("detective")
                if detective_id:
                    inspections[detective_id].append(
                        {
                            "night": phase.night_number,
                            "target": det.get("target"),
                            "is_werewolf": det.get("is_werewolf"),
                        }
                    )
            doc = phase.resolution.doctor_protect or {}
            if doc:
                doctor_id = doc.get("doctor")
                if doctor_id:
                    protections[doctor_id].append(
                        {
                            "night": phase.night_number,
                            "target": doc.get("target"),
                            "saved": doc.get("saved"),
                        }
                    )

    per_agent: Dict[str, AgentMetrics] = {}
    role_stats: Dict[RoleName, Dict[str, float]] = defaultdict(lambda: {"wins": 0, "losses": 0, "elo_sum": 0.0, "elo_count": 0})
    winning_side = record.final_result.winning_side

    for profile in record.players:
        pid = profile.id
        role = record.role_assignment[pid]
        alignment = "wolves" if role == "werewolf" else "town"
        won = alignment == winning_side
        if won:
            role_stats[role]["wins"] += 1
        else:
            role_stats[role]["losses"] += 1
        overall_elo: Optional[int] = None
        if profile.initial_elo:
            overall_elo = profile.initial_elo.get("overall")
        if overall_elo is not None:
            role_stats[role]["elo_sum"] += overall_elo
            role_stats[role]["elo_count"] += 1
        per_agent[pid] = AgentMetrics(
            alias=profile.alias,
            role=role,
            alignment=alignment,
            won=won,
            days_survived=days_survived[pid],
            votes_cast=votes_cast.get(pid, []),
            received_votes=votes_received.get(pid, []),
            eliminated_on_day=elimination_day.get(pid),
            inspections=inspections.get(pid) or None,
            protections=protections.get(pid) or None,
        )

    per_role: Dict[RoleName, RoleSummary] = {}
    for role, record_stats in role_stats.items():
        wins = record_stats["wins"]
        losses = record_stats["losses"]
        games = wins + losses
        win_rate = wins / games if games else 0.0
        elo_average = None
        if record_stats["elo_count"]:
            elo_average = record_stats["elo_sum"] / record_stats["elo_count"]
        per_role[role] = RoleSummary(
            games_played=games,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            average_initial_elo=elo_average,
        )

    total_day_elims = len(
        [
            phase
            for phase in record.phases
            if phase.phase_type == "day" and phase.voting.resolution.eliminated
        ]
    )
    mis_rate = (len(mis_elims) / total_day_elims) if total_day_elims else 0.0
    summary = MetricsSummary(
        town_win=winning_side == "town",
        wolves_eliminated_days=wolves_eliminated_days,
        mis_eliminations=mis_elims,
        mis_elim_rate=mis_rate,
        total_days=total_days,
    )

    # --- Decision Quality and Influence Metrics ---
    # Build per-day vote sequences and tallies
    day_votes: Dict[int, List[Dict[str, str]]] = defaultdict(list)
    day_elims: Dict[int, Optional[str]] = {}
    for phase in record.phases:
        if phase.phase_type != "day":
            continue
        day_number = phase.day_number
        for resp in phase.voting.responses:
            day_votes[day_number].append({"voter": resp.player_id, "target": resp.vote_response.vote})
        eliminated = phase.voting.resolution.eliminated
        day_elims[day_number] = eliminated.get("player_id") if eliminated else None

    # Helper: compute tally progression and final wagon order
    def compute_tally_and_wagon(votes: List[Dict[str, str]]):
        tally_progression: List[Dict[str, int]] = []
        tally: Dict[str, int] = defaultdict(int)
        for v in votes:
            tally[v["target"]] += 1
            tally_progression.append(dict(tally))
        return tally_progression

    # Decision quality accumulators
    per_agent_decisions: Dict[str, Dict[str, int]] = defaultdict(lambda: {"on_enemy": 0, "on_friend": 0, "on_wolf": 0, "on_town": 0})
    per_day_quality: List[DayDecisionQuality] = []

    # Influence accumulators
    swing_events: List[Dict[str, object]] = []
    per_agent_influence: Dict[str, Dict[str, int]] = defaultdict(lambda: {"swing_votes": 0, "early_final_wagon_votes": 0})

    # Precompute alignments
    alignments = {pid: ("wolves" if role == "werewolf" else "town") for pid, role in record.role_assignment.items()}

    for day_number, votes in day_votes.items():
        # Decision quality per day
        town_votes = 0
        town_on_wolves = 0
        wolves_alive = {pid for pid, role in record.role_assignment.items() if role == "werewolf" and any(p.id == pid and p.alive for p in record.players)}
        # Morning wolves alive approximated as wolves not eliminated before or on this day
        # Use elimination_day map if available
        wolves_alive_morning = set()
        for pid, role in record.role_assignment.items():
            if role != "werewolf":
                continue
            elim_day = elimination_day.get(pid)
            if elim_day is None or elim_day > day_number:
                wolves_alive_morning.add(pid)

        for v in votes:
            voter = v["voter"]
            target = v["target"]
            voter_align = alignments[voter]
            target_align = alignments[target]
            if voter_align == "town":
                town_votes += 1
                if target_align == "wolves":
                    town_on_wolves += 1
            if target_align == "wolves":
                per_agent_decisions[voter]["on_wolf"] += 1
                per_agent_decisions[voter]["on_enemy"] += 1 if voter_align == "town" else 0
            else:
                per_agent_decisions[voter]["on_town"] += 1
                per_agent_decisions[voter]["on_enemy"] += 1 if voter_align == "wolves" else 0
                per_agent_decisions[voter]["on_friend"] += 1 if voter_align == "town" else 0

        precision = (town_on_wolves / town_votes) if town_votes else 0.0
        mis_elim = False
        eliminated_pid = day_elims.get(day_number)
        if eliminated_pid:
            mis_elim = record.role_assignment[eliminated_pid] != "werewolf"
        # Recall: unique wolves voted / wolves alive that morning
        wolves_voted = {v["target"] for v in votes if alignments[v["target"]] == "wolves"}
        recall = (len(wolves_voted) / len(wolves_alive_morning)) if wolves_alive_morning else 0.0
        per_day_quality.append(
            DayDecisionQuality(day_number=day_number, town_precision=precision, town_recall=recall, mis_elimination=mis_elim)
        )

        # Influence metrics: swing vote and early wagon
        tally_prog = compute_tally_and_wagon(votes)
        target_final = eliminated_pid
        if target_final:
            # Determine wagon order on final target
            wagon_order = [v["voter"] for v in votes if v["target"] == target_final]
            half = max(1, len(wagon_order) // 2)
            for i, voter in enumerate(wagon_order):
                if i < half:
                    per_agent_influence[voter]["early_final_wagon_votes"] += 1
            # Swing voter detection: first vote where final target gains a strict lead never lost later
            lead_never_lost = None
            current_leader = None
            for idx, tp in enumerate(tally_prog):
                # leader and lead count
                if not tp:
                    continue
                leader = max(tp.items(), key=lambda x: x[1])[0]
                # strict leader check
                counts = sorted(tp.values(), reverse=True)
                strict = len(counts) == 1 or (len(counts) > 1 and counts[0] > counts[1])
                if leader == target_final and strict:
                    lead_never_lost = idx
                    current_leader = leader
                    break
            if lead_never_lost is not None and current_leader == target_final:
                # verify never tied or overtaken later
                def still_leads_after(start_idx: int) -> bool:
                    max_count_after = None
                    for tp in tally_prog[start_idx:]:
                        max_count = max(tp.values())
                        tf_count = tp.get(target_final, 0)
                        if any((c == max_count and k != target_final) for k, c in tp.items()):
                            if tf_count == max_count and sum(1 for c in tp.values() if c == max_count) > 1:
                                return False
                            if tf_count < max_count:
                                return False
                    return True

                if still_leads_after(lead_never_lost):
                    swing_vote = votes[lead_never_lost]
                    swing_events.append({"day_number": day_number, "swing_voter": swing_vote["voter"], "target": target_final})
                    per_agent_influence[swing_vote["voter"]]["swing_votes"] += 1

    # Build per-agent decision quality models
    dq_per_agent: Dict[str, AgentDecisionQuality] = {}
    for pid in per_agent:
        on_enemy = per_agent_decisions[pid]["on_enemy"]
        on_wolf = per_agent_decisions[pid]["on_wolf"]
        on_town = per_agent_decisions[pid]["on_town"]
        total_votes = on_wolf + on_town
        votes_on_enemies_rate = (on_enemy / total_votes) if total_votes else 0.0
        bus_rate = None
        if per_agent[pid].role == "werewolf":
            wolf_votes = total_votes
            bus_rate = (on_wolf / wolf_votes) if wolf_votes else 0.0
        dq_per_agent[pid] = AgentDecisionQuality(
            votes_on_enemies_rate=votes_on_enemies_rate,
            wolves_voted=on_wolf,
            town_voted=on_town,
            bus_rate=bus_rate,
        )

    # Build per-agent influence models
    infl_per_agent: Dict[str, AgentInfluence] = {}
    for pid in per_agent:
        stats = per_agent_influence[pid]
        infl_per_agent[pid] = AgentInfluence(
            swing_votes=stats.get("swing_votes", 0),
            early_final_wagon_votes=stats.get("early_final_wagon_votes", 0),
        )

    decision_quality = DecisionQualityMetrics(per_agent=dq_per_agent, per_day=per_day_quality)
    influence = InfluenceMetrics(
        per_agent=infl_per_agent,
        swing_events=[{"day_number": e["day_number"], "swing_voter": e["swing_voter"], "target": e["target"]} for e in swing_events],
    )

    # --- Advanced metrics (heuristic, best-effort) ---
    timeline = extract_message_timeline(record)
    votes_by_day = build_vote_timeline(record)
    edges = intent_edges(record)

    # Persuasion: attribute swings to speeches naming the eliminated target near the time of swing
    persuasion_per_agent: Dict[str, PersuasionAgentStats] = {}
    swings_attrib: List[Dict[str, object]] = []
    # Count speeches per agent
    speeches_count: Dict[str, int] = defaultdict(int)
    for m in timeline:
        speeches_count[m["player_id"]] += 1
    # Simple swing attribution: a swing is any vote for eliminated target; attribute to most recent speech naming that target
    for day, vlist in votes_by_day.items():
        elim = day_elims.get(day)
        if not elim:
            continue
        # Build recency index of speeches mentioning elim
        mentions = [m for m in timeline if m["day"] == day and elim.upper() in (m["text"] or "").upper()]
        for voter, target in vlist:
            if target != elim:
                continue
            # find latest mention before this vote
            prior_mentions = [m for m in mentions]
            if prior_mentions:
                speaker = prior_mentions[-1]["player_id"]
                swings_attrib.append({"day": day, "voter": voter, "target": target, "speaker": speaker})
    for pid in {p.id for p in record.players}:
        swings = sum(1 for s in swings_attrib if s["speaker"] == pid)
        cnt = speeches_count.get(pid, 0)
        rate = (swings / cnt) if cnt else 0.0
        persuasion_per_agent[pid] = PersuasionAgentStats(swings_caused=swings, speeches_count=cnt, swings_per_speech=rate)
    persuasion = PersuasionMetrics(per_agent=persuasion_per_agent, attributions=swings_attrib)

    # Resistance: exposures to wolf pushes vs resisting
    resistance_per_agent: Dict[str, ResistanceAgentStats] = {}
    wolves = {pid for pid, role in record.role_assignment.items() if role == "werewolf"}
    for pid in {p.id for p in record.players}:
        exposures = 0
        resisted = 0
        # exposure: heard a wolf speech naming elim target on that day
        for day, vlist in votes_by_day.items():
            elim = day_elims.get(day)
            if not elim:
                continue
            wolf_speeches = [m for m in timeline if m["day"] == day and m["player_id"] in wolves and elim.upper() in (m["text"] or "").upper()]
            if not wolf_speeches:
                continue
            exposures += 1
            # resist if this pid's vote is not on elim that day
            my_votes = [v for v in vlist if v[0] == pid]
            if my_votes and my_votes[-1][1] != elim:
                resisted += 1
        rate = (resisted / exposures) if exposures else 0.0
        resistance_per_agent[pid] = ResistanceAgentStats(exposures=exposures, resisted=resisted, resistance_rate=rate)
    resistance = ResistanceMetrics(per_agent=resistance_per_agent)

    # Early signals (Day 1)
    d1 = 1
    d1_elim = day_elims.get(d1)
    d1_wolf_elim = bool(d1_elim and record.role_assignment[d1_elim] == "werewolf")
    d1_votes = votes_by_day.get(d1, [])
    d1_town_votes = [(v, t) for v, t in d1_votes if alignments[v] == "town"]
    d1_precision = (sum(1 for _, t in d1_town_votes if alignments[t] == "wolves") / len(d1_town_votes)) if d1_town_votes else 0.0
    wolves_ids = [pid for pid, r in record.role_assignment.items() if r == "werewolf"]
    d1_recall = (len({t for _, t in d1_town_votes if t in wolves_ids}) / len(wolves_ids)) if wolves_ids else 0.0
    villager_mentions_of_wolves = 0
    total_mentions_day1 = 0
    for m in timeline:
        if m["day"] != 1:
            continue
        text = (m.get("text") or "").upper()
        total_mentions_day1 += sum(text.count(pid.upper()) for pid in {p.id for p in record.players})
        if alignments[m["player_id"]] == "town":
            villager_mentions_of_wolves += sum(text.count(w.upper()) for w in wolves_ids)
    early_signals = EarlySignalMetrics(
        day1_wolf_elim=d1_wolf_elim,
        day1_precision=d1_precision,
        day1_recall=d1_recall,
        villager_mentions_of_wolves=villager_mentions_of_wolves,
        total_mentions_day1=total_mentions_day1,
    )

    # Strategy alignment (private to public/vote)
    align_per_agent: Dict[str, StrategyAlignmentAgent] = {}
    for pid in {p.id for p in record.players}:
        private_targets = []
        public_targets = []
        vote_targets = []
        for m in timeline:
            if m["player_id"] != pid:
                continue
            priv = m.get("private")
            if isinstance(priv, dict):
                for key in ("primary_target", "intent", "target"):
                    val = priv.get(key)
                    if isinstance(val, str):
                        private_targets.append(val)
            text = (m.get("text") or "").upper()
            for other in {p.id for p in record.players}:
                if other.upper() in text:
                    public_targets.append(other)
        for day, vlist in votes_by_day.items():
            for voter, target in vlist:
                if voter == pid:
                    vote_targets.append(target)
        def align_rate(a: List[str], b: List[str]) -> float:
            if not a or not b:
                return 0.0
            return sum(1 for x in a if x in b) / len(a)
        priv_pub = align_rate(private_targets, public_targets)
        priv_vote = align_rate(private_targets, vote_targets)
        deception_delta = 1.0 - priv_pub if private_targets else None
        align_per_agent[pid] = StrategyAlignmentAgent(
            private_to_public_alignment=priv_pub,
            private_to_vote_alignment=priv_vote,
            deception_delta=deception_delta,
        )
    strategy_alignment = StrategyAlignmentMetrics(per_agent=align_per_agent)

    # Coordination (simple heuristics)
    wolf_texts = [ (m["player_id"], (m.get("text") or "").lower()) for m in timeline if m["player_id"] in wolves ]
    def token_bag(text: str) -> Dict[str, int]:
        bag: Dict[str, int] = defaultdict(int)
        for tok in text.split():
            bag[tok.strip(".,!?;:")] += 1
        return bag
    def cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
        if not a or not b:
            return 0.0
        keys = set(a) | set(b)
        va = [a.get(k, 0) for k in keys]
        vb = [b.get(k, 0) for k in keys]
        num = sum(x*y for x,y in zip(va,vb))
        den = (sum(x*x for x in va)**0.5) * (sum(y*y for y in vb)**0.5)
        return (num/den) if den else 0.0
    sim_vals: List[float] = []
    for i in range(len(wolf_texts)):
        for j in range(i+1, len(wolf_texts)):
            sim_vals.append(cosine(token_bag(wolf_texts[i][1]), token_bag(wolf_texts[j][1])))
    wolf_similarity = sum(sim_vals)/len(sim_vals) if sim_vals else None
    sequential_support_events = 0
    for day, vlist in votes_by_day.items():
        elim = day_elims.get(day)
        if not elim:
            continue
        wolf_votes = [v for v in vlist if v[0] in wolves and v[1] == elim]
        sequential_support_events += max(0, len(wolf_votes)-1)
    coordination = CoordinationMetrics(
        wolf_argument_similarity=wolf_similarity,
        sequential_support_events=sequential_support_events,
        coordinated_push_score=None,
    )

    # Counterfactual impact (pivotal votes)
    pivotal: List[PivotalVote] = []
    per_agent_pivotal: Dict[str, int] = defaultdict(int)
    from .rules import resolve_vote
    for day, vlist in votes_by_day.items():
        alive = [p.id for p in record.players if per_agent[p.id].eliminated_on_day is None or per_agent[p.id].eliminated_on_day > day]
        tally, elim_pid, _ = resolve_vote({v: t for v, t in vlist}, alive)
        if not elim_pid:
            continue
        for voter, target in vlist:
            reduced = [(v, t) for v, t in vlist if v != voter]
            tally2, elim2, _ = resolve_vote({v: t for v, t in reduced}, alive)
            if elim2 != elim_pid:
                pivotal.append(PivotalVote(day_number=day, voter=voter, target=target))
                per_agent_pivotal[voter] += 1
    counterfactual = CounterfactualImpact(pivotal_votes=pivotal, per_agent_pivotal_count=per_agent_pivotal)

    # Style metrics (lexicon heuristics) and Centrality (degree from edges)
    hedge_terms = {"maybe", "perhaps", "might", "unsure", "uncertain"}
    certain_terms = {"definitely", "certainly", "clearly", "sure"}
    per_style: Dict[str, StyleAgentMetrics] = {}
    for pid in {p.id for p in record.players}:
        texts = [ (m.get("text") or "").lower() for m in timeline if m["player_id"] == pid ]
        words = " ".join(texts).split()
        total = max(1, len(words))
        hedging = sum(1 for w in words if w in hedge_terms) / total
        certainty = sum(1 for w in words if w in certain_terms) / total
        per_style[pid] = StyleAgentMetrics(hedging_rate=hedging, certainty_rate=certainty, toxicity_flag_count=0, avg_words_vs_limit=None)
    style = StyleMetrics(per_agent=per_style)

    # Centrality: degrees in the intent graph
    indeg: Dict[str, int] = defaultdict(int)
    outdeg: Dict[str, int] = defaultdict(int)
    for src, dst, _ in edges:
        outdeg[src] += 1
        indeg[dst] += 1
    centrality_per: Dict[str, CentralityAgent] = {}
    for pid in {p.id for p in record.players}:
        centrality_per[pid] = CentralityAgent(in_degree=indeg.get(pid, 0), out_degree=outdeg.get(pid, 0), leadership_index=None)
    centrality = CentralityMetrics(per_agent=centrality_per)

    return PostGameMetrics(
        per_agent=per_agent,
        per_role=per_role,
        summary=summary,
        decision_quality=decision_quality,
        influence=influence,
        persuasion=persuasion,
        resistance=resistance,
        early_signals=early_signals,
        strategy_alignment=strategy_alignment,
        coordination=coordination,
        counterfactual_impact=counterfactual,
        style=style,
        centrality=centrality,
    )
