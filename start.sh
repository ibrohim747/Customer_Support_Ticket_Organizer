#!/usr/bin/env bash
# One-command start. Uses Docker if it is available, otherwise Python 3.10+
# (the program itself needs only the Python standard library — nothing to install).
#
#   ./start.sh                  -> interactive: choose a file, preliminary analysis, confirm, full analysis
#   ./start.sh input/my.csv     -> full analysis of one file, no questions
#   ./start.sh --python ...     -> always use Python (no Docker)
#   ./start.sh --docker ...     -> always use Docker
#
# Put your own CSV files into input/. Results are written to output/.
set -e
cd "$(dirname "$0")"
IMAGE=ticket-organizer

MODE=auto
if [ "$1" = "--python" ] || [ "$1" = "--docker" ]; then
    MODE="${1#--}"
    shift
fi

# Created here, as the current user. If Docker created them, they would belong to root.
mkdir -p input output

docker_ready() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

find_python() {
    # First command that exists and is Python 3.10 or newer.
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1 &&
           "$cmd" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

run_with_python() {
    if ! PYTHON=$(find_python); then
        echo "Python 3.10 or newer is not installed: https://www.python.org/downloads/"
        echo "(or install Docker: https://docs.docker.com/get-docker/)"
        exit 1
    fi
    echo "Running with $("$PYTHON" --version)."
    exec "$PYTHON" -m ticket_organizer "$@"
}

run_with_docker() {
    echo "Preparing the Docker image (the first time takes about a minute)..."
    docker build --quiet --tag "$IMAGE" . >/dev/null

    # -it only when there is a keyboard (a terminal); interactive mode needs it.
    TTY_FLAGS=()
    if [ -t 0 ] && [ -t 1 ]; then
        TTY_FLAGS=(-it)
    fi

    # Home folder at the same path: a file dragged into the terminal (/home/me/...) is found
    # inside the container too, and results can be saved next to it. --user = files are created
    # as you, and the program can only write where you yourself can write.
    exec docker run --rm "${TTY_FLAGS[@]}" \
        --user "$(id -u):$(id -g)" \
        -v "$HOME:$HOME" \
        -v "$PWD/input:/app/input" \
        -v "$PWD/output:/app/output" \
        "$IMAGE" "$@"
}

case "$MODE" in
    python)
        run_with_python "$@"
        ;;
    docker)
        if ! docker_ready; then
            echo "Cannot use Docker."
            echo "  - Is it installed and running?"
            echo "  - Linux: add yourself to the docker group (sudo usermod -aG docker \$USER),"
            echo "    then log out and in again (or run: newgrp docker)."
            exit 1
        fi
        run_with_docker "$@"
        ;;
    auto)
        if docker_ready; then
            run_with_docker "$@"
        else
            echo "Docker is not available — using Python instead."
            run_with_python "$@"
        fi
        ;;
esac
