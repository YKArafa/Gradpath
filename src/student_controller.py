from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.shared.database import get_session
from src.shared.models import Advisor, Degree, Major, Student
from src.auth_controller import get_current_advisor

# Router initialization with router-level authentication dependency
router = APIRouter(
    prefix="/students",
    tags=["Students"],
    dependencies=[Depends(get_current_advisor)],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class StudentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of the student")
    email: EmailStr = Field(..., description="Student email address")
    institution: Optional[str] = Field(
        None,
        max_length=255,
        description="Academic institution (defaults to current advisor's institution if omitted)",
    )
    time_of_enrollment: Optional[datetime] = Field(
        None,
        description="Enrollment timestamp (defaults to current UTC time if omitted)",
    )
    degree_id: int = Field(..., description="ID of the degree program")
    major_id: Optional[int] = Field(
        None,
        description="Optional ID of the academic major",
    )
    advisor_id: Optional[int] = Field(
        None,
        description="Optional ID of the advisor (defaults to authenticated advisor if omitted)",
    )
    preferences: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Student preferences stored as JSON",
    )
    gpa: Optional[float] = Field(
        None,
        ge=0.0,
        le=4.0,
        description="Cumulative Grade Point Average (GPA)",
        alias="GPA",
    )

    model_config = ConfigDict(populate_by_name=True)


class StudentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated full name")
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    institution: Optional[str] = Field(None, max_length=255, description="Updated institution")
    time_of_enrollment: Optional[datetime] = Field(None, description="Updated enrollment timestamp")
    degree_id: Optional[int] = Field(None, description="Updated degree program ID")
    major_id: Optional[int] = Field(None, description="Updated major ID (or null to unassign)")
    advisor_id: Optional[int] = Field(None, description="Updated advisor ID")
    preferences: Optional[dict[str, Any]] = Field(None, description="Updated preferences JSON")
    gpa: Optional[float] = Field(None, ge=0.0, le=4.0, description="Updated GPA", alias="GPA")

    model_config = ConfigDict(populate_by_name=True)



class StudentResponse(BaseModel):
    id: int
    advisor_id: Optional[int] = None
    name: str
    email: str
    institution: str
    time_of_enrollment: datetime
    degree_id: int
    major_id: Optional[int] = None
    preferences: dict[str, Any]
    gpa: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class StudentDetailResponse(StudentResponse):
    degree_name: Optional[str] = None
    major_name: Optional[str] = None
    advisor_name: Optional[str] = None
    advisor_email: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: Build StudentDetailResponse
# ---------------------------------------------------------------------------

def build_student_detail(student: Student) -> StudentDetailResponse:
    """Helper to convert a Student ORM instance (with eager loaded relationships) to a rich response."""
    return StudentDetailResponse(
        id=student.id,
        advisor_id=student.advisor_id,
        name=student.name,
        email=student.email,
        institution=student.institution,
        time_of_enrollment=student.time_of_enrollment,
        degree_id=student.degree_id,
        major_id=student.major_id,
        preferences=student.preferences or {},
        gpa=float(student.gpa) if student.gpa is not None else None,
        created_at=student.created_at,
        degree_name=student.degree.name if student.degree else None,
        major_name=student.major.name if student.major else None,
        advisor_name=student.advisor.name if student.advisor else None,
        advisor_email=student.advisor.email if student.advisor else None,
    )


# ---------------------------------------------------------------------------
# Method 1: Create Student (Auth Required)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=StudentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Student",
    description="Creates a new student record linked to a degree, optional major, and advisor. Requires authentication.",
)
@router.post(
    "/",
    response_model=StudentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_student(
    data: StudentCreateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> StudentDetailResponse:
    """Create a student record with validation of degree, major, and advisor foreign keys."""
    # 1. Resolve advisor_id: explicit in payload or default to authenticated advisor
    resolved_advisor_id = data.advisor_id if data.advisor_id is not None else current_advisor.id

    # 2. Resolve institution: explicit or default to authenticated advisor's institution
    resolved_institution = data.institution.strip() if data.institution else current_advisor.institution

    # 3. Resolve enrollment time: explicit or now
    enrollment_time = data.time_of_enrollment or datetime.now(timezone.utc)

    # 4. Verify degree exists
    degree_stmt = select(Degree).where(Degree.id == data.degree_id)
    degree_res = await session.execute(degree_stmt)
    degree = degree_res.scalar_one_or_none()
    if not degree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Degree with ID {data.degree_id} not found.",
        )

    # 5. Verify major if provided
    major = None
    if data.major_id is not None:
        major_stmt = select(Major).where(Major.id == data.major_id)
        major_res = await session.execute(major_stmt)
        major = major_res.scalar_one_or_none()
        if not major:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Major with ID {data.major_id} not found.",
            )
        if major.degree_id != data.degree_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Major '{major.name}' (ID {data.major_id}) does not belong to Degree ID {data.degree_id}.",
            )

    # 6. Verify advisor if different from current_advisor
    if resolved_advisor_id != current_advisor.id:
        adv_stmt = select(Advisor).where(Advisor.id == resolved_advisor_id)
        adv_res = await session.execute(adv_stmt)
        advisor = adv_res.scalar_one_or_none()
        if not advisor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advisor with ID {resolved_advisor_id} not found.",
            )

    # 7. Instantiate and persist Student
    new_student = Student(
        advisor_id=resolved_advisor_id,
        name=data.name.strip(),
        email=data.email.strip().lower(),
        institution=resolved_institution,
        time_of_enrollment=enrollment_time,
        degree_id=data.degree_id,
        major_id=data.major_id,
        preferences=data.preferences or {},
        gpa=data.gpa,
    )
    session.add(new_student)
    await session.commit()
    await session.refresh(new_student)

    # Eager load relationships for the returned detail response
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.id == new_student.id)
    )
    res = await session.execute(stmt)
    loaded_student = res.scalar_one()

    return build_student_detail(loaded_student)


# ---------------------------------------------------------------------------
# Method 2: Getter - Get Advisees for Current Authenticated Advisor
# ---------------------------------------------------------------------------

@router.get(
    "/my/students",
    response_model=list[StudentDetailResponse],
    summary="Get advisees for the logged-in Advisor",
    description="Returns all students assigned to the currently authenticated advisor. Requires authentication.",
)
async def get_my_students(
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[StudentDetailResponse]:
    """Retrieve all students assigned to the current authenticated advisor."""
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.advisor_id == current_advisor.id)
        .order_by(Student.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    students = result.scalars().all()
    return [build_student_detail(s) for s in students]


# ---------------------------------------------------------------------------
# Method 3: Getter - Get Student by ID (Auth Required)
# ---------------------------------------------------------------------------

@router.get(
    "/{student_id}",
    response_model=StudentDetailResponse,
    summary="Get Student by ID",
    description="Retrieves a single student by their unique ID, including degree, major, and advisor details. Requires authentication.",
)
async def get_student_by_id(
    student_id: int,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> StudentDetailResponse:
    """Retrieve a student record by ID. Requires authentication."""
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.id == student_id)
    )
    result = await session.execute(stmt)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )

    return build_student_detail(student)


# ---------------------------------------------------------------------------
# Method 4: Getter - Get Student by Email (Auth Required)
# ---------------------------------------------------------------------------

@router.get(
    "/by-email/{email:path}",
    response_model=StudentDetailResponse,
    summary="Get Student by Email",
    description="Retrieves a single student by their email address. Requires authentication.",
)
async def get_student_by_email(
    email: str,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> StudentDetailResponse:
    """Retrieve a student record by email. Requires authentication."""
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.email == email.strip().lower())
    )
    result = await session.execute(stmt)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with email '{email}' not found.",
        )

    return build_student_detail(student)


# ---------------------------------------------------------------------------
# Method 5: Getter - Get Students by Advisor ID (Auth Required)
# ---------------------------------------------------------------------------

@router.get(
    "/advisor/{advisor_id}",
    response_model=list[StudentDetailResponse],
    summary="Get Students by Advisor ID",
    description="Retrieves all students assigned to a specific advisor ID. Requires authentication.",
)
async def get_students_by_advisor(
    advisor_id: int,
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[StudentDetailResponse]:
    """Retrieve all students assigned to a given advisor. Requires authentication."""
    # Verify advisor exists
    adv_stmt = select(Advisor).where(Advisor.id == advisor_id)
    adv_res = await session.execute(adv_stmt)
    if not adv_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisor with ID {advisor_id} not found.",
        )

    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.advisor_id == advisor_id)
        .order_by(Student.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    students = result.scalars().all()
    return [build_student_detail(s) for s in students]


# ---------------------------------------------------------------------------
# Method 6: Getter - List & Filter Students (Auth Required)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[StudentDetailResponse],
    summary="List and filter Students",
    description="Retrieves a paginated list of students with optional filtering by advisor, degree, major, or search term. Requires authentication.",
)
@router.get(
    "/",
    response_model=list[StudentDetailResponse],
    include_in_schema=False,
)
async def get_students(
    advisor_id: Optional[int] = Query(None, description="Filter by advisor ID"),
    degree_id: Optional[int] = Query(None, description="Filter by degree ID"),
    major_id: Optional[int] = Query(None, description="Filter by major ID"),
    search: Optional[str] = Query(None, description="Search term for name or email"),
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[StudentDetailResponse]:
    """Retrieve a filtered and paginated list of students. Requires authentication."""
    stmt = select(Student).options(
        selectinload(Student.degree),
        selectinload(Student.major),
        selectinload(Student.advisor),
    )

    if advisor_id is not None:
        stmt = stmt.where(Student.advisor_id == advisor_id)
    if degree_id is not None:
        stmt = stmt.where(Student.degree_id == degree_id)
    if major_id is not None:
        stmt = stmt.where(Student.major_id == major_id)
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Student.name.ilike(search_pattern),
                Student.email.ilike(search_pattern),
            )
        )

    stmt = stmt.order_by(Student.id.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    students = result.scalars().all()
    return [build_student_detail(s) for s in students]


# ---------------------------------------------------------------------------
# Method 7: Edit / Update Student (Auth Required)
# ---------------------------------------------------------------------------

@router.put(
    "/{student_id}",
    response_model=StudentDetailResponse,
    summary="Update/Edit Student",
    description="Updates an existing student record with partial or full attributes. Requires authentication.",
)
@router.patch(
    "/{student_id}",
    response_model=StudentDetailResponse,
    summary="Update/Edit Student (Partial)",
    description="Partially updates an existing student record. Requires authentication.",
)
async def update_student(
    student_id: int,
    data: StudentUpdateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> StudentDetailResponse:
    """Edit student details with foreign key and constraint validation."""
    # 1. Fetch student
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.id == student_id)
    )
    res = await session.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found.",
        )

    # 2. Extract explicitly provided fields
    update_dict = data.model_dump(exclude_unset=True, by_alias=False)

    # 3. Determine degree ID to validate major against
    target_degree_id = update_dict.get("degree_id", student.degree_id)

    # If degree_id is updated, verify it exists
    if "degree_id" in update_dict and update_dict["degree_id"] != student.degree_id:
        deg_res = await session.execute(select(Degree).where(Degree.id == target_degree_id))
        if not deg_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Degree with ID {target_degree_id} not found.",
            )
        student.degree_id = target_degree_id

    # If major_id is updated
    if "major_id" in update_dict:
        new_major_id = update_dict["major_id"]
        if new_major_id is not None:
            maj_res = await session.execute(select(Major).where(Major.id == new_major_id))
            major = maj_res.scalar_one_or_none()
            if not major:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Major with ID {new_major_id} not found.",
                )
            if major.degree_id != target_degree_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Major '{major.name}' (ID {new_major_id}) does not belong to Degree ID {target_degree_id}.",
                )
        student.major_id = new_major_id

    # If advisor_id is updated
    if "advisor_id" in update_dict:
        new_advisor_id = update_dict["advisor_id"]
        if new_advisor_id is not None and new_advisor_id != student.advisor_id:
            adv_res = await session.execute(select(Advisor).where(Advisor.id == new_advisor_id))
            if not adv_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Advisor with ID {new_advisor_id} not found.",
                )
        student.advisor_id = new_advisor_id

    # Update scalar and JSON fields
    if "name" in update_dict and update_dict["name"] is not None:
        student.name = update_dict["name"].strip()
    if "email" in update_dict and update_dict["email"] is not None:
        student.email = update_dict["email"].strip().lower()
    if "institution" in update_dict and update_dict["institution"] is not None:
        student.institution = update_dict["institution"].strip()
    if "time_of_enrollment" in update_dict and update_dict["time_of_enrollment"] is not None:
        student.time_of_enrollment = update_dict["time_of_enrollment"]
    if "preferences" in update_dict and update_dict["preferences"] is not None:
        student.preferences = update_dict["preferences"]
    if "gpa" in update_dict:
        student.gpa = update_dict["gpa"]

    # 4. Commit and re-query eager relationships
    await session.commit()
    await session.refresh(student)

    fresh_stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.advisor),
        )
        .where(Student.id == student.id)
    )
    fresh_res = await session.execute(fresh_stmt)
    refreshed_student = fresh_res.scalar_one()

    return build_student_detail(refreshed_student)

