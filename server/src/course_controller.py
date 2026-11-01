from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.shared.models import Advisor, Course
from src.auth_controller import get_current_advisor

# Router initialization with router-level authentication dependency
router = APIRouter(
    prefix="/courses",
    tags=["Courses"],
    dependencies=[Depends(get_current_advisor)],
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class CourseCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Unique course code (e.g. CS101)")
    title: str = Field(..., min_length=1, max_length=255, description="Course title")
    description: Optional[str] = Field(None, description="Course description")
    credit_hours: float = Field(
        ...,
        gt=0,
        description="Credit hours or ECTS credits",
        alias="ects",
    )
    difficulty_level: Optional[Literal["low", "medium", "hard"]] = Field(
        default="medium",
        description="Course difficulty level: 'low', 'medium', or 'hard'",
        alias="difficulty",
    )
    prerequisites: Optional[list[Any]] = Field(
        default_factory=list,
        description="List of prerequisites (e.g. course codes or course IDs) stored as JSON",
    )

    model_config = ConfigDict(populate_by_name=True)


class CourseUpdateRequest(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="Updated course code")
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated course title")
    description: Optional[str] = Field(None, description="Updated course description")
    credit_hours: Optional[float] = Field(
        None,
        gt=0,
        description="Updated credit hours or ECTS credits",
        alias="ects",
    )
    difficulty_level: Optional[Literal["low", "medium", "hard"]] = Field(
        None,
        description="Updated course difficulty level: 'low', 'medium', or 'hard'",
        alias="difficulty",
    )
    prerequisites: Optional[list[Any]] = Field(
        None,
        description="Updated prerequisites list stored as JSON",
    )

    model_config = ConfigDict(populate_by_name=True)


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    description: Optional[str] = None
    credit_hours: float
    difficulty_level: str = "medium"
    difficulty: Optional[str] = None
    prerequisites: list[Any]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Helper: Build CourseResponse
# ---------------------------------------------------------------------------

def build_course_response(course: Course) -> CourseResponse:
    """Helper to convert Course ORM instance to Pydantic CourseResponse."""
    diff = course.difficulty_level or "medium"
    return CourseResponse(
        id=course.id,
        code=course.code,
        title=course.title,
        description=course.description,
        credit_hours=float(course.credit_hours),
        difficulty_level=diff,
        difficulty=diff,
        prerequisites=course.prerequisites or [],
    )


# ---------------------------------------------------------------------------
# Method 1: Add / Create Course
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new Course",
    description="Creates a new academic course. Requires advisor authentication.",
)
@router.post(
    "/",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_course(
    data: CourseCreateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> CourseResponse:
    """Add a new course with duplicate code check."""
    normalized_code = data.code.strip().upper()

    # 1. Check if course with this code already exists
    existing_stmt = select(Course).where(Course.code == normalized_code)
    existing_res = await session.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Course with code '{normalized_code}' already exists.",
        )

    # 2. Create course record
    diff = (data.difficulty_level or "medium").lower()
    new_course = Course(
        code=normalized_code,
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        credit_hours=data.credit_hours,
        difficulty_level=diff,
        prerequisites=data.prerequisites or [],
    )
    session.add(new_course)
    await session.commit()
    await session.refresh(new_course)

    return build_course_response(new_course)


# ---------------------------------------------------------------------------
# Method 2: Edit / Update Course (PUT & PATCH)
# ---------------------------------------------------------------------------

@router.put(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Update Course (Full)",
    description="Updates all or partial attributes of a course. Requires advisor authentication.",
)
@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Update Course (Partial)",
    description="Partially updates an existing course. Requires advisor authentication.",
)
async def update_course(
    course_id: int,
    data: CourseUpdateRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> CourseResponse:
    """Edit course details with code uniqueness check."""
    # 1. Fetch course by ID
    stmt = select(Course).where(Course.id == course_id)
    res = await session.execute(stmt)
    course = res.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID {course_id} not found.",
        )

    update_dict = data.model_dump(exclude_unset=True, by_alias=False)

    # 2. Check code uniqueness if code is updated
    if "code" in update_dict and update_dict["code"] is not None:
        new_code = update_dict["code"].strip().upper()
        if new_code != course.code:
            existing_stmt = select(Course).where(Course.code == new_code, Course.id != course_id)
            existing_res = await session.execute(existing_stmt)
            if existing_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another course with code '{new_code}' already exists.",
                )
            course.code = new_code

    # 3. Update remaining fields
    if "title" in update_dict and update_dict["title"] is not None:
        course.title = update_dict["title"].strip()
    if "description" in update_dict:
        course.description = update_dict["description"].strip() if update_dict["description"] else None
    if "credit_hours" in update_dict and update_dict["credit_hours"] is not None:
        course.credit_hours = update_dict["credit_hours"]
    if "difficulty_level" in update_dict and update_dict["difficulty_level"] is not None:
        course.difficulty_level = update_dict["difficulty_level"].lower()
    if "prerequisites" in update_dict and update_dict["prerequisites"] is not None:
        course.prerequisites = update_dict["prerequisites"]

    await session.commit()
    await session.refresh(course)

    return build_course_response(course)


# ---------------------------------------------------------------------------
# Method 3: Get Course by ID
# ---------------------------------------------------------------------------

@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    summary="Get Course by ID",
    description="Retrieves a course record by its unique database ID. Requires advisor authentication.",
)
async def get_course_by_id(
    course_id: int,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> CourseResponse:
    """Retrieve a single course by its integer ID."""
    stmt = select(Course).where(Course.id == course_id)
    result = await session.execute(stmt)
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID {course_id} not found.",
        )

    return build_course_response(course)


# ---------------------------------------------------------------------------
# Method 4: Get Course by Code
# ---------------------------------------------------------------------------

@router.get(
    "/by-code/{code}",
    response_model=CourseResponse,
    summary="Get Course by Code",
    description="Retrieves a course record by its unique code (e.g. CS101). Requires advisor authentication.",
)
async def get_course_by_code(
    code: str,
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> CourseResponse:
    """Retrieve a single course by its code (case-insensitive)."""
    normalized_code = code.strip().upper()
    stmt = select(Course).where(Course.code == normalized_code)
    result = await session.execute(stmt)
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with code '{code}' not found.",
        )

    return build_course_response(course)


# ---------------------------------------------------------------------------
# Method 5: List & Filter Courses
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[CourseResponse],
    summary="List and filter Courses",
    description="Retrieves a paginated list of courses with optional search and credit filters. Requires advisor authentication.",
)
@router.get(
    "/",
    response_model=list[CourseResponse],
    include_in_schema=False,
)
async def get_courses(
    search: Optional[str] = Query(None, description="Search term for course code or title"),
    difficulty: Optional[Literal["low", "medium", "hard"]] = Query(None, description="Filter by difficulty level ('low', 'medium', 'hard')"),
    min_credits: Optional[float] = Query(None, ge=0, description="Filter courses with minimum credit hours"),
    max_credits: Optional[float] = Query(None, ge=0, description="Filter courses with maximum credit hours"),
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_advisor: Advisor = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> list[CourseResponse]:
    """Retrieve a filtered and paginated list of courses."""
    stmt = select(Course)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Course.code.ilike(search_pattern),
                Course.title.ilike(search_pattern),
            )
        )

    if difficulty:
        stmt = stmt.where(Course.difficulty_level == difficulty.lower())

    if min_credits is not None:
        stmt = stmt.where(Course.credit_hours >= min_credits)

    if max_credits is not None:
        stmt = stmt.where(Course.credit_hours <= max_credits)

    stmt = stmt.order_by(Course.code.asc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    courses = result.scalars().all()

    return [build_course_response(c) for c in courses]
