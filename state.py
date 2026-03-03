"""
Shared state for the Coach Bot graph.
"""

from typing import Annotated, Any, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


def _last(a, b):
    """Reducer: nimmt immer den neuesten Wert (verhindert InvalidUpdateError)."""
    return b


FeedbackCategory = Literal[
    "positive", "partial_positive", "neutral", "partial_negative", "negative"
]

InputType = Literal["question", "feedback", "other"]


class CoachState(TypedDict, total=False):
    # ── Conversation messages ──────────────────────────────────────────────────
    messages: Annotated[list, add_messages]

    # ── Auth ───────────────────────────────────────────────────────────────────
    is_logged_in: bool
    user_profile: Optional[dict]

    # ── Questionnaire ──────────────────────────────────────────────────────────
    questionnaire_answers: list
    area_scores: dict
    top_areas: list

    # ── Methoden ──────────────────────────────────────────────────────────────
    available_methods: dict
    selected_methods:  Annotated[list, _last]
    chosen_method:     Annotated[Optional[dict], _last]
    next_available_method: Annotated[Optional[dict], _last]
    used_method_names: list

    # ── Session ────────────────────────────────────────────────────────────────
    session_active:  Annotated[bool, _last]
    method_chosen:   Annotated[bool, _last]
    has_saved_result: bool

    # ── Routing helpers ────────────────────────────────────────────────────────
    user_action:       Annotated[Optional[str], _last]
    input_type:        Annotated[Optional[str], _last]
    feedback_category: Annotated[Optional[str], _last]
    next_action:       Annotated[Optional[str], _last]
    pending_question:  Annotated[Optional[str], _last]
