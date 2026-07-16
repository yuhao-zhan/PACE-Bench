import math

_PARTIAL_SCORE_MAX = 80.0

import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from pace_bench.primitives import compute_constraint_penalty

from pace_bench.tasks.categories.Category5_Cybernetics_Control.C_05.environment import (
    BARRIER_DELAY_STEPS as _SOURCE_BARRIER_DELAY_STEPS,
    FORCE_LIMIT_INSIDE as _SOURCE_FORCE_LIMIT_INSIDE,
    RECENT_A_FOR_B as _SOURCE_RECENT_A_FOR_B,
    REPULSION_STRONG_THRESHOLD as _SOURCE_REPULSION_STRONG_THRESHOLD,

)

def _distance_point_to_switch_zone(x: float, y: float, cx: float, cy: float, hw: float, hh: float) -> float:
    closest_x = min(max(x, cx - hw), cx + hw)
    closest_y = min(max(y, cy - hh), cy + hh)
    return math.hypot(x - closest_x, y - closest_y)

def _agent_center_in_zone(x: float, y: float, cx: float, cy: float, hw: float, hh: float) -> bool:
    return (cx - hw <= x <= cx + hw) and (cy - hh <= y <= cy + hh)

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        self._required_order = list(terrain_bounds.get("required_order", ["A", "B", "C"]))
    def evaluate(self, agent_body, step_count, max_steps):
        if not self.environment:
            return True, 0.0, {"error": "Environment not available"}
        sequence_correct = self.environment.get_sequence_correct()
        wrong_order = self.environment.get_wrong_order()
        triggered = self.environment.get_triggered_switches()
        next_req = self.environment.get_next_required_switch()
        x, y = self.environment.get_agent_position()
        vx, vy = self.environment.get_agent_velocity()
        steps_in_current_zone = getattr(
            self.environment, "get_steps_in_current_zone", lambda: 0
        )()
        steps_required_to_trigger = getattr(
            self.environment, "get_steps_required_to_trigger", lambda: 1
        )()
        cooldown_remaining = getattr(
            self.environment, "get_cooldown_remaining", lambda: 0
        )()
        failed = False
        failure_reason = None
        timed_out = False
        if wrong_order:
            failed = True
            failure_reason = "Switches triggered in wrong order relative to required sequence"
        elif max_steps > 0 and step_count >= max_steps and not sequence_correct:
            failed = True
            timed_out = True
            failure_reason = "Time limit reached before completing the required switch sequence"
        success = sequence_correct and not failed
        n_milestones = max(1, len(self._required_order))
        milestone_weight = _PARTIAL_SCORE_MAX / float(n_milestones)
        if success:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            score = (
                len(triggered) * milestone_weight
                if self._required_order
                else 0.0
            )
        zones = self.terrain_bounds.get("zones", {})
        tb_fn = getattr(self.environment, "get_terrain_bounds", None)
        if callable(tb_fn):
            live_tb = tb_fn()
            if isinstance(live_tb, dict) and live_tb.get("zones"):
                zones = live_tb["zones"]
        distance_to_next = None
        inside_next_required_zone = False
        if next_req and next_req in zones:
            cx, cy, hw, hh = zones[next_req]
            distance_to_next = _distance_point_to_switch_zone(x, y, cx, cy, hw, hh)
            inside_next_required_zone = _agent_center_in_zone(x, y, cx, cy, hw, hh)
        speed = math.sqrt(vx * vx + vy * vy)
        progress_percent = (
            (len(triggered) / float(n_milestones) * 100.0) if self._required_order else 0.0
        )
        metrics = {
            "max_steps": max_steps,
            "agent_x": x,
            "agent_y": y,
            "agent_vx": vx,
            "agent_vy": vy,
            "triggered_switches": list(triggered),
            "next_required": next_req,
            "sequence_correct": sequence_correct,
            "wrong_order": wrong_order,
            "step_count": step_count,
            "success": success,
            "failed": failed,
            "failure_reason": failure_reason,
            "distance_to_next_zone": distance_to_next,
            "inside_next_required_zone": inside_next_required_zone,
            "speed": speed,
            "progress_percent": progress_percent,
            "steps_in_current_zone": steps_in_current_zone,
            "steps_required_to_trigger": steps_required_to_trigger,
            "cooldown_remaining": cooldown_remaining,
            "timed_out": timed_out,
            "zones": zones,
        }
        if self.environment is not None:
            env = self.environment
            metrics["env_speed_cap_inside"] = getattr(env, "_speed_cap_inside", None)
            rab = getattr(env, "_recent_a_for_b", None)
            if rab is not None:
                metrics["env_flag_tight_a_to_b"] = rab < _SOURCE_RECENT_A_FOR_B
                metrics["env_flag_loose_a_to_b_recency"] = rab > _SOURCE_RECENT_A_FOR_B
            else:
                metrics["env_flag_tight_a_to_b"] = False
                metrics["env_flag_loose_a_to_b_recency"] = False
            bdelay = getattr(env, "_barrier_delay_steps", None)
            if bdelay is not None:
                metrics["env_flag_long_barrier_delay"] = (
                    bdelay > _SOURCE_BARRIER_DELAY_STEPS
                )
            rm = getattr(env, "_repulsion_mag", None)
            if rm is not None:
                metrics["env_flag_strong_repulsion"] = (
                    rm >= _SOURCE_REPULSION_STRONG_THRESHOLD
                )
            fl = getattr(env, "_force_limit_inside", None)
            if fl is not None:
                metrics["env_flag_sensitive_trigger"] = fl < _SOURCE_FORCE_LIMIT_INSIDE
            get_rep = getattr(env, "get_repulsion_at_agent", None)
            if callable(get_rep):
                rfx, rfy, rmag = get_rep()
                metrics["repulsion_fx"] = rfx
                metrics["repulsion_fy"] = rfy
                metrics["repulsion_magnitude"] = rmag
            get_bar = getattr(env, "get_barrier_status", None)
            if callable(get_bar):
                bs = get_bar()
                metrics["barrier_active"] = bs.get("active", False)
                metrics["barrier_steps_until_open"] = bs.get("steps_until_open", 0)
            get_ct = getattr(env, "get_cooldown_total", None)
            if callable(get_ct):
                metrics["cooldown_total"] = get_ct()
            get_tw = getattr(env, "get_temporal_window_status", None)
            if callable(get_tw):
                tw = get_tw()
                metrics["A_visited"] = tw.get("A_visited", False)
                metrics["B_visited"] = tw.get("B_visited", False)
                metrics["steps_since_last_A"] = tw.get("steps_since_last_A", -1)
                metrics["steps_since_last_B"] = tw.get("steps_since_last_B", -1)
                metrics["temporal_window_A_to_B"] = tw.get("window_A_to_B", 0)
                metrics["temporal_window_B_to_C"] = tw.get("window_B_to_C", 0)
            get_drs = getattr(env, "get_dwell_reset_stats", None)
            if callable(get_drs):
                drs = get_drs()
                metrics["dwell_reset_zone_change"] = drs.get("zone_change", 0)
                metrics["dwell_reset_speed"] = drs.get("speed", 0)
                metrics["dwell_reset_force"] = drs.get("force", 0)
                metrics["dwell_blocked_temporal"] = drs.get("blocked_temporal", 0)
                metrics["dwell_blocked_altitude"] = drs.get("blocked_altitude", 0)
                metrics["dwell_blocked_cooldown"] = drs.get("blocked_cooldown", 0)
            get_laf = getattr(env, "get_last_applied_force", None)
            if callable(get_laf):
                afx, afy, afm = get_laf()
                metrics["applied_force_x"] = afx
                metrics["applied_force_y"] = afy
                metrics["applied_force_magnitude"] = afm
            get_yh = getattr(env, "get_agent_y_history_stats", None)
            if callable(get_yh):
                yhs = get_yh()
                metrics["agent_y_max_recent"] = yhs.get("max_recent_y", 0.0)
                metrics["agent_y_history_length"] = yhs.get("history_length", 0)
                metrics["history_window"] = yhs.get("history_window", 0)
                metrics["required_max_y_c"] = yhs.get("required_max_y", 0.0)
            get_pv = getattr(env, "get_peak_values", None)
            if callable(get_pv):
                pv = get_pv()
                metrics["peak_speed_seen"] = pv.get("peak_speed", 0.0)
                metrics["peak_force_applied_magnitude"] = pv.get("peak_force_applied", 0.0)
            get_izfl = getattr(env, "get_in_zone_force_limit", None)
            if callable(get_izfl):
                metrics["force_limit_inside"] = get_izfl()
            get_izsc = getattr(env, "get_in_zone_speed_cap", None)
            if callable(get_izsc):
                metrics["speed_cap_inside"] = get_izsc()
            get_rp = getattr(env, "get_repulsion_params", None)
            if callable(get_rp):
                rp = get_rp()
                metrics["repulsion_mag"] = rp.get("magnitude", 0.0)
                metrics["repulsion_range"] = rp.get("range", 0.0)
                metrics["repulsion_tangential_mag"] = rp.get("tangential", 0.0)
            get_tss = getattr(env, "get_trigger_stay_steps", None)
            if callable(get_tss):
                metrics["trigger_stay_steps"] = get_tss()
            get_bds = getattr(env, "get_barrier_delay_steps", None)
            if callable(get_bds):
                metrics["barrier_delay_steps"] = get_bds()
            get_am = getattr(env, "get_agent_mass", None)
            if callable(get_am):
                metrics["agent_mass"] = get_am()
            get_maf = getattr(env, "get_max_agent_force", None)
            if callable(get_maf):
                metrics["max_agent_force_per_axis"] = get_maf()
            get_ch = getattr(env, "get_c_high_history", None)
            if callable(get_ch):
                metrics["c_high_history"] = get_ch()
            get_crmy = getattr(env, "get_c_required_max_y", None)
            if callable(get_crmy):
                metrics["c_required_max_y"] = get_crmy()
        done = failed or sequence_correct
        return done, score, metrics
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("C_05", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'required_order': self._required_order,
        }
    def get_task_description(self):
        desc = (
        )
        order_s = ", ".join(self._required_order) if self._required_order else "(see environment)"
        primary = (
            f"Trigger switches in order: {order_s}"
        )
        return {
            "task": "C-05: The Logic Lock",
            "description": desc,
            "required_order": self._required_order,
            "success_criteria": {
                "primary": primary,
                "failure": (
                ),
            },
            "evaluation": {
                "score_range": "0-100",
                "success_score": 100,
                "failure_score": 0,
            },
        }
