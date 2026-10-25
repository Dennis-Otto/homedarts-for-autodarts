# shellcheck shell=bash
# Sourced by run.sh, browser.sh and screenshots.sh: what a run that failed or was
# stopped prints about the containers of its Compose project, and how a signal stops
# it (docs/development.md#when-a-step-hangs).

# The state of the containers of a project, what each of them uses of the CPU and the
# memory, and the last lines of the log of Home Assistant: diagnose 300 docker
# compose --project-name homedarts_e2e --file compose.yaml.
diagnose() {
	local lines="$1"
	shift
	"$@" ps --all || true
	"$@" stats --no-stream || true
	"$@" exec -T homeassistant tail -n "${lines}" /config/home-assistant.log || true
}

# A signal stops the run as a failure, and the trap on EXIT then prints and keeps what
# a failed run keeps: SIGINT, with which GitHub stops a step that runs out of time
# (timeout-minutes of the step) and Ctrl+C stops a run on a machine, and SIGTERM,
# which GitHub sends 7.5 s later. Bash runs a trap only between two commands, so a
# long command runs with in_background, whose wait a signal ends at once. STOPPED
# names the signal, such as SIGINT, for the scripts that source this file.
STOPPED=""
# shellcheck disable=SC2034 # STOPPED, which the scripts that source this file read
stopped() {
	STOPPED="SIG$1"
	echo "Stopped by SIG$1; the state and the logs of the containers follow." >&2
	exit "$2"
}
trap 'stopped INT 130' INT
trap 'stopped TERM 143' TERM

# In the trap on EXIT: a further signal, such as the SIGTERM after GitHub's SIGINT,
# lets it finish, until GitHub ends the step 2.5 s after that.
keep_cleaning() {
	trap ':' INT TERM
}

# Run a command, a function too, in the background and wait for it, with its status.
# BACKGROUND keeps its process for end_background while it runs.
BACKGROUND=""
in_background() {
	local status=0
	"$@" &
	BACKGROUND=$!
	wait "${BACKGROUND}" || status=$?
	BACKGROUND=""
	return "${status}"
}

# In the trap on EXIT, before anything else: end the command that a signal stopped the
# wait for, and wait until it has ended, so that nothing of the step outlives it and
# the diagnosis shows the containers only after it.
end_background() {
	if [[ -n "${BACKGROUND}" ]]; then
		kill "${BACKGROUND}" 2>/dev/null || true
		wait "${BACKGROUND}" 2>/dev/null || true
	fi
}
