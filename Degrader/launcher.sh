#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_MAIN="$SCRIPT_DIR/run_gui.py"

VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

source "$SCRIPT_DIR/common_launcher_funcs.sh"

enable_logging_action() {
    log_info "Logging control is not implemented in this project."
}
disable_logging_action() {
    log_info "Logging control is not implemented in this project."
}

show_help() {
    echo "Project Degrader - GUI Launcher"
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  run                Run the application (default action)."
    echo "  install            Create the virtual environment and/or install dependencies."
    echo "  recreate           Forcibly recreate the virtual environment."
    echo "  delete             Delete the virtual environment and caches."
    echo "  help               Show this help message."
}

recreate_action() {
    log_info "Recreating virtual environment..."
    if [ -d "$VENV_DIR" ]; then
        log_info "Removing existing venv in '$VENV_DIR'..."
        deactivate_venv
        if rm -rf "$VENV_DIR"; then
            log_status "Existing venv removed" 0
        else
            log_status "Failed to remove venv. Remove manually" 1
            exit 1
        fi
    fi
    ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"
}

delete_action() {
    log_info "Starting cleanup..."
    if [ -d "$VENV_DIR" ]; then
        log_info "Removing virtual environment in '$VENV_DIR'..."
        deactivate_venv
        rm -rf "$VENV_DIR"
        log_status "Virtual environment removed" 0
    else
        log_info "Virtual environment not found, skipping."
    fi

    log_info "Removing '__pycache__' directories..."
    find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} +
    log_status "'__pycache__' directories removed" 0
    log_info "Cleanup completed."
}

COMMAND=${1:-run}

case "$COMMAND" in

install)
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        log_info "Environment is ready."
    else
        log_status "Failed to set up environment." 1
        exit 1
    fi
    deactivate_venv
    ;;

run)
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        log_info "Starting Project Degrader application..."
        
        export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
        python "$APP_MAIN"
        
        app_exit_code=$?
        deactivate_venv
        log_info "Application completed with exit code: $app_exit_code"
        exit $app_exit_code
    else
        deactivate_venv
        log_status "Failed to prepare environment. Aborting." 1
        exit 1
    fi
    # -----------------------------------
    ;;

recreate)
    recreate_action
    deactivate_venv
    ;;

delete)
    delete_action
    ;;
--enable-logging | --disable-logging)
    log_info "Logging control is not implemented for this project."
    ;;
help | --help)
    show_help
    ;;
*)
    log_info "Error: Unknown command '$COMMAND'"
    show_help
    exit 1
    ;;
esac

exit 0