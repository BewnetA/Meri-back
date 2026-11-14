from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_session_context
from app.models.job import AccommodationRequest, Job, JobAlert
from app.schemas.job import (
    AccommodationRequestCreate,
    AccommodationRequestResponse,
    JobAlertCreate,
    JobAlertResponse,
    JobCreate,
    JobResponse,
)

router = APIRouter()


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    skill: str | None = Query(None, description="Filter by skill e.g. Python"),
    location: str | None = Query(None, description="Filter by location e.g. Addis Ababa"),
    keyword: str | None = Query(None, description="Search term in title or description"),
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Job).where(Job.is_active == True)
    platform_id = session.get("platform_id")
    if platform_id:
        stmt = stmt.where(Job.platform_id == platform_id)

    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if keyword:
        stmt = stmt.where(
            (Job.title.ilike(f"%{keyword}%")) | (Job.description.ilike(f"%{keyword}%"))
        )

    res = await db.execute(stmt)
    jobs = res.scalars().all()

    if skill:
        skill_lower = skill.lower()
        jobs = [j for j in jobs if any(skill_lower in s.lower() for s in (j.skills or []))]

    return jobs


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_listing(
    payload: JobCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    platform_id = session.get("platform_id")
    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Platform identification required"
        )

    job = Job(
        platform_id=platform_id,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        description=payload.description,
        requirements=payload.requirements,
        skills=payload.skills,
        application_instructions=payload.application_instructions,
        job_url=payload.job_url,
        is_active=True,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{id}", response_model=JobResponse)
async def get_job_detail(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Job).where(Job.id == id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/alerts", response_model=JobAlertResponse)
async def create_job_alert(
    payload: JobAlertCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = session.get("user_id")
    platform_id = session.get("platform_id")
    if not user_id or not platform_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Learner authentication required"
        )

    alert = JobAlert(
        user_id=user_id,
        platform_id=platform_id,
        keywords=payload.keywords,
        skills=payload.skills,
        location=payload.location,
        notify_telegram=payload.notify_telegram,
        notify_sms=payload.notify_sms,
        is_active=True,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/alerts", response_model=list[JobAlertResponse])
async def list_job_alerts(
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Learner authentication required"
        )

    stmt = select(JobAlert).where(JobAlert.user_id == user_id, JobAlert.is_active == True)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/accommodations", response_model=AccommodationRequestResponse)
async def submit_accommodation_request(
    payload: AccommodationRequestCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits confidential interview accommodation request.
    Enforces learner consent requirement as specified in Section 12.
    """
    if not payload.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Learner consent is required to process accommodation request.",
        )

    user_id = session.get("user_id")
    platform_id = session.get("platform_id")
    if not user_id or not platform_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Learner authentication required"
        )

    # Validate job
    job_stmt = select(Job).where(Job.id == payload.job_id)
    job_res = await db.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")

    request_obj = AccommodationRequest(
        job_id=job.id,
        user_id=user_id,
        platform_id=platform_id,
        details=payload.details,
        consent_given=True,
        status="submitted",
    )
    db.add(request_obj)
    await db.commit()
    await db.refresh(request_obj)
    return request_obj
