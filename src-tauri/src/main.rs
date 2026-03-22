#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::Duration,
};

use tauri::{Manager, State};

struct BackendState {
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn backend_status() -> String {
    "local-backend-managed-by-tauri".to_string()
}

fn spawn_backend(app_handle: &tauri::AppHandle, state: &State<BackendState>) -> Result<(), String> {
    let app_data_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|err| err.to_string())?;
    std::fs::create_dir_all(&app_data_dir).map_err(|err| err.to_string())?;

    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .ok_or_else(|| "Could not determine repository root".to_string())?
        .to_path_buf();

    let python = std::env::var("COMPUTERAGENT_PYTHON").unwrap_or_else(|_| "python".to_string());
    let mut command = Command::new(python);
    command
        .arg("-m")
        .arg("backend.computeragent.server")
        .current_dir(&repo_root)
        .env("COMPUTERAGENT_DATA_DIR", &app_data_dir)
        .env("COMPUTERAGENT_BACKEND_PORT", "8765")
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command.spawn().map_err(|err| format!("Failed to start Python backend: {err}"))?;
    *state.child.lock().map_err(|_| "Could not store backend handle".to_string())? = Some(child);
    thread::sleep(Duration::from_millis(900));
    Ok(())
}

fn stop_backend(state: &State<BackendState>) {
    if let Ok(mut guard) = state.child.lock() {
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
        }
        *guard = None;
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![backend_status])
        .setup(|app| {
            let handle = app.handle().clone();
            let state = app.state::<BackendState>();
            spawn_backend(&handle, &state)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<BackendState>();
                stop_backend(&state);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running ComputerAgent");
}
