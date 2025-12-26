mod decode;
mod discover;
mod open;

use crate::state::cursor::{CursorEvent, CursorId};
use anyhow::{Context, Result};
use decode::{Decoder, MappingStrategy, SingleDeviceMapping};
use log::{debug, info, warn};
use nix::poll::{poll, PollFd, PollFlags};
use open::open_device;
use std::os::unix::io::AsRawFd;
use std::path::PathBuf;
use std::time::Duration;

pub use discover::{discover_sources, sources_from_env};

#[derive(Clone, Debug)]
pub struct DeviceSource {
    pub path: PathBuf,
    pub name: String,
    pub cursor_hint: Option<CursorId>,
}

pub struct EvdevDaemon {
    devices: Vec<DeviceHandle>,
}

struct DeviceHandle {
    source: DeviceSource,
    device: evdev::Device,
    decoder: Decoder,
}

impl EvdevDaemon {
    pub fn new(mut sources: Vec<DeviceSource>) -> Result<Self> {
        assign_cursor_hints(&mut sources);
        let abs_scale = abs_scale_from_env();
        let single_source = sources.len() == 1;
        let mut devices = Vec::new();

        for source in &sources {
            if let Some(cursor) = source.cursor_hint {
                info!(
                    "Assigned {:?} cursor source: {} ({})",
                    cursor,
                    source.name,
                    source.path.display()
                );
            }
        }

        if single_source {
            warn!(
                "Single input source detected: {}. Decoder will attempt left/right mapping.",
                sources[0].name
            );
        }

        for source in sources {
            let device = open_device(&source.path)
                .with_context(|| format!("open_device failed for {}", source.path.display()))?;

            let mapping = match source.cursor_hint {
                Some(cursor) => MappingStrategy::DevicePerCursor { cursor },
                None if single_source => MappingStrategy::SingleDevice {
                    mapping: SingleDeviceMapping::Unknown,
                },
                None => MappingStrategy::SingleDevice {
                    mapping: SingleDeviceMapping::Unknown,
                },
            };

            log_device_capabilities(&source, &device);
            let decoder = Decoder::new(mapping, abs_scale);
            info!("Opened {} ({})", source.name, source.path.display());
            devices.push(DeviceHandle {
                source,
                device,
                decoder,
            });
        }

        Ok(Self { devices })
    }

    pub fn poll(&mut self, timeout: Duration) -> Result<Vec<CursorEvent>> {
        let mut poll_fds: Vec<PollFd> = self
            .devices
            .iter()
            .map(|handle| PollFd::new(handle.device.as_raw_fd(), PollFlags::POLLIN))
            .collect();

        let timeout_ms = timeout.as_millis().min(i32::MAX as u128) as i32;
        let _ = poll(&mut poll_fds, timeout_ms)?;

        let mut output = Vec::new();
        for (idx, poll_fd) in poll_fds.iter().enumerate() {
            if poll_fd
                .revents()
                .unwrap_or(PollFlags::empty())
                .contains(PollFlags::POLLIN)
            {
                let handle = &mut self.devices[idx];
                let events = handle.device.fetch_events()?;
                for event in events {
                    let decoded = handle.decoder.decode(event, &handle.source)?;
                    output.extend(decoded);
                }
            }
        }

        Ok(output)
    }
}

fn assign_cursor_hints(sources: &mut [DeviceSource]) {
    let mut left_idx = None;
    let mut right_idx = None;
    let mut unknown_idx = Vec::new();

    for (idx, source) in sources.iter().enumerate() {
        match source.cursor_hint {
            Some(CursorId::Left) => left_idx = Some(idx),
            Some(CursorId::Right) => right_idx = Some(idx),
            None => unknown_idx.push(idx),
        }
    }

    if sources.len() == 2 {
        match (left_idx, right_idx, unknown_idx.as_slice()) {
            (Some(_), Some(_), _) => {}
            (Some(_), None, [unknown]) => {
                sources[*unknown].cursor_hint = Some(CursorId::Right);
                debug!("Assigned right cursor to {}", sources[*unknown].name);
            }
            (None, Some(_), [unknown]) => {
                sources[*unknown].cursor_hint = Some(CursorId::Left);
                debug!("Assigned left cursor to {}", sources[*unknown].name);
            }
            (None, None, [left, right]) => {
                sources[*left].cursor_hint = Some(CursorId::Left);
                sources[*right].cursor_hint = Some(CursorId::Right);
                debug!(
                    "Assigned default cursors: {} -> Left, {} -> Right",
                    sources[*left].name,
                    sources[*right].name
                );
            }
            _ => {}
        }
    }
}

fn log_device_capabilities(source: &DeviceSource, device: &evdev::Device) {
    let rel_axes = device
        .supported_relative_axes()
        .map(|axes| format!("{axes:?}"))
        .unwrap_or_else(|| "None".to_string());
    let abs_axes = device
        .supported_absolute_axes()
        .map(|axes| format!("{axes:?}"))
        .unwrap_or_else(|| "None".to_string());
    let events = format!("{:?}", device.supported_events());

    debug!(
        "Device capabilities for {} ({}): events={} rel_axes={} abs_axes={}",
        source.name,
        source.path.display(),
        events,
        rel_axes,
        abs_axes
    );
}

fn abs_scale_from_env() -> f32 {
    std::env::var("DUALMOUSE_ABS_SCALE")
        .ok()
        .and_then(|raw| raw.parse::<f32>().ok())
        .filter(|value| *value > 0.0)
        .unwrap_or(0.02)
}
