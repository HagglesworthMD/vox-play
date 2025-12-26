use anyhow::{Context, Result};
use std::time::{Duration, Instant};

mod evdev;
mod state;

use evdev::{discover_sources, sources_from_env, EvdevDaemon};
use state::cursor::{CursorEvent, CursorId, CursorState};

fn main() -> Result<()> {
    env_logger::init();

    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|arg| arg == "--list-devices") {
        let sources = discover_sources().context("discover_sources failed")?;
        if sources.is_empty() {
            println!("No candidate devices discovered.");
        } else {
            for source in sources {
                println!(
                    "{}\t{}\t{:?}",
                    source.path.display(),
                    source.name,
                    source.cursor_hint
                );
            }
        }
        return Ok(());
    }

    let sources = if let Some(sources) = sources_from_env()? {
        sources
    } else {
        discover_sources().context("discover_sources failed")?
    };
    if sources.is_empty() {
        anyhow::bail!(
            "No input sources discovered. Check permissions, Steam Input, or /dev/input/event* access."
        );
    }

    let mut daemon = EvdevDaemon::new(sources)?;

    let mut left = CursorState::new(CursorId::Left);
    let mut right = CursorState::new(CursorId::Right);

    let mut last_print = Instant::now();
    loop {
        let events = daemon.poll(Duration::from_millis(8))?;
        for event in events {
            apply_event(&mut left, &mut right, event);
        }

        if last_print.elapsed() > Duration::from_millis(50) {
            println!(
                "L: ({:>7.1},{:>7.1}) btn={:?}  |  R: ({:>7.1},{:>7.1}) btn={:?}",
                left.x, left.y, left.buttons, right.x, right.y, right.buttons
            );
            last_print = Instant::now();
        }
    }
}

fn apply_event(left: &mut CursorState, right: &mut CursorState, event: CursorEvent) {
    match event.cursor {
        CursorId::Left => left.apply(event),
        CursorId::Right => right.apply(event),
    }
}
