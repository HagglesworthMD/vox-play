use std::collections::BTreeSet;

#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum CursorId {
    Left,
    Right,
}

#[derive(Copy, Clone, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum Button {
    Left,
    Right,
    Middle,
}

#[derive(Clone, Debug)]
pub struct CursorState {
    pub id: CursorId,
    pub x: f32,
    pub y: f32,
    pub buttons: BTreeSet<Button>,
}

#[derive(Clone, Debug)]
pub struct CursorEvent {
    pub cursor: CursorId,
    pub dx: f32,
    pub dy: f32,
    pub wheel: i32,
    pub button: Option<(Button, bool)>,
}

impl CursorState {
    pub fn new(id: CursorId) -> Self {
        Self {
            id,
            x: 0.0,
            y: 0.0,
            buttons: BTreeSet::new(),
        }
    }

    pub fn apply(&mut self, event: CursorEvent) {
        self.x += event.dx;
        self.y += event.dy;
        if let Some((button, down)) = event.button {
            if down {
                self.buttons.insert(button);
            } else {
                self.buttons.remove(&button);
            }
        }
    }
}
