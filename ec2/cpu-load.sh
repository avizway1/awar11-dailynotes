#!/bin/bash
# =====================================================================
#  cpu-load.sh  -  Gradual CPU load generator for Auto Scaling testing
#  Aviz Academy | avizacademy.com | Learn by Doing, Not Just Watching
# ---------------------------------------------------------------------
#  How it works (simple idea):
#   - Start one "yes" process per vCPU. "yes" burns 100% of a core.
#   - Every 1 second we act like a traffic signal:
#       GREEN  (run)   for X% of the second
#       RED    (pause) for the rest of the second
#     So 30% target = run 0.3s, pause 0.7s  ->  ~30% CPU usage.
#   - Every STEP_INTERVAL seconds, the target goes up by STEP_PERCENT.
#   - At MAX_PERCENT it holds for HOLD_TIME, then stops automatically
#     so you can also watch the ASG scale IN.
#
#  No extra packages needed (works on Amazon Linux 2 and 2023).
# =====================================================================

# ------------------- Settings (students can change) -------------------
# You can edit here OR override while running, e.g.:
#   STEP_PERCENT=20 STEP_INTERVAL=120 ./cpu-load.sh
STEP_PERCENT=${STEP_PERCENT:-30}     # Increase CPU by this % each step
STEP_INTERVAL=${STEP_INTERVAL:-60}   # Seconds to stay on each step
MAX_PERCENT=${MAX_PERCENT:-100}      # Highest CPU % to reach
HOLD_TIME=${HOLD_TIME:-900}          # Seconds to hold at MAX before stopping
CPU_CORES=${CPU_CORES:-$(nproc)}     # Load all vCPUs (CloudWatch shows the average)
REPORT_EVERY=${REPORT_EVERY:-10}     # Print actual CPU usage every N seconds
# ----------------------------------------------------------------------

SLICE_MS=1000        # 1 second "traffic signal" cycle
YES_PIDS=()
THROTTLE_PID=""

# ---------- Validate inputs ----------
for var in STEP_PERCENT STEP_INTERVAL MAX_PERCENT HOLD_TIME CPU_CORES REPORT_EVERY; do
  if ! [[ "${!var}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: $var must be a whole number (current value: '${!var}')"
    exit 1
  fi
done
if (( STEP_PERCENT < 1 || STEP_PERCENT > 100 || MAX_PERCENT < 1 || MAX_PERCENT > 100 )); then
  echo "ERROR: STEP_PERCENT and MAX_PERCENT must be between 1 and 100"
  exit 1
fi
if (( STEP_INTERVAL < 1 || REPORT_EVERY < 1 || CPU_CORES < 1 )); then
  echo "ERROR: STEP_INTERVAL, REPORT_EVERY and CPU_CORES must be at least 1"
  exit 1
fi

# ---------- Helper: convert milliseconds to "S.mmm" for sleep ----------
ms_to_sec() {
  printf '%d.%03d' $(( $1 / 1000 )) $(( $1 % 1000 ))
}

# ---------- Measure real CPU usage over N seconds (from /proc/stat) ----------
measure_cpu() {
  local _ u n s i w irq sirq st t1 i1 t2 i2 dt di
  read -r _ u n s i w irq sirq st _ < /proc/stat
  t1=$(( u + n + s + i + w + irq + sirq + st )); i1=$(( i + w ))
  sleep "$1"
  read -r _ u n s i w irq sirq st _ < /proc/stat
  t2=$(( u + n + s + i + w + irq + sirq + st )); i2=$(( i + w ))
  dt=$(( t2 - t1 )); di=$(( i2 - i1 ))
  (( dt > 0 )) && echo $(( 100 * (dt - di) / dt )) || echo 0
}

# ---------- The traffic signal: resume/pause the yes processes ----------
throttle_loop() {
  local busy_ms=$(( SLICE_MS * $1 / 100 ))
  local idle_ms=$(( SLICE_MS - busy_ms ))
  local busy_s idle_s
  busy_s=$(ms_to_sec "$busy_ms")
  idle_s=$(ms_to_sec "$idle_ms")

  while true; do
    kill -CONT "${YES_PIDS[@]}" 2>/dev/null     # GREEN: burn CPU
    sleep "$busy_s"
    if (( idle_ms > 0 )); then
      kill -STOP "${YES_PIDS[@]}" 2>/dev/null   # RED: pause
      sleep "$idle_s"
    fi
  done
}

# ---------- Start load at a given percentage ----------
start_load() {
  YES_PIDS=()
  for (( c = 0; c < CPU_CORES; c++ )); do
    yes > /dev/null &
    YES_PIDS+=($!)
  done
  throttle_loop "$1" &
  THROTTLE_PID=$!
}

# ---------- Stop all load processes ----------
stop_load() {
  [[ -n "$THROTTLE_PID" ]] && kill "$THROTTLE_PID" 2>/dev/null
  if (( ${#YES_PIDS[@]} > 0 )); then
    kill -CONT "${YES_PIDS[@]}" 2>/dev/null   # wake paused ones so they can exit
    kill "${YES_PIDS[@]}" 2>/dev/null
  fi
  wait 2>/dev/null
  YES_PIDS=()
  THROTTLE_PID=""
}

# ---------- Clean exit on Ctrl+C or kill ----------
cleanup() {
  echo
  echo ">>> Interrupted. Stopping CPU load..."
  stop_load
  echo ">>> Load stopped. CPU will return to normal."
  exit 0
}
trap cleanup INT TERM

# ---------- Run one level for a duration, printing live stats ----------
run_level() {
  local target=$1 duration=$2 elapsed=0 chunk actual
  start_load "$target"
  while (( elapsed < duration )); do
    chunk=$(( duration - elapsed ))
    (( chunk > REPORT_EVERY )) && chunk=$REPORT_EVERY
    actual=$(measure_cpu "$chunk")
    elapsed=$(( elapsed + chunk ))
    printf '[%s]  Target: %3d%%  |  Actual CPU: %3d%%  |  %4ds left on this step\n' \
      "$(date +%H:%M:%S)" "$target" "$actual" $(( duration - elapsed ))
  done
  stop_load
}

# ---------- Summary ----------
steps_below_max=$(( (MAX_PERCENT - 1) / STEP_PERCENT ))
total_time=$(( steps_below_max * STEP_INTERVAL + HOLD_TIME ))

echo "=============================================================="
echo "  Gradual CPU Load Test  (Auto Scaling Group demo)"
echo "=============================================================="
echo "  vCPUs to load    : $CPU_CORES"
echo "  Step increase    : +${STEP_PERCENT}% every ${STEP_INTERVAL}s"
echo "  Max CPU target   : ${MAX_PERCENT}% (hold for ${HOLD_TIME}s)"
echo "  Estimated time   : $(( total_time / 60 ))m $(( total_time % 60 ))s"
echo "  Stop anytime     : Ctrl+C"
echo "=============================================================="

# ---------- Main: climb the stairs ----------
level=0
while true; do
  level=$(( level + STEP_PERCENT ))
  if (( level >= MAX_PERCENT )); then
    level=$MAX_PERCENT
    echo ">>> Reached MAX: ${level}%  - holding for ${HOLD_TIME}s"
    (( HOLD_TIME > 0 )) && run_level "$level" "$HOLD_TIME"
    break
  fi
  echo ">>> Step up: CPU target ${level}%"
  run_level "$level" "$STEP_INTERVAL"
done

echo "=============================================================="
echo "  Load test complete. CPU is back to normal."
echo "  Now watch the ASG scale IN (this is slower than scale OUT)."
echo "=============================================================="
