use crate::evdev::DeviceSource;
use crate::state::cursor::{Button, CursorEvent, CursorId};
use anyhow::Result;
use evdev::{AbsoluteAxisType, InputEvent, InputEventKind, Key, RelativeAxisType};
use log::{debug, warn};
use std::ops::RangeInclusive;

#[derive(Clone, Debug)]
pub enum MappingStrategy {
    DevicePerCursor { cursor: CursorId },
    SingleDevice { mapping: SingleDeviceMapping },
}

#[derive(Clone, Debug)]
pub enum SingleDeviceMapping {
    Unknown,
    ByAbsAxisRange {
        axis: AbsoluteAxisType,
        left: RangeInclusive<i32>,
        right: RangeInclusive<i32>,
    },
    ByEventCodeRange {
        left: RangeInclusive<u16>,
        right: RangeInclusive<u16>,
    },
    ByTrackingIdParity,
}

#[derive(Clone, Debug, Default)]
struct PendingMotion {
    dx: f32,
    dy: f32,
    wheel: i32,
    button: Option<(Button, bool)>,
}

#[derive(Clone, Debug, Default)]
struct AbsState {
    last_x: Option<i32>,
    last_y: Option<i32>,
    cur_x: Option<i32>,
    cur_y: Option<i32>,
}

#[derive(Clone, Debug, Default)]
struct MtSlotState {
    tracking_id: Option<i32>,
    cursor: Option<CursorId>,
    last_x: Option<i32>,
    last_y: Option<i32>,
    cur_x: Option<i32>,
    cur_y: Option<i32>,
}

pub struct Decoder {
    mapping: MappingStrategy,
    pending_left: PendingMotion,
    pending_right: PendingMotion,
    abs_left: AbsState,
    abs_right: AbsState,
    mt_slots: Vec<MtSlotState>,
    mt_cur_slot: i32,
    mt_left_tracking: Option<i32>,
    mt_right_tracking: Option<i32>,
    active_cursor: CursorId,
    warned_unknown: bool,
    last_abs_x: Option<i32>,
    abs_scale: f32,
}

impl Decoder {
    pub fn new(mapping: MappingStrategy, abs_scale: f32) -> Self {
        Self {
            mapping,
            pending_left: PendingMotion::default(),
            pending_right: PendingMotion::default(),
            abs_left: AbsState::default(),
            abs_right: AbsState::default(),
            mt_slots: Vec::new(),
            mt_cur_slot: 0,
            mt_left_tracking: None,
            mt_right_tracking: None,
            active_cursor: CursorId::Left,
            warned_unknown: false,
            last_abs_x: None,
            abs_scale,
        }
    }

    pub fn decode(
        &mut self,
        event: InputEvent,
        source: &DeviceSource,
    ) -> Result<Vec<CursorEvent>> {
        let cursor = self.cursor_for_event(&event, source);

        match event.kind() {
            InputEventKind::RelAxis(axis) => {
                let pending = self.pending_mut(cursor);
                match axis {
                    RelativeAxisType::REL_X => pending.dx += event.value() as f32,
                    RelativeAxisType::REL_Y => pending.dy += event.value() as f32,
                    RelativeAxisType::REL_WHEEL => pending.wheel += event.value(),
                    _ => {}
                }
            }
            InputEventKind::Key(key) => {
                if let Some(button) = map_button(key) {
                    let pending = self.pending_mut(cursor);
                    pending.button = Some((button, event.value() != 0));
                }
            }
            InputEventKind::AbsAxis(axis) => {
                self.last_abs_x = if axis == AbsoluteAxisType::ABS_MT_POSITION_X {
                    Some(event.value())
                } else {
                    self.last_abs_x
                };
                self.update_mapping_from_abs(axis, event.value());
                self.update_abs_position(cursor, axis, event.value());
            }
            InputEventKind::Sync(_) => {
                return Ok(self.flush());
            }
            _ => {}
        }

        Ok(Vec::new())
    }

    fn flush(&mut self) -> Vec<CursorEvent> {
        self.apply_mt_deltas();
        let mut events = Vec::new();
        for cursor in [CursorId::Left, CursorId::Right] {
            let (abs_dx, abs_dy) = self.abs_delta(cursor);
            let mut pending = self.take_pending(cursor);
            let dx = pending.dx + abs_dx;
            let dy = pending.dy + abs_dy;

            if dx == 0.0 && dy == 0.0 && pending.wheel == 0 && pending.button.is_none() {
                continue;
            }

            events.push(CursorEvent {
                cursor,
                dx,
                dy,
                wheel: pending.wheel,
                button: pending.button.take(),
            });
        }

        events
    }

    fn cursor_for_event(&mut self, event: &InputEvent, source: &DeviceSource) -> CursorId {
        match &mut self.mapping {
            MappingStrategy::DevicePerCursor { cursor } => *cursor,
            MappingStrategy::SingleDevice { mapping } => {
                if let Some(cursor) = cursor_from_single_mapping(mapping, event, self.last_abs_x)
                {
                    self.active_cursor = cursor;
                } else if matches!(mapping, SingleDeviceMapping::Unknown) && !self.warned_unknown {
                    warn!(
                        "Single device '{}' has no left/right mapping yet; defaulting to Left",
                        source.name
                    );
                    self.warned_unknown = true;
                }
                self.active_cursor
            }
        }
    }

    fn update_mapping_from_abs(&mut self, axis: AbsoluteAxisType, value: i32) {
        if let MappingStrategy::SingleDevice { mapping } = &self.mapping {
            if let SingleDeviceMapping::ByAbsAxisRange { axis: map_axis, left, right } = mapping {
                if axis == *map_axis {
                    if left.contains(&value) {
                        self.active_cursor = CursorId::Left;
                    } else if right.contains(&value) {
                        self.active_cursor = CursorId::Right;
                    }
                }
            }
        }
    }

    fn update_abs_position(&mut self, cursor: CursorId, axis: AbsoluteAxisType, value: i32) {
        match axis {
            AbsoluteAxisType::ABS_MT_SLOT => self.mt_cur_slot = value,
            AbsoluteAxisType::ABS_MT_TRACKING_ID => self.handle_mt_tracking_id(value),
            AbsoluteAxisType::ABS_MT_POSITION_X => self.update_mt_slot_position(axis, value),
            AbsoluteAxisType::ABS_MT_POSITION_Y => self.update_mt_slot_position(axis, value),
            AbsoluteAxisType::ABS_X => self.update_abs_axis(cursor, axis, value),
            AbsoluteAxisType::ABS_Y => self.update_abs_axis(cursor, axis, value),
            _ => {}
        }
    }

    fn abs_delta(&mut self, cursor: CursorId) -> (f32, f32) {
        let state = self.abs_state_mut(cursor);
        let (cx, cy) = match (state.cur_x.take(), state.cur_y.take()) {
            (Some(x), Some(y)) => (x, y),
            (Some(x), None) => {
                state.cur_x = Some(x);
                return (0.0, 0.0);
            }
            (None, Some(y)) => {
                state.cur_y = Some(y);
                return (0.0, 0.0);
            }
            (None, None) => return (0.0, 0.0),
        };

        let (lx, ly) = match (state.last_x, state.last_y) {
            (Some(lx), Some(ly)) => (lx, ly),
            _ => {
                state.last_x = Some(cx);
                state.last_y = Some(cy);
                return (0.0, 0.0);
            }
        };

        state.last_x = Some(cx);
        state.last_y = Some(cy);
        (
            (cx - lx) as f32 * self.abs_scale,
            (cy - ly) as f32 * self.abs_scale,
        )
    }

    fn update_abs_axis(&mut self, cursor: CursorId, axis: AbsoluteAxisType, value: i32) {
        let state = self.abs_state_mut(cursor);
        match axis {
            AbsoluteAxisType::ABS_X => state.cur_x = Some(value),
            AbsoluteAxisType::ABS_Y => state.cur_y = Some(value),
            _ => {}
        }
    }

    fn handle_mt_tracking_id(&mut self, value: i32) {
        let slot_index = match usize::try_from(self.mt_cur_slot) {
            Ok(index) => index,
            Err(_) => return,
        };

        self.ensure_slot(slot_index);
        let slot = &mut self.mt_slots[slot_index];

        if value < 0 {
            if let Some(tracking_id) = slot.tracking_id {
                self.release_tracking(tracking_id);
            }
            slot.tracking_id = None;
            slot.cursor = None;
            slot.cur_x = None;
            slot.cur_y = None;
            slot.last_x = None;
            slot.last_y = None;
            return;
        }

        slot.tracking_id = Some(value);
        if let Some(cursor) = self.assign_tracking(value) {
            slot.cursor = Some(cursor);
            slot.cur_x = None;
            slot.cur_y = None;
            slot.last_x = None;
            slot.last_y = None;
        }
    }

    fn update_mt_slot_position(&mut self, axis: AbsoluteAxisType, value: i32) {
        let slot_index = match usize::try_from(self.mt_cur_slot) {
            Ok(index) => index,
            Err(_) => return,
        };
        self.ensure_slot(slot_index);
        let slot = &mut self.mt_slots[slot_index];

        match axis {
            AbsoluteAxisType::ABS_MT_POSITION_X => slot.cur_x = Some(value),
            AbsoluteAxisType::ABS_MT_POSITION_Y => slot.cur_y = Some(value),
            _ => {}
        }
    }

    fn apply_mt_deltas(&mut self) {
        for slot in &mut self.mt_slots {
            let cursor = match slot.cursor {
                Some(cursor) => cursor,
                None => continue,
            };

            let (cx, cy) = match (slot.cur_x.take(), slot.cur_y.take()) {
                (Some(x), Some(y)) => (x, y),
                (Some(x), None) => {
                    slot.cur_x = Some(x);
                    continue;
                }
                (None, Some(y)) => {
                    slot.cur_y = Some(y);
                    continue;
                }
                (None, None) => continue,
            };

            let (lx, ly) = match (slot.last_x, slot.last_y) {
                (Some(lx), Some(ly)) => (lx, ly),
                _ => {
                    slot.last_x = Some(cx);
                    slot.last_y = Some(cy);
                    continue;
                }
            };

            slot.last_x = Some(cx);
            slot.last_y = Some(cy);

            let pending = self.pending_mut(cursor);
            pending.dx += (cx - lx) as f32 * self.abs_scale;
            pending.dy += (cy - ly) as f32 * self.abs_scale;
        }
    }

    fn assign_tracking(&mut self, tracking_id: i32) -> Option<CursorId> {
        if self.mt_left_tracking == Some(tracking_id) {
            return Some(CursorId::Left);
        }
        if self.mt_right_tracking == Some(tracking_id) {
            return Some(CursorId::Right);
        }
        if self.mt_left_tracking.is_none() {
            self.mt_left_tracking = Some(tracking_id);
            debug!("Assigned tracking id {tracking_id} -> Left cursor");
            return Some(CursorId::Left);
        }
        if self.mt_right_tracking.is_none() {
            self.mt_right_tracking = Some(tracking_id);
            debug!("Assigned tracking id {tracking_id} -> Right cursor");
            return Some(CursorId::Right);
        }
        debug!("Ignoring extra tracking id {tracking_id}");
        None
    }

    fn release_tracking(&mut self, tracking_id: i32) {
        if self.mt_left_tracking == Some(tracking_id) {
            self.mt_left_tracking = None;
            debug!("Released tracking id {tracking_id} from Left cursor");
        }
        if self.mt_right_tracking == Some(tracking_id) {
            self.mt_right_tracking = None;
            debug!("Released tracking id {tracking_id} from Right cursor");
        }
    }

    fn ensure_slot(&mut self, slot_index: usize) {
        if self.mt_slots.len() <= slot_index {
            self.mt_slots
                .resize_with(slot_index + 1, MtSlotState::default);
        }
    }

    fn pending_mut(&mut self, cursor: CursorId) -> &mut PendingMotion {
        match cursor {
            CursorId::Left => &mut self.pending_left,
            CursorId::Right => &mut self.pending_right,
        }
    }

    fn take_pending(&mut self, cursor: CursorId) -> PendingMotion {
        match cursor {
            CursorId::Left => std::mem::take(&mut self.pending_left),
            CursorId::Right => std::mem::take(&mut self.pending_right),
        }
    }

    fn abs_state_mut(&mut self, cursor: CursorId) -> &mut AbsState {
        match cursor {
            CursorId::Left => &mut self.abs_left,
            CursorId::Right => &mut self.abs_right,
        }
    }
}

fn cursor_from_single_mapping(
    mapping: &SingleDeviceMapping,
    event: &InputEvent,
    last_abs_x: Option<i32>,
) -> Option<CursorId> {
    match mapping {
        SingleDeviceMapping::Unknown => None,
        SingleDeviceMapping::ByTrackingIdParity => {
            if matches!(event.kind(), InputEventKind::AbsAxis(AbsoluteAxisType::ABS_MT_TRACKING_ID)) {
                if event.value() % 2 == 0 {
                    Some(CursorId::Left)
                } else {
                    Some(CursorId::Right)
                }
            } else {
                None
            }
        }
        SingleDeviceMapping::ByEventCodeRange { left, right } => {
            let code = event.code();
            if left.contains(&code) {
                Some(CursorId::Left)
            } else if right.contains(&code) {
                Some(CursorId::Right)
            } else {
                None
            }
        }
        SingleDeviceMapping::ByAbsAxisRange { axis, left, right } => {
            if matches!(event.kind(), InputEventKind::AbsAxis(current_axis) if &current_axis == axis) {
                let value = event.value();
                if left.contains(&value) {
                    Some(CursorId::Left)
                } else if right.contains(&value) {
                    Some(CursorId::Right)
                } else {
                    None
                }
            } else if let Some(value) = last_abs_x {
                if left.contains(&value) {
                    Some(CursorId::Left)
                } else if right.contains(&value) {
                    Some(CursorId::Right)
                } else {
                    None
                }
            } else {
                None
            }
        }
    }
}

fn map_button(key: Key) -> Option<Button> {
    match key {
        Key::BTN_LEFT => Some(Button::Left),
        Key::BTN_RIGHT => Some(Button::Right),
        Key::BTN_MIDDLE => Some(Button::Middle),
        _ => None,
    }
}
