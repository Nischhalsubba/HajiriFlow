from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hajiriflow.api.dependencies import (
    RequestIdentity,
    get_db,
    require_csrf,
    require_organization_permission,
)
from hajiriflow.device_platform.privacy import BiometricPrivacyService

router = APIRouter(prefix="/api/v1/organizations", tags=["biometric-privacy"])


class ConsentDecisionCreate(BaseModel):
    decision: Literal["granted", "declined", "revoked"]
    policy_version: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=240)


class ConsentDecisionView(BaseModel):
    id: UUID
    employee_id: UUID
    decision: str
    policy_version: str
    purpose: str
    occurred_at: datetime


class DeletionRequestCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class DeletionCompletionCreate(BaseModel):
    external_receipt_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class DeletionFailureCreate(BaseModel):
    failure_code: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )


class DeletionRequestView(BaseModel):
    id: UUID
    employee_id: UUID
    device_user_id: UUID
    status: str
    requested_at: datetime
    completed_at: datetime | None
    external_receipt_hash: str | None
    failure_code: str | None


def consent_view(item) -> ConsentDecisionView:
    return ConsentDecisionView(
        id=item.id,
        employee_id=item.employee_id,
        decision=item.decision,
        policy_version=item.policy_version,
        purpose=item.purpose,
        occurred_at=item.occurred_at,
    )


def deletion_view(item) -> DeletionRequestView:
    return DeletionRequestView(
        id=item.id,
        employee_id=item.employee_id,
        device_user_id=item.device_user_id,
        status=item.status,
        requested_at=item.requested_at,
        completed_at=item.completed_at,
        external_receipt_hash=item.external_receipt_hash,
        failure_code=item.failure_code,
    )


def service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="record already exists")
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{organization_id}/employees/{employee_id}/biometric-consent",
    response_model=ConsentDecisionView,
    status_code=status.HTTP_201_CREATED,
)
def record_biometric_consent(
    organization_id: UUID,
    employee_id: UUID,
    payload: ConsentDecisionCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.consent.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ConsentDecisionView:
    try:
        item = BiometricPrivacyService(session).record_consent(
            organization_id=organization_id,
            employee_id=employee_id,
            decision=payload.decision,
            policy_version=payload.policy_version,
            purpose=payload.purpose,
            actor_user_id=identity.principal.user.id,
        )
        return consent_view(item)
    except (ValueError, LookupError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get(
    "/{organization_id}/employees/{employee_id}/biometric-consent",
    response_model=ConsentDecisionView | None,
)
def latest_biometric_consent(
    organization_id: UUID,
    employee_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.consent.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> ConsentDecisionView | None:
    try:
        item = BiometricPrivacyService(session).latest_consent(
            organization_id=organization_id,
            employee_id=employee_id,
        )
        return consent_view(item) if item is not None else None
    except LookupError as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/device-users/{device_user_id}/biometric-deletions",
    response_model=DeletionRequestView,
    status_code=status.HTTP_201_CREATED,
)
def request_biometric_deletion(
    organization_id: UUID,
    device_user_id: UUID,
    payload: DeletionRequestCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.deletion.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeletionRequestView:
    try:
        item = BiometricPrivacyService(session).request_deletion(
            organization_id=organization_id,
            device_user_id=device_user_id,
            reason=payload.reason,
            actor_user_id=identity.principal.user.id,
        )
        return deletion_view(item)
    except (ValueError, LookupError, IntegrityError) as exc:
        raise service_error(exc) from exc


@router.get(
    "/{organization_id}/biometric-deletions/pending",
    response_model=list[DeletionRequestView],
)
def pending_biometric_deletions(
    organization_id: UUID,
    _: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.consent.read")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[DeletionRequestView]:
    return [
        deletion_view(item)
        for item in BiometricPrivacyService(session).pending_deletions(
            organization_id=organization_id
        )
    ]


@router.post(
    "/{organization_id}/biometric-deletions/{request_id}/complete",
    response_model=DeletionRequestView,
)
def complete_biometric_deletion(
    organization_id: UUID,
    request_id: UUID,
    payload: DeletionCompletionCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.deletion.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeletionRequestView:
    try:
        item = BiometricPrivacyService(session).complete_deletion(
            organization_id=organization_id,
            request_id=request_id,
            external_receipt_hash=payload.external_receipt_hash,
            actor_user_id=identity.principal.user.id,
        )
        return deletion_view(item)
    except (ValueError, LookupError) as exc:
        raise service_error(exc) from exc


@router.post(
    "/{organization_id}/biometric-deletions/{request_id}/fail",
    response_model=DeletionRequestView,
)
def fail_biometric_deletion(
    organization_id: UUID,
    request_id: UUID,
    payload: DeletionFailureCreate,
    _: Annotated[None, Depends(require_csrf)],
    identity: Annotated[
        RequestIdentity,
        Depends(require_organization_permission("biometric.deletion.manage")),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> DeletionRequestView:
    try:
        item = BiometricPrivacyService(session).fail_deletion(
            organization_id=organization_id,
            request_id=request_id,
            failure_code=payload.failure_code,
            actor_user_id=identity.principal.user.id,
        )
        return deletion_view(item)
    except (ValueError, LookupError) as exc:
        raise service_error(exc) from exc
