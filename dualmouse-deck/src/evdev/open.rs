use anyhow::{Context, Result};
use evdev::Device;
use std::fs::OpenOptions;
use std::path::Path;

pub fn open_device(path: &Path) -> Result<Device> {
    let file = OpenOptions::new()
        .read(true)
        .open(path)
        .with_context(|| format!("failed to open {}", path.display()))?;
    let mut device = Device::new_from_file(file)?;
    device.set_non_blocking(true)?;
    Ok(device)
}
