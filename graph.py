"""
Coach Bot - LangGraph Implementation (fixed, no infinite loops)
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import CoachState
from nodes.auth import login_node, guest_node
from nodes.profile import load_profile_node
from nodes.questionnaire import questionnaire_node, calculate_scores_node, determine_top_areas_node
from nodes.method_selection import select_methods_node, display_methods_node
from nodes.coach import coach_explain_node
from nodes.session import show_method_detail_node, give_start_impulse_node, request_feedback_node, wait_for_input_node
from nodes.feedback import (
    feedback_positive_node,
    feedback_partial_positive_node,
    feedback_neutral_node,
    feedback_partial_negative_node,
    feedback_negative_node,
)
from routers import (
    route_login,
    route_user_action,
    route_start_or_question,
    route_input_type,
    route_feedback_category,
    route_next_action,
)


def build_graph():
    builder = StateGraph(CoachState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    builder.add_node("login",                    login_node)
    builder.add_node("guest",                    guest_node)
    builder.add_node("load_profile",             load_profile_node)
    builder.add_node("questionnaire",            questionnaire_node)
    builder.add_node("calculate_scores",         calculate_scores_node)
    builder.add_node("determine_top_areas",      determine_top_areas_node)
    builder.add_node("select_methods",           select_methods_node)
    builder.add_node("display_methods",          display_methods_node)
    builder.add_node("coach_explain",            coach_explain_node)
    builder.add_node("show_method_detail",       show_method_detail_node)
    builder.add_node("give_start_impulse",       give_start_impulse_node)
    builder.add_node("request_feedback",         request_feedback_node)
    builder.add_node("wait_for_input",           wait_for_input_node)
    builder.add_node("route_feedback",           lambda state: state)
    builder.add_node("feedback_positive",        feedback_positive_node)
    builder.add_node("feedback_partial_positive",feedback_partial_positive_node)
    builder.add_node("feedback_neutral",         feedback_neutral_node)
    builder.add_node("feedback_partial_negative",feedback_partial_negative_node)
    builder.add_node("feedback_negative",        feedback_negative_node)

    # ── Entry ──────────────────────────────────────────────────────────────────
    builder.set_entry_point("login")

    # ── Auth ───────────────────────────────────────────────────────────────────
    builder.add_conditional_edges("login", route_login, {
        "logged_in": "load_profile",
        "guest":     "guest",
    })
    builder.add_edge("guest",        "questionnaire")
    builder.add_edge("load_profile", "questionnaire")

    # ── Questionnaire ──────────────────────────────────────────────────────────
    builder.add_edge("questionnaire",       "calculate_scores")
    builder.add_edge("calculate_scores",    "determine_top_areas")
    builder.add_edge("determine_top_areas", "select_methods")
    builder.add_edge("select_methods",      "display_methods")

    # display_methods → END (wartet auf nächsten HTTP-Request vom User)
    builder.add_edge("display_methods", END)

    # coach_explain → END
    builder.add_conditional_edges("coach_explain", _after_coach_explain, {
        "end": END,
    })

    # ── Session ────────────────────────────────────────────────────────────────
    builder.add_conditional_edges("show_method_detail", route_start_or_question, {
        "question": "coach_explain",
        "start":    "give_start_impulse",
    })
    builder.add_edge("give_start_impulse", "request_feedback")
    builder.add_edge("request_feedback",   "wait_for_input")

    # wait_for_input: question / feedback / end  (no "other" → no infinite loop)
    builder.add_conditional_edges("wait_for_input", route_input_type, {
        "question": "coach_explain",
        "feedback": "route_feedback",
        "end":      END,
    })

    # ── Feedback routing ───────────────────────────────────────────────────────
    builder.add_conditional_edges("route_feedback", route_feedback_category, {
        "positive":         "feedback_positive",
        "partial_positive": "feedback_partial_positive",
        "neutral":          "feedback_neutral",
        "partial_negative": "feedback_partial_negative",
        "negative":         "feedback_negative",
    })

    # ── After feedback → next action ───────────────────────────────────────────
    for fb_node in [
        "feedback_positive", "feedback_partial_positive", "feedback_neutral",
        "feedback_partial_negative", "feedback_negative",
    ]:
        builder.add_conditional_edges(fb_node, route_next_action, {
            "question":   "coach_explain",
            "new_method": "show_method_detail",
            "end":        END,
        })

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


def _after_coach_explain(state: CoachState) -> str:
    """
    Nach coach_explain immer END – der Graph wartet auf die nächste
    HTTP-Anfrage. Die nächste Nachricht entscheidet dann weiter.
    """
    return "end"


graph = build_graph()