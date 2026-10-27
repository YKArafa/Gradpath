from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from src.shared.database import get_session
from src.shared.models import Advisor, Student, Transcript
from src.auth_controller import get_current_advisor

# Router initialization with router-level authentication dependency
router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"],
    dependencies=[Depends(get_current_advisor)],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class SemesterEntry(BaseModel):
    semester: str = Field(..., min_length=1, max_length=100, description="Semester label (e.g. 'Fall 2024')")
    courses: dict[str, Any] = Field(
        default_factory=dict,
        description="Map of course ID or code to numeric grade (e.g. {'1': 3.7, '2': 4.0})",
    )

    model_config = ConfigDict(extra="allow")


class TranscriptCreateRequest(BaseModel):
    student_id: int = Field(..., description="ID of the student associated with this transcript")
    semesters: Optional[list[dict[str, Any]]] = Field(
        default_factory=list,
        description="List of semester records containing semester string and courses map",
        alias="records",
    )

    model_config = ConfigDict(populate_by_name=True)


class TranscriptUpdateRequest(BaseModel):
    student_id: Optional[int] = Field(None, description="Optional updated student ID")
    semesters: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Updated list of semester records",
        alias="records",
    )

    model_config = ConfigDict(populate_by_name=True)


class TranscriptResponse(BaseModel):
    id: int
    student_id: int
    semesters: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TranscriptDetailResponse(TranscriptResponse):
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    student_institution: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: Build TranscriptDetailResponse
# ---------------------------------------------------------------------------

def build_transcript_response(transcript: Transcript) -> TranscriptDetailResponse:
    """Helper to convert Transcript ORM instance (with student relationship) to rich response."""
    student_name = transcript.student.name if transcript.student else None
    student_email = transcript.student.email if transcript.student else None
    student_institution = transcript.student.institution if transcript.student else None

    return TranscriptDetailResponse(
        id=transcript.id,
        student_id=transcript.student_id,
        semesters=transcript.semesters or [],
        student_name=student_name,
        student_email=student_email,
        student_institution=student_institution,
    )


# ---------------------------------------------------------------------------
# Method 1: Add / Create Transcript
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=TranscriptDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new Transcript",
    description="Creates a new transcript record for a student. Requires advisor authentication.",
)
@router.post(
    "/",
    response_model=TranscriptDetailResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_transcript(
    data: TranscriptCreateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> TranscriptDetailResponse:
    """Add a new transcript linked to a student."""
    # 1. Verify student exists
    student_stmt = select(Student).where(Student.id == data.student_id)
    student_res = await session.execute(student_stmt)
    student = student_res.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {data.student_id} not found.",
        )

    # 2. Create transcript record
    new_transcript = Transcript(
        student_id=data.student_id,
        semesters=data.semesters or [],
    )
    session.add(new_transcript)
    await session.commit()
    await session.refresh(new_transcript)

    # 3. Reload with eager relationships
    stmt = (
        select(Transcript)
        .options(selectinload(Transcript.student))
        .where(Transcript.id == new_transcript.id)
    )
    res = await session.execute(stmt)
    loaded_transcript = res.scalar_one()

    return build_transcript_response(loaded_transcript)


# ---------------------------------------------------------------------------
# Method 2: Edit / Update Transcript (Full PUT & Partial PATCH)
# ---------------------------------------------------------------------------

@router.put(
    "/{transcript_id}",
    response_model=TranscriptDetailResponse,
    summary="Update Transcript (Full)",
    description="Updates all or partial attributes of a transcript. Requires advisor authentication.",
)
@router.patch(
    "/{transcript_id}",
    response_model=TranscriptDetailResponse,
    summary="Update Transcript (Partial)",
    description="Partially updates an existing transcript. Requires advisor authentication.",
)
async def update_transcript(
    transcript_id: int,
    data: TranscriptUpdateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> TranscriptDetailResponse:
    """Edit transcript details (e.g. semesters or student_id)."""
    # 1. Fetch transcript by ID
    stmt = (
        select(Transcript)
        .options(selectinload(Transcript.student))
        .where(Transcript.id == transcript_id)
    )
    res = await session.execute(stmt)
    transcript = res.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript with ID {transcript_id} not found.",
        )

    update_dict = data.model_dump(exclude_unset=True, by_alias=False)

    # 2. If student_id is updated, verify new student exists
    if "student_id" in update_dict and update_dict["student_id"] is not None:
        new_student_id = update_dict["student_id"]
        if new_student_id != transcript.student_id:
            s_stmt = select(Student).where(Student.id == new_student_id)
            s_res = await session.execute(s_stmt)
            if not s_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Student with ID {new_student_id} not found.",
                )
            transcript.student_id = new_student_id

    # 3. Update semesters if provided
    if "semesters" in update_dict and update_dict["semesters"] is not None:
        transcript.semesters = update_dict["semesters"]
        flag_modified(transcript, "semesters")

    await session.commit()

    # Re-query with updated student relationship
    res = await session.execute(stmt)
    refreshed_transcript = res.scalar_one()

    return build_transcript_response(refreshed_transcript)


# ---------------------------------------------------------------------------
# Method 3: Get Transcript by ID
# ---------------------------------------------------------------------------

@router.get(
    "/{transcript_id}",
    response_model=TranscriptDetailResponse,
    summary="Get Transcript by ID",
    description="Retrieves a single transcript by its ID. Requires advisor authentication.",
)
async def get_transcript_by_id(
    transcript_id: int,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> TranscriptDetailResponse:
    """Retrieve a single transcript by ID with student information."""
    stmt = (
        select(Transcript)
        .options(selectinload(Transcript.student))
        .where(Transcript.id == transcript_id)
    )
    res = await session.execute(stmt)
    transcript = res.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript with ID {transcript_id} not found.",
        )

    return build_transcript_response(transcript)


# ---------------------------------------------------------------------------
# Method 4: Get Transcripts by Student ID
# ---------------------------------------------------------------------------

@router.get(
    "/student/{student_id}",
    response_model=list[TranscriptDetailResponse],
    summary="Get Transcripts by Student ID",
    description="Retrieves all transcripts for a specific student. Requires advisor authentication.",
)
async def get_transcripts_by_student_id(
    student_id: int,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[TranscriptDetailResponse]:
    """Retrieve all transcripts associated with a given student ID."""
    # 1. Verify student exists
    student_stmt = select(Student).where(Student.id == student_id)
    student_res = await session.execute(student_stmt)
    if not student_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )

    # 2. Query transcripts
    stmt = (
        select(Transcript)
        .options(selectinload(Transcript.student))
        .where(Transcript.student_id == student_id)
        .order_by(Transcript.id.asc())
    )
    res = await session.execute(stmt)
    transcripts = res.scalars().all()

    return [build_transcript_response(t) for t in transcripts]


# ---------------------------------------------------------------------------
# Method 5: List Transcripts (with optional student_id filter & pagination)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[TranscriptDetailResponse],
    summary="List Transcripts",
    description="Retrieves a paginated list of transcripts with optional student ID filtering. Requires advisor authentication.",
)
@router.get(
    "/",
    response_model=list[TranscriptDetailResponse],
    include_in_schema=False,
)
async def list_transcripts(
    student_id: Optional[int] = Query(None, description="Optional filter by student ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max number of records to return"),
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[TranscriptDetailResponse]:
    """List transcripts with pagination and optional student filter."""
    stmt = select(Transcript).options(selectinload(Transcript.student))
    if student_id is not None:
        stmt = stmt.where(Transcript.student_id == student_id)
    stmt = stmt.order_by(Transcript.id.desc()).offset(skip).limit(limit)

    res = await session.execute(stmt)
    transcripts = res.scalars().all()

    return [build_transcript_response(t) for t in transcripts]


# ---------------------------------------------------------------------------
# Method 6: Append Semester Record to Transcript
# ---------------------------------------------------------------------------

@router.post(
    "/{transcript_id}/semesters",
    response_model=TranscriptDetailResponse,
    summary="Add Semester Record to Transcript",
    description="Appends a new semester record to the transcript's semester list. Requires advisor authentication.",
)
async def add_semester_record(
    transcript_id: int,
    semester_data: SemesterEntry,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> TranscriptDetailResponse:
    """Append a single semester entry to an existing transcript."""
    stmt = (
        select(Transcript)
        .options(selectinload(Transcript.student))
        .where(Transcript.id == transcript_id)
    )
    res = await session.execute(stmt)
    transcript = res.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript with ID {transcript_id} not found.",
        )

    current_semesters = list(transcript.semesters or [])
    current_semesters.append(semester_data.model_dump())
    transcript.semesters = current_semesters
    flag_modified(transcript, "semesters")

    await session.commit()

    res = await session.execute(stmt)
    return build_transcript_response(res.scalar_one())


# ---------------------------------------------------------------------------
# Method 7: Delete Transcript
# ---------------------------------------------------------------------------

@router.delete(
    "/{transcript_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Transcript",
    description="Deletes a transcript record by its unique database ID. Requires advisor authentication.",
)
async def delete_transcript(
    transcript_id: int,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Delete a transcript record by ID."""
    stmt = select(Transcript).where(Transcript.id == transcript_id)
    res = await session.execute(stmt)
    transcript = res.scalar_one_or_none()

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript with ID {transcript_id} not found.",
        )

    await session.delete(transcript)
    await session.commit()

    return {"message": f"Transcript with ID {transcript_id} successfully deleted."}
