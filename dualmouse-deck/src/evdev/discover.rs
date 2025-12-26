use crate::evdev::DeviceSource;
use crate::state::cursor::CursorId;
use anyhow::{Context, Result};
use evdev::{AbsoluteAxisType, Device, EventType, RelativeAxisType};
use log::{debug, warn};
use std::fs;
use std::path::{Path, PathBuf};
use std::str::FromStr;

pub fn discover_sources() -> Result<Vec<DeviceSource>> {
    let mut sources = Vec::new();
    let input_dir = Path::new("/dev/input");

    let entries = match fs::read_dir(input_dir) {
        Ok(entries) => entries,
        Err(err) => {
            warn!("failed to read /dev/input: {err}");
            return Ok(sources);
        }
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path
            .file_name()
            .and_then(|name| name.to_str())
            .map(|name| name.starts_with("event"))
            .unwrap_or(false)
        {
            continue;
        }

        if let Some(source) = probe_device(&path)? {
            sources.push(source);
        }
    }

    Ok(sources)
}

pub fn sources_from_env() -> Result<Option<Vec<DeviceSource>>> {
    let raw = match std::env::var("DUALMOUSE_SOURCES") {
        Ok(value) if !value.trim().is_empty() => value,
        _ => return Ok(None),
    };

    let mut sources = Vec::new();
    for entry in raw.split(',') {
        let path = PathBuf::from_str(entry.trim())?;
        let source = probe_device(&path).with_context(|| {
            format!("failed to probe device from DUALMOUSE_SOURCES: {}", path.display())
        })?;
        if let Some(source) = source {
            sources.push(source);
        } else {
            warn!("skipping {} (not pointer-like or unreadable)", path.display());
        }
    }

    Ok(Some(sources))
}

fn probe_device(path: &Path) -> Result<Option<DeviceSource>> {
    let file = match fs::File::open(path) {
        Ok(file) => file,
        Err(_) => return Ok(None),
    };

    let device = match Device::new_from_file(file) {
        Ok(device) => device,
        Err(_) => return Ok(None),
    };

    if !looks_like_pointer_surface(&device) {
        debug!("skip {} (not pointer-like)", path.display());
        return Ok(None);
    }

    let name = device
        .name()
        .map(|name| name.to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let cursor_hint = guess_cursor_hint(&name);
    debug!("candidate device: {} ({})", name, path.display());

    Ok(Some(DeviceSource {
        path: PathBuf::from(path),
        name,
        cursor_hint,
    }))
}

fn looks_like_pointer_surface(device: &Device) -> bool {
    let has_rel_xy = device
        .supported_relative_axes()
        .map(|axes| axes.contains(RelativeAxisType::REL_X) && axes.contains(RelativeAxisType::REL_Y))
        .unwrap_or(false);

    let has_abs_mt_xy = device
        .supported_absolute_axes()
        .map(|axes| {
            axes.contains(AbsoluteAxisType::ABS_MT_POSITION_X)
                && axes.contains(AbsoluteAxisType::ABS_MT_POSITION_Y)
        })
        .unwrap_or(false);

    let has_abs_xy = device
        .supported_absolute_axes()
        .map(|axes| axes.contains(AbsoluteAxisType::ABS_X) && axes.contains(AbsoluteAxisType::ABS_Y))
        .unwrap_or(false);

    let supported = device.supported_events();
    let has_axes = supported.contains(EventType::RELATIVE) || supported.contains(EventType::ABSOLUTE);

    has_axes && (has_rel_xy || has_abs_mt_xy || has_abs_xy)
}

fn guess_cursor_hint(name: &str) -> Option<CursorId> {
    let lower = name.to_lowercase();
    if lower.contains("left") {
        Some(CursorId::Left)
    } else if lower.contains("right") {
        Some(CursorId::Right)
    } else {
        None
    }
}
