from __future__ import annotations

import ctypes
import json
import math
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

try:
    import psutil  # type: ignore
except ImportError:  # Windows keeps a native implementation; POSIX installers include psutil.
    psutil = None


MIB = 1024 ** 2
GIB = 1024 ** 3
POLICY_PATH = Path(__file__).resolve().parents[1] / "assets" / "resource-policy.json"


def _load_policy() -> dict[str, Any]:
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"RESOURCE_POLICY_INVALID: {exc}") from exc
    required = {
        "owned_task_budget_bytes", "worker_job_limit_bytes", "orchestrator_reserve_bytes",
        "install_worker_limit_bytes", "install_orchestrator_reserve_bytes",
        "lean_worker_limit_bytes", "lean_orchestrator_reserve_bytes",
        "lean_trim_trigger_bytes",
        "start_min_free_bytes", "run_min_free_bytes", "maximum_parallel_workers", "gpu_allowed",
    }
    if value.get("schema_version") != 1 or not required <= value.keys():
        raise RuntimeError("RESOURCE_POLICY_INVALID: required fields are missing")
    numeric = {key: value[key] for key in required if key not in {"gpu_allowed"}}
    if not all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in numeric.values()):
        raise RuntimeError("RESOURCE_POLICY_INVALID: numeric fields must be positive integers")
    if value["worker_job_limit_bytes"] + value["orchestrator_reserve_bytes"] > value["owned_task_budget_bytes"]:
        raise RuntimeError("RESOURCE_POLICY_INVALID: worker plus orchestrator exceeds the owned-task budget")
    if value["install_worker_limit_bytes"] + value["install_orchestrator_reserve_bytes"] > value["owned_task_budget_bytes"]:
        raise RuntimeError("RESOURCE_POLICY_INVALID: installer worker plus orchestrator exceeds the owned-task budget")
    if value["lean_worker_limit_bytes"] + value["lean_orchestrator_reserve_bytes"] > value["owned_task_budget_bytes"]:
        raise RuntimeError("RESOURCE_POLICY_INVALID: Lean worker plus orchestrator exceeds the owned-task budget")
    if value["lean_trim_trigger_bytes"] >= value["lean_worker_limit_bytes"]:
        raise RuntimeError("RESOURCE_POLICY_INVALID: Lean trim trigger must be below the worker limit")
    if value["maximum_parallel_workers"] != 1 or value["gpu_allowed"] is not False:
        raise RuntimeError("RESOURCE_POLICY_INVALID: only serial CPU execution is admitted")
    if value.get("memory_metric") != "aggregate_working_set":
        raise RuntimeError("RESOURCE_POLICY_INVALID: physical aggregate working set is required")
    return value


RESOURCE_POLICY = _load_policy()
OWNED_TASK_BUDGET_BYTES = int(RESOURCE_POLICY["owned_task_budget_bytes"])
WORKER_JOB_LIMIT_BYTES = int(RESOURCE_POLICY["worker_job_limit_bytes"])
ORCHESTRATOR_RESERVE_BYTES = int(RESOURCE_POLICY["orchestrator_reserve_bytes"])
INSTALL_WORKER_LIMIT_BYTES = int(RESOURCE_POLICY["install_worker_limit_bytes"])
INSTALL_ORCHESTRATOR_RESERVE_BYTES = int(RESOURCE_POLICY["install_orchestrator_reserve_bytes"])
LEAN_WORKER_LIMIT_BYTES = int(RESOURCE_POLICY["lean_worker_limit_bytes"])
LEAN_ORCHESTRATOR_RESERVE_BYTES = int(RESOURCE_POLICY["lean_orchestrator_reserve_bytes"])
LEAN_TRIM_TRIGGER_BYTES = int(RESOURCE_POLICY["lean_trim_trigger_bytes"])
START_MIN_FREE_BYTES = int(RESOURCE_POLICY["start_min_free_bytes"])
RUN_MIN_FREE_BYTES = int(RESOURCE_POLICY["run_min_free_bytes"])
SAMPLING_INTERVAL_SECONDS = float(RESOURCE_POLICY["sampling_interval_seconds"])


class ResourceGuardError(RuntimeError):
    pass


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _assign_memory_job(process: subprocess.Popen[bytes], maximum_job_bytes: int) -> int | None:
    if os.name != "nt":
        if psutil is None:
            raise ResourceGuardError("RESOURCE_TELEMETRY_MISSING: psutil is required on Linux and macOS")
        return process.pid
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    kernel32.SetInformationJobObject.restype = ctypes.c_int
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise ResourceGuardError(f"RESOURCE_JOB_CREATE_FAILED: Windows error {ctypes.get_last_error()}")
    information = _JobExtendedLimitInformation()
    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE keeps the full tree owned without
    # requiring the privileged working-set quota right. Physical memory is
    # enforced by the aggregate Job PID monitor below.
    information.BasicLimitInformation.LimitFlags = 0x2000
    if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(information), ctypes.sizeof(information)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise ResourceGuardError(f"RESOURCE_JOB_LIMIT_FAILED: Windows error {error}")
    process_handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
    if not kernel32.AssignProcessToJobObject(handle, process_handle):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise ResourceGuardError(f"RESOURCE_JOB_ASSIGN_FAILED: Windows error {error}")
    return int(handle)


def _job_process_ids(handle: int | None) -> list[int]:
    if not handle:
        return []
    if os.name != "nt":
        if psutil is None:
            raise ResourceGuardError("RESOURCE_TELEMETRY_MISSING: psutil is required on Linux and macOS")
        try:
            process = psutil.Process(handle)
            return [process.pid, *(child.pid for child in process.children(recursive=True))]
        except psutil.Error:
            return []
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.QueryInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
    ]
    kernel32.QueryInformationJobObject.restype = ctypes.c_int
    capacity = 32
    while capacity <= 4096:
        header = 2 * ctypes.sizeof(ctypes.c_ulong)
        buffer = ctypes.create_string_buffer(header + capacity * ctypes.sizeof(ctypes.c_size_t))
        returned = ctypes.c_ulong()
        if not kernel32.QueryInformationJobObject(
            ctypes.c_void_p(handle), 3, buffer, ctypes.sizeof(buffer), ctypes.byref(returned),
        ):
            raise ResourceGuardError(f"RESOURCE_JOB_QUERY_FAILED: Windows error {ctypes.get_last_error()}")
        assigned = ctypes.c_ulong.from_buffer(buffer, 0).value
        count = ctypes.c_ulong.from_buffer(buffer, ctypes.sizeof(ctypes.c_ulong)).value
        if count >= assigned:
            array_type = ctypes.c_size_t * count
            values = array_type.from_buffer(buffer, header)
            return [int(value) for value in values]
        capacity = max(capacity * 2, int(assigned))
    raise ResourceGuardError("RESOURCE_JOB_QUERY_FAILED: process list exceeds the safety bound")


def _process_working_set_bytes(process_id: int) -> int:
    if os.name != "nt":
        if psutil is None:
            raise ResourceGuardError("RESOURCE_TELEMETRY_MISSING: psutil is required on Linux and macOS")
        try:
            return int(psutil.Process(process_id).memory_info().rss)
        except psutil.Error:
            return 0
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, process_id)
    if not handle:
        return 0
    try:
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.WorkingSetSize)
    finally:
        kernel32.CloseHandle(handle)


def _trim_process_working_set(process_id: int) -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
    psapi.EmptyWorkingSet.restype = ctypes.c_int
    handle = kernel32.OpenProcess(0x0100 | 0x0400, False, process_id)
    if not handle:
        return False
    try:
        return bool(psapi.EmptyWorkingSet(handle))
    finally:
        kernel32.CloseHandle(handle)


def job_working_set_bytes(handle: int | None) -> int:
    return sum(_process_working_set_bytes(process_id) for process_id in _job_process_ids(handle))


def _close_job(handle: int | None) -> None:
    if handle and os.name == "nt":
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(ctypes.c_void_p(handle))


def memory_snapshot() -> dict[str, int | float]:
    if os.name != "nt":
        if psutil is None:
            raise ResourceGuardError("RESOURCE_TELEMETRY_MISSING: psutil is required on Linux and macOS")
        value = psutil.virtual_memory()
        return {
            "total_physical_bytes": int(value.total),
            "available_physical_bytes": int(value.available),
            "memory_load_percent": int(round(value.percent)),
            "available_physical_gib": round(value.available / GIB, 2),
        }
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ResourceGuardError("could not read Windows memory status")
    return {
        "total_physical_bytes": int(status.ullTotalPhys),
        "available_physical_bytes": int(status.ullAvailPhys),
        "memory_load_percent": int(status.dwMemoryLoad),
        "available_physical_gib": round(status.ullAvailPhys / GIB, 2),
    }


def require_start_headroom(minimum_free_bytes: int = START_MIN_FREE_BYTES) -> dict[str, int | float]:
    snapshot = memory_snapshot()
    available = int(snapshot["available_physical_bytes"])
    if available < minimum_free_bytes:
        raise ResourceGuardError(
            f"RESOURCE_HEADROOM_INSUFFICIENT: available RAM is {available / GIB:.2f} GiB; "
            f"at least {minimum_free_bytes / GIB:.2f} GiB is required before a heavy task starts"
        )
    return snapshot


def current_process_working_set_bytes() -> int:
    if os.name != "nt":
        if psutil is None:
            raise ResourceGuardError("RESOURCE_TELEMETRY_MISSING: psutil is required on Linux and macOS")
        return int(psutil.Process().memory_info().rss)
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    handle = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        raise ResourceGuardError("could not read current process memory")
    return int(counters.WorkingSetSize)


def current_process_in_job() -> bool:
    if os.name != "nt":
        return os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    kernel32.IsProcessInJob.restype = ctypes.c_int
    result = ctypes.c_int()
    if not kernel32.IsProcessInJob(kernel32.GetCurrentProcess(), None, ctypes.byref(result)):
        raise ResourceGuardError(f"RESOURCE_JOB_QUERY_FAILED: Windows error {ctypes.get_last_error()}")
    return bool(result.value)


def require_orchestrator_budget(maximum_bytes: int = ORCHESTRATOR_RESERVE_BYTES) -> int:
    used = current_process_working_set_bytes()
    if used and used > maximum_bytes:
        raise ResourceGuardError(
            f"RESOURCE_ORCHESTRATOR_LIMIT: current process uses {used / MIB:.1f} MiB; "
            f"the incremental orchestrator limit is {maximum_bytes / MIB:.1f} MiB"
        )
    return used


def _terminate_owned_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            text=True, capture_output=True, timeout=20, check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def run_managed(
    command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
    timeout: float, start_min_free_bytes: int = START_MIN_FREE_BYTES,
    run_min_free_bytes: int = RUN_MIN_FREE_BYTES,
    maximum_job_bytes: int = WORKER_JOB_LIMIT_BYTES,
    maximum_orchestrator_bytes: int = ORCHESTRATOR_RESERVE_BYTES,
    trim_trigger_bytes: int | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        bounded_timeout = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ResourceGuardError("RESOURCE_TASK_TIMEOUT_INVALID: timeout must be finite and positive") from exc
    if not math.isfinite(bounded_timeout) or bounded_timeout <= 0:
        raise ResourceGuardError("RESOURCE_TASK_TIMEOUT_INVALID: timeout must be finite and positive")
    nested_managed_worker = (
        os.environ.get("RESEARCH_GUARD_MANAGED_WORKER") == "1"
        and current_process_in_job()
    )
    # The outer managed job has already passed the heavy-task admission check
    # and continues to monitor the complete descendant tree.  A nested worker
    # therefore reuses the registered run low-water mark instead of pretending
    # to start an independent heavy task.  The first admission threshold and
    # aggregate owned-task cap remain unchanged.
    admission_min_free_bytes = start_min_free_bytes
    if nested_managed_worker and start_min_free_bytes == START_MIN_FREE_BYTES:
        admission_min_free_bytes = run_min_free_bytes
    require_start_headroom(admission_min_free_bytes)
    if maximum_job_bytes + maximum_orchestrator_bytes > OWNED_TASK_BUDGET_BYTES:
        raise ResourceGuardError("RESOURCE_POLICY_INVALID: selected profile exceeds the owned-task budget")
    if not nested_managed_worker:
        require_orchestrator_budget(maximum_orchestrator_bytes)
    bounded_env = dict(os.environ) if env is None else dict(env)
    for variable in (
        "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
    ):
        bounded_env[variable] = "1"
    bounded_env["RESEARCH_GUARD_MANAGED_WORKER"] = "1"
    started = time.monotonic()
    with tempfile.TemporaryFile("w+b") as stdout_log, tempfile.TemporaryFile("w+b") as stderr_log:
        process = subprocess.Popen(
            list(command), cwd=cwd, env=bounded_env,
            stdout=stdout_log, stderr=stderr_log,
            start_new_session=os.name != "nt",
        )
        job_handle: int | None = None
        peak_worker_bytes = 0
        peak_orchestrator_bytes = 0
        peak_owned_bytes = 0
        working_set_trim_count = 0
        working_set_trim_failures = 0
        try:
            try:
                job_handle = _assign_memory_job(process, maximum_job_bytes)
            except ResourceGuardError:
                _terminate_owned_tree(process)
                raise
            while process.poll() is None:
                if time.monotonic() - started > bounded_timeout:
                    _terminate_owned_tree(process)
                    raise ResourceGuardError(f"RESOURCE_TASK_TIMEOUT: owned process tree exceeded {bounded_timeout:.0f} seconds")
                snapshot = memory_snapshot()
                if int(snapshot["available_physical_bytes"]) < run_min_free_bytes:
                    _terminate_owned_tree(process)
                    raise ResourceGuardError(
                        f"RESOURCE_LOW_WATER_ABORT: available RAM fell below {run_min_free_bytes / GIB:.2f} GiB; "
                        "only the task-owned process tree was terminated"
                    )
                process_ids = _job_process_ids(job_handle)
                worker_bytes = sum(_process_working_set_bytes(process_id) for process_id in process_ids)
                orchestrator_bytes = current_process_working_set_bytes()
                owned_bytes = worker_bytes + orchestrator_bytes
                peak_worker_bytes = max(peak_worker_bytes, worker_bytes)
                peak_orchestrator_bytes = max(peak_orchestrator_bytes, orchestrator_bytes)
                peak_owned_bytes = max(peak_owned_bytes, owned_bytes)
                if (
                    worker_bytes > maximum_job_bytes
                    or (not nested_managed_worker and orchestrator_bytes > maximum_orchestrator_bytes)
                    or owned_bytes > OWNED_TASK_BUDGET_BYTES
                ):
                    _terminate_owned_tree(process)
                    raise ResourceGuardError(
                        "RESOURCE_WORKING_SET_ABORT: task-owned physical working set exceeded its profile; "
                        f"worker={worker_bytes / MIB:.1f} MiB, orchestrator={orchestrator_bytes / MIB:.1f} MiB, "
                        f"total={owned_bytes / MIB:.1f} MiB"
                    )
                if trim_trigger_bytes is not None and worker_bytes >= trim_trigger_bytes:
                    for process_id in process_ids:
                        if _trim_process_working_set(process_id):
                            working_set_trim_count += 1
                        else:
                            working_set_trim_failures += 1
                time.sleep(SAMPLING_INTERVAL_SECONDS)
            process.wait(timeout=30)

            def tail(handle: Any, limit: int = 200_000) -> str:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - limit), os.SEEK_SET)
                return handle.read(limit).decode("utf-8", errors="replace")

            result = subprocess.CompletedProcess(
                list(command), process.returncode, tail(stdout_log), tail(stderr_log)
            )
            result.resource_usage = {  # type: ignore[attr-defined]
                "memory_metric": "aggregate_working_set",
                "peak_worker_bytes": peak_worker_bytes,
                "peak_orchestrator_bytes": peak_orchestrator_bytes,
                "peak_owned_bytes": peak_owned_bytes,
                "worker_limit_bytes": maximum_job_bytes,
                "orchestrator_limit_bytes": maximum_orchestrator_bytes,
                "owned_limit_bytes": OWNED_TASK_BUDGET_BYTES,
                "admission_min_free_bytes": admission_min_free_bytes,
                "working_set_trim_trigger_bytes": trim_trigger_bytes,
                "working_set_trim_count": working_set_trim_count,
                "working_set_trim_failures": working_set_trim_failures,
                "nested_managed_worker": nested_managed_worker,
            }
            return result
        finally:
            if process.poll() is None:
                _terminate_owned_tree(process)
            _close_job(job_handle)


def run_managed_light(
    command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
    timeout: float = 120, start_min_free_bytes: int = START_MIN_FREE_BYTES,
    run_min_free_bytes: int = RUN_MIN_FREE_BYTES,
) -> subprocess.CompletedProcess[str]:
    """Run a bounded low-memory validation without weakening heavy-task limits."""
    return run_managed(
        command, cwd=cwd, env=env, timeout=timeout,
        start_min_free_bytes=start_min_free_bytes,
        run_min_free_bytes=run_min_free_bytes,
        maximum_job_bytes=WORKER_JOB_LIMIT_BYTES,
    )


def run_managed_install(
    command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run an installer or isolated-package check without exceeding 512 MiB total."""
    return run_managed(
        command, cwd=cwd, env=env, timeout=timeout,
        maximum_job_bytes=INSTALL_WORKER_LIMIT_BYTES,
        maximum_orchestrator_bytes=INSTALL_ORCHESTRATOR_RESERVE_BYTES,
    )


def run_managed_lean(
    command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
    timeout: float = 180,
) -> subprocess.CompletedProcess[str]:
    return run_managed(
        command, cwd=cwd, env=env, timeout=timeout,
        maximum_job_bytes=LEAN_WORKER_LIMIT_BYTES,
        maximum_orchestrator_bytes=LEAN_ORCHESTRATOR_RESERVE_BYTES,
        trim_trigger_bytes=LEAN_TRIM_TRIGGER_BYTES,
    )
