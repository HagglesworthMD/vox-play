# src/voxelmask_core/actions.py
"""
Action types and reducer for VoxelMask state management.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module implements an action/reducer pattern:
- Actions are typed dicts/dataclasses describing state changes
- apply_action() processes an action and returns new state + side effects
- Side effects are descriptions (not executed here) for the UI layer

Action Flow:
    Button click → on_click sets pending_action → rerun →
    Action consumed (cleared FIRST) → apply_action() → State updated once
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

from .model import CoreState


class ActionType(Enum):
    """Enumeration of all action types."""
    # Detection actions
    DETECT_PHI_REGIONS = auto()
    CLEAR_DETECTION = auto()
    
    # Review actions
    ACCEPT_REVIEW = auto()
    REJECT_REVIEW = auto()
    
    # Region actions 
    TOGGLE_REGION = auto()
    MASK_REGION = auto()
    UNMASK_REGION = auto()
    DELETE_REGION = auto()
    ADD_MANUAL_REGION = auto()
    
    # Bulk region actions
    MASK_ALL_REGIONS = auto()
    UNMASK_ALL_REGIONS = auto()
    RESET_ALL_REGIONS = auto()
    CLEAR_MANUAL_REGIONS = auto()
    
    # Processing actions
    START_PROCESSING = auto()
    PROCESSING_COMPLETE = auto()
    PROCESSING_FAILED = auto()
    
    # Export actions
    PREPARE_EXPORT = auto()
    
    # Navigation actions
    SELECT_SERIES = auto()
    SELECT_INSTANCE = auto()
    
    # Run management
    RESET_RUN = auto()
    NEW_RUN = auto()


@dataclass
class ActionPayload:
    """Base payload for actions that need additional data."""
    pass


@dataclass
class RegionActionPayload(ActionPayload):
    """Payload for region-specific actions."""
    region_id: str


@dataclass
class AddManualRegionPayload(ActionPayload):
    """Payload for adding a manual region."""
    x: int
    y: int
    w: int
    h: int
    frame_index: int = -1


@dataclass
class DetectPhiPayload(ActionPayload):
    """Payload for PHI detection action."""
    mask_x: int
    mask_y: int
    mask_w: int
    mask_h: int
    us_file_count: int


@dataclass
class SelectSeriesPayload(ActionPayload):
    """Payload for series selection."""
    series_idx: int


@dataclass
class SelectInstancePayload(ActionPayload):
    """Payload for instance selection."""
    instance_idx: int


@dataclass 
class Action:
    """
    An action to be applied to the core state.
    
    Actions are immutable descriptions of state changes.
    They are processed by apply_action() to produce new state.
    """
    type: ActionType
    payload: Optional[ActionPayload] = None
    
    @classmethod
    def detect_phi(cls, x: int, y: int, w: int, h: int, us_count: int) -> 'Action':
        return cls(
            type=ActionType.DETECT_PHI_REGIONS,
            payload=DetectPhiPayload(x, y, w, h, us_count)
        )
    
    @classmethod
    def accept_review(cls) -> 'Action':
        return cls(type=ActionType.ACCEPT_REVIEW)
    
    @classmethod
    def toggle_region(cls, region_id: str) -> 'Action':
        return cls(
            type=ActionType.TOGGLE_REGION,
            payload=RegionActionPayload(region_id)
        )
    
    @classmethod
    def mask_all(cls) -> 'Action':
        return cls(type=ActionType.MASK_ALL_REGIONS)
    
    @classmethod
    def unmask_all(cls) -> 'Action':
        return cls(type=ActionType.UNMASK_ALL_REGIONS)
    
    @classmethod
    def reset_all(cls) -> 'Action':
        return cls(type=ActionType.RESET_ALL_REGIONS)
    
    @classmethod
    def add_manual_region(cls, x: int, y: int, w: int, h: int, frame_index: int = -1) -> 'Action':
        return cls(
            type=ActionType.ADD_MANUAL_REGION,
            payload=AddManualRegionPayload(x, y, w, h, frame_index)
        )
    
    @classmethod
    def delete_region(cls, region_id: str) -> 'Action':
        return cls(
            type=ActionType.DELETE_REGION,
            payload=RegionActionPayload(region_id)
        )
    
    @classmethod
    def clear_manual_regions(cls) -> 'Action':
        return cls(type=ActionType.CLEAR_MANUAL_REGIONS)
    
    @classmethod
    def start_processing(cls) -> 'Action':
        return cls(type=ActionType.START_PROCESSING)
    
    @classmethod
    def processing_complete(cls) -> 'Action':
        return cls(type=ActionType.PROCESSING_COMPLETE)
    
    @classmethod
    def reset_run(cls) -> 'Action':
        return cls(type=ActionType.RESET_RUN)
    
    @classmethod
    def select_series(cls, idx: int) -> 'Action':
        return cls(
            type=ActionType.SELECT_SERIES,
            payload=SelectSeriesPayload(idx)
        )
    
    @classmethod
    def select_instance(cls, idx: int) -> 'Action':
        return cls(
            type=ActionType.SELECT_INSTANCE,
            payload=SelectInstancePayload(idx)
        )


class SideEffectType(Enum):
    """Types of side effects that may be triggered by actions."""
    RUN_PIPELINE = auto()
    REBUILD_VIEWER = auto()
    SHOW_TOAST = auto()
    RERUN = auto()


@dataclass
class SideEffect:
    """
    Description of a side effect to be executed by the UI layer.
    
    Side effects are NOT executed within the core logic.
    They are returned as descriptions for the Streamlit layer to execute.
    """
    type: SideEffectType
    payload: Optional[Dict[str, Any]] = None


@dataclass
class ActionResult:
    """
    Result of applying an action.
    
    Contains the new state and any side effects to execute.
    """
    state: CoreState
    side_effects: List[SideEffect]
    success: bool = True
    error: Optional[str] = None


def apply_action(
    state: CoreState,
    action: Action,
    *,
    review_session: Optional[Any] = None,
) -> ActionResult:
    """
    Apply an action to the core state.
    
    This is the main reducer function. It takes the current state and an action,
    and returns a new state along with any side effects to execute.
    
    IMPORTANT: This function does NOT modify st.session_state directly.
    It returns a new CoreState object and side effects as descriptions.
    
    Args:
        state: Current CoreState
        action: Action to apply
        review_session: Optional ReviewSession object (may be mutated for region actions)
        
    Returns:
        ActionResult with new state and side effects
    """
    side_effects: List[SideEffect] = []
    new_state = state  # Will be replaced if state changes
    
    if action.type == ActionType.DETECT_PHI_REGIONS:
        payload: DetectPhiPayload = action.payload
        new_state = CoreState(
            **{
                **state.to_session_state_updates(),
                'us_shared_mask': (payload.mask_x, payload.mask_y, payload.mask_w, payload.mask_h),
                'batch_mask': (payload.mask_x, payload.mask_y, payload.mask_w, payload.mask_h),
                'mask_candidates_ready': True,
                'mask_review_accepted': False,  # Reset acceptance on new detection
            }
        )
        side_effects.append(SideEffect(
            type=SideEffectType.SHOW_TOAST,
            payload={'message': f"🔍 PHI regions detected for {payload.us_file_count} US images"}
        ))
        side_effects.append(SideEffect(type=SideEffectType.RERUN))
        
    elif action.type == ActionType.ACCEPT_REVIEW:
        if review_session is not None:
            # Commit draft and seal the session (mutates review_session)
            try:
                review_session.commit_draft()
                review_session.accept_review()
            except Exception:
                pass  # Session may already be sealed
        
        new_state = CoreState(
            **{
                **state.to_session_state_updates(),
                'mask_review_accepted': True,
            }
        )
        side_effects.append(SideEffect(
            type=SideEffectType.SHOW_TOAST,
            payload={'message': "✅ Review accepted - ready to process"}
        ))
        side_effects.append(SideEffect(type=SideEffectType.RERUN))
        
    elif action.type == ActionType.TOGGLE_REGION:
        payload: RegionActionPayload = action.payload
        if review_session is not None:
            try:
                review_session.draft_toggle(payload.region_id)
            except Exception:
                pass
        # No state change needed - review_session was mutated
        
    elif action.type == ActionType.MASK_ALL_REGIONS:
        if review_session is not None:
            try:
                for region in review_session.get_active_regions():
                    review_session.draft_mask(region.region_id)
            except Exception:
                pass
                
    elif action.type == ActionType.UNMASK_ALL_REGIONS:
        if review_session is not None:
            try:
                for region in review_session.get_active_regions():
                    review_session.draft_unmask(region.region_id)
            except Exception:
                pass
                
    elif action.type == ActionType.RESET_ALL_REGIONS:
        if review_session is not None:
            try:
                review_session.clear_draft()
            except Exception:
                pass
                
    elif action.type == ActionType.ADD_MANUAL_REGION:
        payload: AddManualRegionPayload = action.payload
        if review_session is not None:
            try:
                review_session.add_manual_region(
                    payload.x, payload.y, payload.w, payload.h,
                    frame_index=payload.frame_index
                )
            except Exception:
                pass
                
    elif action.type == ActionType.DELETE_REGION:
        payload: RegionActionPayload = action.payload
        if review_session is not None:
            try:
                review_session.draft_delete(payload.region_id)
            except Exception:
                pass
                
    elif action.type == ActionType.CLEAR_MANUAL_REGIONS:
        if review_session is not None:
            try:
                review_session.clear_manual_regions()
            except Exception:
                pass
                
    elif action.type == ActionType.START_PROCESSING:
        # Side effect: trigger pipeline execution
        side_effects.append(SideEffect(
            type=SideEffectType.RUN_PIPELINE,
            payload={'state': state}
        ))
        
    elif action.type == ActionType.PROCESSING_COMPLETE:
        new_state = CoreState(
            **{
                **state.to_session_state_updates(),
                'processing_complete': True,
            }
        )
        
    elif action.type == ActionType.SELECT_SERIES:
        payload: SelectSeriesPayload = action.payload
        # Navigation doesn't change CoreState, handled by UI layer
        side_effects.append(SideEffect(
            type=SideEffectType.REBUILD_VIEWER,
            payload={'series_idx': payload.series_idx}
        ))
        
    elif action.type == ActionType.SELECT_INSTANCE:
        payload: SelectInstancePayload = action.payload
        # Navigation doesn't change CoreState, handled by UI layer
        pass
        
    elif action.type == ActionType.RESET_RUN:
        # Return empty state - actual reset handled by UI layer
        new_state = CoreState()
        side_effects.append(SideEffect(type=SideEffectType.RERUN))
    
    return ActionResult(
        state=new_state,
        side_effects=side_effects,
        success=True,
    )
