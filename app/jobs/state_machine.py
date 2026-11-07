from typing import Set

class JobStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

TERMINAL_STATUSES: Set[str] = {
    JobStatus.SUCCESS,
    JobStatus.PARTIAL,
    JobStatus.FAILED,
}

class JobStage:
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    OCR = "OCR"
    SCHEMA_ANALYSIS = "SCHEMA_ANALYSIS"
    EXTRACTING = "EXTRACTING"
    CALCULATING = "CALCULATING"
    VERIFYING = "VERIFYING"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"

def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES

def validate_transition(current_status: str, new_status: str) -> bool:
    if is_terminal(current_status):
        # Terminal statuses never change
        return False
    if current_status == JobStatus.PENDING:
        return new_status in {JobStatus.RUNNING, JobStatus.FAILED}
    if current_status == JobStatus.RUNNING:
        return new_status in {JobStatus.SUCCESS, JobStatus.PARTIAL, JobStatus.FAILED, JobStatus.PENDING}
    return False

