//! Stable C ABI used by the SwiftUI front end on iOS and iPadOS.

use sh_engine::Engine;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::path::Path;
use std::ptr;
use std::sync::OnceLock;

static ENGINE: OnceLock<Engine> = OnceLock::new();

fn catch<T>(default: T, f: impl FnOnce() -> T) -> T {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)).unwrap_or(default)
}

fn input_string(value: *const c_char) -> Option<String> {
    if value.is_null() {
        return None;
    }
    // SAFETY: callers must provide a valid NUL-terminated string for the duration of this call.
    unsafe { CStr::from_ptr(value) }
        .to_str()
        .ok()
        .map(str::to_owned)
}

fn output_string(value: String) -> *mut c_char {
    CString::new(value)
        .unwrap_or_else(|_| CString::new(r#"{"ok":false,"error":"invalid response"}"#).unwrap())
        .into_raw()
}

#[no_mangle]
pub extern "C" fn sh_apple_init(data_dir: *const c_char) -> bool {
    catch(false, || {
        let Some(data_dir) = input_string(data_dir) else {
            return false;
        };
        ENGINE.get_or_init(|| Engine::new(Path::new(&data_dir)));
        true
    })
}

#[no_mangle]
pub extern "C" fn sh_apple_command(json: *const c_char) -> *mut c_char {
    catch(ptr::null_mut(), || {
        let Some(json) = input_string(json) else {
            return output_string(r#"{"ok":false,"error":"invalid command"}"#.into());
        };
        let response = match ENGINE.get() {
            Some(engine) => engine.command(&json),
            None => r#"{"ok":false,"error":"engine not started"}"#.into(),
        };
        output_string(response)
    })
}

#[no_mangle]
pub extern "C" fn sh_apple_string_free(value: *mut c_char) {
    if !value.is_null() {
        // SAFETY: value must have been returned by output_string and may be freed once.
        unsafe { drop(CString::from_raw(value)) };
    }
}

/// Returns `(row_count << 16) | (bin_count / 16)`, matching the Android bridge.
#[no_mangle]
pub extern "C" fn sh_apple_spectrum_rows(
    output: *mut f32,
    output_len: usize,
    metadata: *mut f64,
    metadata_len: usize,
) -> u32 {
    catch(0, || {
        if output.is_null() || metadata.is_null() || metadata_len < 2 {
            return 0;
        }
        let Some(engine) = ENGINE.get() else { return 0 };
        // SAFETY: Swift owns these buffers and guarantees the supplied writable lengths.
        let output = unsafe { std::slice::from_raw_parts_mut(output, output_len) };
        let metadata = unsafe { std::slice::from_raw_parts_mut(metadata, metadata_len) };
        let (rows, bins) = engine.spectrum_rows(output, metadata);
        ((rows as u32) << 16) | ((bins as u32) / 16)
    })
}

#[no_mangle]
pub extern "C" fn sh_apple_audio(output: *mut f32, output_len: usize) -> usize {
    catch(0, || {
        if output.is_null() {
            return 0;
        }
        let Some(engine) = ENGINE.get() else { return 0 };
        // SAFETY: Swift owns this buffer and guarantees the supplied writable length.
        engine.audio(unsafe { std::slice::from_raw_parts_mut(output, output_len) })
    })
}
