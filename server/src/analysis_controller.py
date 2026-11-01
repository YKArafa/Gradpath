import re
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.shared.database import get_session
from src.shared.models import Advisor, Course, Degree, Major, Student, Transcript
from src.auth_controller import get_current_advisor

# Router initialization with router-level authentication dependency
router = APIRouter(
    prefix="/analysis",
    tags=["Academic Analysis"],
    dependencies=[Depends(get_current_advisor)],
)

# Standard credits per regular semester in academic planning (Bologna / ECTS standard)
STANDARD_SEMESTER_CREDITS: float = 30.0

# Standard fallback credits for undeclared major (80 credit hours)
UNDECLARED_MAJOR_CREDITS: float = 80.0

# ---------------------------------------------------------------------------
# Pydantic Schemas for Analysis Output
# ---------------------------------------------------------------------------

class CourseRiskItem(BaseModel):
    course_identifier: str
    code: Optional[str] = None
    title: Optional[str] = None
    credit_hours: float
    semester: Optional[str] = None
    grade: Optional[float] = None
    status: str

    model_config = ConfigDict(populate_by_name=True)


class GeneralRiskAnalysisResponse(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    institution: str
    enrollment_time: datetime
    current_date: datetime
    current_semester: str
    current_semester_index: int
    finish_semester: str
    has_begun_current_semester: bool
    last_transcript_semester: Optional[str] = None
    semesters_left: int
    remaining_semesters: list[str]
    credit_score_counter: float
    credits_per_semester_needed: float
    standard_credits_per_semester: float = STANDARD_SEMESTER_CREDITS
    has_major: bool
    risk_level: str
    degree_total_credits: float = Field(0.0, description="Sum of credit hours of all courses in the degree program")
    total_program_credits: float = Field(0.0, description="Total credits required (degree + major courses, or degree + 80 if undeclared)")
    passed_credits: float = Field(0.0, description="Total passed credit hours from student transcripts")
    breakdown: dict[str, Any]
    summary: str

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Semester Parsing & Calendar Helpers
# ---------------------------------------------------------------------------

def normalize_season(season_str: str) -> str:
    """
    Normalizes season string to 'Winter', 'Spring', or 'Summer'.
    'Fall', 'Autumn', 'Winter', 'W', 'F' represent the first regular semester.
    'Spring', 'S' represent the second regular semester.
    'Summer', 'Su' represent the summer session.
    """
    s = season_str.strip().lower()
    if s.startswith(("w", "f", "aut")):
        return "Winter"
    if s.startswith("sp") or s == "s":
        return "Spring"
    if s.startswith("su"):
        return "Summer"
    return season_str.capitalize()


def parse_semester(sem_input: str) -> tuple[str, int]:
    """
    Parse a semester string like 'Winter 2026', 'Fall 2024', 'Spring 2028', 'W26'.
    Returns (normalized_season, 4_digit_year).
    """
    clean = sem_input.strip()
    match = re.search(r'(?i)(winter|fall|spring|summer|autumn|w|f|sp|su)\s*(\d{2,4})', clean)
    if match:
        season_raw = match.group(1)
        year_raw = int(match.group(2))
        if year_raw < 100:
            year_raw += 2000
        return normalize_season(season_raw), year_raw

    # Fallback: split on whitespace
    parts = clean.split()
    if len(parts) >= 2:
        try:
            year = int(parts[1])
            if year < 100:
                year += 2000
            return normalize_season(parts[0]), year
        except ValueError:
            pass

    # If parsing fails, default to current year
    return "Winter", datetime.now(timezone.utc).year


def format_semester(season: str, year: int) -> str:
    """Format season and year into canonical display string, e.g. 'Winter 2026'."""
    return f"{season} {year}"


def get_next_regular_semester(season: str, year: int) -> tuple[str, int]:
    """
    Returns the next regular semester in sequence (skipping Summer).
    Sequence:
      Winter Y -> Spring Y+1
      Spring Y+1 -> Winter Y+1
      Summer Y -> Winter Y
    """
    norm = normalize_season(season)
    if norm == "Winter":
        return "Spring", year + 1
    elif norm == "Spring":
        return "Winter", year
    else:  # Summer
        return "Winter", year


def date_to_semester(dt: datetime) -> tuple[str, int]:
    """
    Convert a datetime to an academic semester (Winter, Spring, or Summer).
    Academic calendar standard:
      - Months 9..12: Winter semester of year Y (starts Sept/Oct)
      - Months 1..2: Continuation of Winter semester from year Y-1
      - Months 3..6: Spring semester of year Y (starts Feb/March)
      - Months 7..8: Summer semester of year Y
    """
    month = dt.month
    year = dt.year

    if month >= 9:
        return "Winter", year
    elif month in (1, 2):
        return "Winter", year - 1
    elif month in (3, 4, 5, 6):
        return "Spring", year
    else:
        return "Summer", year


def semester_compare_key(season: str, year: int) -> float:
    """
    Numeric key to sort / compare semesters chronologically.
    Winter Y: year + 0.1 (academic year start, e.g. 2026.1)
    Spring Y+1: year + 0.6 (spring, e.g. 2026.6)
    Summer Y: year + 0.8
    """
    norm = normalize_season(season)
    if norm == "Winter":
        return year + 0.1
    elif norm == "Spring":
        # Spring of calendar year Y belongs to academic year Y-1
        return (year - 1) + 0.6
    else:
        return (year - 1) + 0.8


def get_regular_semesters_between(start_sem: tuple[str, int], end_sem: tuple[str, int]) -> list[str]:
    """
    Returns list of regular semester strings from start_sem up to and including end_sem.
    Only the 2 regular semester types (Winter and Spring) are included.
    """
    result: list[str] = []
    curr_season, curr_year = start_sem

    # If start is Summer, advance to next regular semester
    if normalize_season(curr_season) == "Summer":
        curr_season, curr_year = get_next_regular_semester(curr_season, curr_year)

    end_key = semester_compare_key(end_sem[0], end_sem[1])

    while semester_compare_key(curr_season, curr_year) <= end_key:
        result.append(format_semester(curr_season, curr_year))
        curr_season, curr_year = get_next_regular_semester(curr_season, curr_year)

    return result


def is_failed_grade(grade: Any, threshold: float = 1.0) -> bool:
    """
    Determine if a grade represents a failed course.
    Under 4.0 GPA scales, 0.0 is F (Fail).
    Accepts numeric values (< threshold) and string tokens ('F', 'FAIL', '0').
    """
    if grade is None:
        return False
    if isinstance(grade, (int, float)):
        return float(grade) < threshold
    s = str(grade).strip().upper()
    if s in ("F", "FAIL", "FAILED", "U", "0", "0.0"):
        return True
    try:
        val = float(s)
        return val < threshold
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Method: general_risk_analysis
# ---------------------------------------------------------------------------

@router.get(
    "/general-risk-analysis/{student_id}",
    response_model=GeneralRiskAnalysisResponse,
    summary="General Risk Analysis on Student",
    description=(
        "Analyzes graduation risk based on remaining credits until graduation divided by remaining semesters. "
        "Checks transcript for failed courses (including summer), remaining degree/major courses (or 80 credits "
        "if undeclared), and determines remaining regular semesters."
    ),
)
@router.get(
    "/students/{student_id}/risk",
    response_model=GeneralRiskAnalysisResponse,
    include_in_schema=False,
)
async def general_risk_analysis(
    student_id: int,
    finish_semester: Optional[str] = Query(
        None,
        description="Target graduation semester (e.g. 'Spring 2028'). Defaults to 8 regular semesters from enrollment.",
    ),
    now: Optional[datetime] = Query(
        None,
        description="Optional reference date override for analysis (defaults to current UTC date).",
    ),
    failing_grade_threshold: float = Query(
        1.0,
        description="Grade threshold below which course is considered failed (default: 1.0, where 0.0 is F).",
    ),
    current_advisor: Optional[Advisor] = Depends(get_current_advisor),
    session: AsyncSession = Depends(get_session),
) -> GeneralRiskAnalysisResponse:
    """
    Analyze graduation risk for a student.
    
    1. Enrollment time vs now's date -> Determines which semester the student is in.
    2. Fetches student's transcript and all courses:
       - If a course is failed (including summer), its credit hours are added to credit counter.
       - Accurately tracks passed credit hours.
    3. Sums total credits of courses in the degree program and checks remaining degree courses.
    4. Checks major:
       - If student has a major: checks remaining courses in major and adds their credit hours.
       - If student does NOT have a major: adds 80 credits to counter.
    5. Determines remaining regular semesters (Winter and Spring):
       - Checks if student began current semester (is it present in transcript).
       - If began: remaining count starts at the NEXT regular semester.
       - If not began: remaining count starts at the current semester.
    6. Divides remaining credits counter by number of semesters left.
    """
    # Guard against direct Python function calls where FastAPI Query defaults are not resolved
    if not isinstance(failing_grade_threshold, (int, float)):
        failing_grade_threshold = 1.0
    else:
        failing_grade_threshold = float(failing_grade_threshold)

    if not isinstance(finish_semester, str):
        finish_semester = None
    if not isinstance(now, datetime):
        now = None

    # 1. Fetch student with eager-loaded degree, major, and transcripts
    stmt = (
        select(Student)
        .options(
            selectinload(Student.degree),
            selectinload(Student.major),
            selectinload(Student.transcripts),
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

    # 2. Build course catalog lookup map for quick credit resolution
    courses_res = await session.execute(select(Course))
    all_courses = courses_res.scalars().all()
    course_by_id: dict[int, Course] = {c.id: c for c in all_courses}
    course_by_code: dict[str, Course] = {c.code.strip().upper(): c for c in all_courses}
    course_by_title: dict[str, Course] = {c.title.strip().upper(): c for c in all_courses}

    def resolve_course_credits(course_key: Any, default_credits: float = 3.0) -> tuple[float, Optional[str], Optional[str]]:
        """Resolves credit hours, code, and title from ID, code string, title string, or dict."""
        if isinstance(course_key, dict):
            c_credits = float(course_key.get("credit_hours", course_key.get("credits", course_key.get("ects", default_credits))))
            c_code = course_key.get("code")
            c_title = course_key.get("title") or course_key.get("name")
            return c_credits, c_code, c_title

        # Try ID match
        try:
            int_id = int(course_key)
            if int_id in course_by_id:
                c = course_by_id[int_id]
                return float(c.credit_hours), c.code, c.title
        except (ValueError, TypeError):
            pass

        # Try Code match
        code_str = str(course_key).strip().upper()
        if code_str in course_by_code:
            c = course_by_code[code_str]
            return float(c.credit_hours), c.code, c.title

        # Try Title match
        if code_str in course_by_title:
            c = course_by_title[code_str]
            return float(c.credit_hours), c.code, c.title

        return default_credits, code_str, code_str

    # 3. Compare enrollment time to now's date -> see which semester student is in
    current_dt = now or datetime.now(timezone.utc)
    enrollment_dt = student.time_of_enrollment

    enrollment_season, enrollment_year = date_to_semester(enrollment_dt)
    current_season, current_year = date_to_semester(current_dt)
    current_semester_str = format_semester(current_season, current_year)

    # Calculate 1-based semester index from enrollment
    all_semesters_since_enrollment = get_regular_semesters_between(
        (enrollment_season, enrollment_year),
        (current_season, current_year)
    )
    current_semester_index = max(1, len(all_semesters_since_enrollment))

    # 4. Resolve Target Graduation / Finish Semester
    target_finish_tuple: tuple[str, int]
    if finish_semester:
        target_finish_tuple = parse_semester(finish_semester)
    elif student.preferences and "finish_semester" in student.preferences:
        target_finish_tuple = parse_semester(str(student.preferences["finish_semester"]))
    elif student.preferences and "graduation_semester" in student.preferences:
        target_finish_tuple = parse_semester(str(student.preferences["graduation_semester"]))
    else:
        # Default: 8 regular semesters from enrollment (standard 4-year degree)
        total_semesters_target = int(student.preferences.get("total_semesters", 8)) if student.preferences else 8
        cur_s, cur_y = enrollment_season, enrollment_year
        for _ in range(total_semesters_target - 1):
            cur_s, cur_y = get_next_regular_semester(cur_s, cur_y)
        target_finish_tuple = (cur_s, cur_y)

    finish_semester_str = format_semester(target_finish_tuple[0], target_finish_tuple[1])

    # 5. Fetch Transcript and inspect all courses
    # Initialize credit score counter
    credit_score_counter: float = 0.0

    transcript_records: list[dict[str, Any]] = []
    if student.transcripts:
        for t in student.transcripts:
            if t.semesters:
                transcript_records.extend(t.semesters)

    # Track courses taken, passed, and failed
    taken_course_identifiers: set[str] = set()
    passed_course_identifiers: set[str] = set()
    passed_course_keys_seen: set[str] = set()
    passed_credits_total: float = 0.0
    failed_course_items: list[CourseRiskItem] = []
    failed_credits_total: float = 0.0

    transcript_semester_tuples: list[tuple[str, int]] = []

    for entry in transcript_records:
        sem_label = entry.get("semester", "")
        if sem_label:
            parsed_sem = parse_semester(sem_label)
            transcript_semester_tuples.append(parsed_sem)

        courses_data = entry.get("courses", {})
        # courses_data can be dict {course_id_or_code: grade} or list of course objects
        items_to_check: list[tuple[Any, Any]] = []
        if isinstance(courses_data, dict):
            items_to_check = list(courses_data.items())
        elif isinstance(courses_data, list):
            for c_item in courses_data:
                if isinstance(c_item, dict):
                    cid = c_item.get("id") or c_item.get("course_id") or c_item.get("code")
                    grd = c_item.get("grade", c_item.get("score"))
                    items_to_check.append((cid, grd))

        for c_key, grade in items_to_check:
            c_key_str = str(c_key).strip().upper()
            taken_course_identifiers.add(c_key_str)

            c_credits, c_code, c_title = resolve_course_credits(c_key)
            if c_code:
                taken_course_identifiers.add(c_code.strip().upper())
            if c_title:
                taken_course_identifiers.add(c_title.strip().upper())

            if is_failed_grade(grade, threshold=failing_grade_threshold):
                # Course failed in transcript (including summer) -> add credit hours to counter
                credit_score_counter += c_credits
                failed_credits_total += c_credits
                failed_course_items.append(
                    CourseRiskItem(
                        course_identifier=c_key_str,
                        code=c_code,
                        title=c_title,
                        credit_hours=c_credits,
                        semester=sem_label,
                        grade=float(grade) if isinstance(grade, (int, float)) else None,
                        status="failed",
                    )
                )
            else:
                canonical_course_key = c_code.upper() if c_code else c_key_str
                if canonical_course_key not in passed_course_keys_seen:
                    passed_course_keys_seen.add(canonical_course_key)
                    passed_credits_total += c_credits

                passed_course_identifiers.add(c_key_str)
                if c_code:
                    passed_course_identifiers.add(c_code.upper())
                if c_title:
                    passed_course_identifiers.add(c_title.upper())

    # 6. Check if student began current semester (by seeing if it is there in transcript)
    current_sem_tuple = (current_season, current_year)
    has_begun_current_semester = False
    last_transcript_semester_str: Optional[str] = None

    if transcript_semester_tuples:
        # Sort transcript semesters chronologically
        transcript_semester_tuples.sort(key=lambda x: semester_compare_key(x[0], x[1]))
        latest_transcript_sem = transcript_semester_tuples[-1]
        last_transcript_semester_str = format_semester(latest_transcript_sem[0], latest_transcript_sem[1])

        # Check if current semester is present or if student has transcript at or past current semester
        for t_sem in transcript_semester_tuples:
            if t_sem[0] == current_season and t_sem[1] == current_year:
                has_begun_current_semester = True
                break
        if not has_begun_current_semester and semester_compare_key(latest_transcript_sem[0], latest_transcript_sem[1]) >= semester_compare_key(current_season, current_year):
            has_begun_current_semester = True

    # 7. Calculate Semesters Left (only 2 types of regular semesters: Winter and Spring)
    # If student began current semester: semesters left count begins by the NEXT regular semester
    # If not began: count begins from the current semester (or next regular if current is summer)
    start_counting_sem: tuple[str, int]
    if has_begun_current_semester:
        start_counting_sem = get_next_regular_semester(current_season, current_year)
    else:
        if normalize_season(current_season) == "Summer":
            start_counting_sem = get_next_regular_semester(current_season, current_year)
        else:
            start_counting_sem = (current_season, current_year)

    remaining_semesters_list = get_regular_semesters_between(start_counting_sem, target_finish_tuple)
    semesters_left = len(remaining_semesters_list)

    # 8. Check remaining courses student didn't take in degree program and calculate total degree credits
    remaining_degree_items: list[CourseRiskItem] = []
    remaining_degree_credits: float = 0.0
    degree_total_credits: float = 0.0

    degree_courses = student.degree.courses if student.degree and student.degree.courses else []
    for deg_c in degree_courses:
        c_credits, c_code, c_title = resolve_course_credits(deg_c)
        degree_total_credits += c_credits
        deg_c_str = str(deg_c).strip().upper()

        # Check if taken / passed
        is_taken = (
            deg_c_str in taken_course_identifiers
            or (c_code and c_code.upper() in taken_course_identifiers)
            or (c_title and c_title.upper() in taken_course_identifiers)
        )
        if not is_taken:
            credit_score_counter += c_credits
            remaining_degree_credits += c_credits
            remaining_degree_items.append(
                CourseRiskItem(
                    course_identifier=deg_c_str,
                    code=c_code,
                    title=c_title,
                    credit_hours=c_credits,
                    status="remaining_degree",
                )
            )

    # 9. Check Major: if student has a major, check major courses; if not, add 80 credits to counter
    remaining_major_items: list[CourseRiskItem] = []
    remaining_major_credits: float = 0.0
    major_total_credits: float = 0.0
    has_major = bool(student.major_id is not None and student.major)

    if has_major:
        major_courses = student.major.required_courses if student.major.required_courses else []
        for maj_c in major_courses:
            c_credits, c_code, c_title = resolve_course_credits(maj_c)
            major_total_credits += c_credits
            maj_c_str = str(maj_c).strip().upper()

            is_taken = (
                maj_c_str in taken_course_identifiers
                or (c_code and c_code.upper() in taken_course_identifiers)
                or (c_title and c_title.upper() in taken_course_identifiers)
            )
            if not is_taken:
                credit_score_counter += c_credits
                remaining_major_credits += c_credits
                remaining_major_items.append(
                    CourseRiskItem(
                        course_identifier=maj_c_str,
                        code=c_code,
                        title=c_title,
                        credit_hours=c_credits,
                        status="remaining_major",
                    )
                )
        major_credits_added = remaining_major_credits
        total_program_credits = degree_total_credits + major_total_credits
    else:
        # If student does not have a major -> add 80 to the counter
        credit_score_counter += UNDECLARED_MAJOR_CREDITS
        major_credits_added = UNDECLARED_MAJOR_CREDITS
        major_total_credits = UNDECLARED_MAJOR_CREDITS
        total_program_credits = degree_total_credits + UNDECLARED_MAJOR_CREDITS

    # 10. Divide sum of credit hours of remaining courses by number of semesters left
    if semesters_left > 0:
        credits_per_semester_needed = round(credit_score_counter / semesters_left, 2)
    else:
        credits_per_semester_needed = credit_score_counter

    # 11. Determine Risk Level
    # Standard load is 30 credits / semester. Overload above 30 indicates risk.
    if semesters_left == 0:
        risk_level = "Low" if credit_score_counter <= 0 else "Critical"
    elif credits_per_semester_needed <= STANDARD_SEMESTER_CREDITS:
        risk_level = "Low"
    elif credits_per_semester_needed <= STANDARD_SEMESTER_CREDITS + 6.0:  # <= 36.0
        risk_level = "Medium"
    else:
        risk_level = "High"

    summary_msg = (
        f"Student '{student.name}' is currently in {current_semester_str} (Semester {current_semester_index}). "
        f"Semesters remaining until {finish_semester_str}: {semesters_left}. "
        f"Total credits needed: {credit_score_counter:.1f} (Failed: {failed_credits_total:.1f}, "
        f"Degree remaining: {remaining_degree_credits:.1f}, "
        f"Major: {major_credits_added:.1f}). "
        f"Degree total course credits: {degree_total_credits:.1f} (Program total: {total_program_credits:.1f}). "
        f"Required workload: {credits_per_semester_needed:.1f} credits/semester (Standard: 30.0). "
        f"Risk Level: {risk_level}."
    )

    return GeneralRiskAnalysisResponse(
        student_id=student.id,
        student_name=student.name,
        student_email=student.email,
        institution=student.institution,
        enrollment_time=student.time_of_enrollment,
        current_date=current_dt,
        current_semester=current_semester_str,
        current_semester_index=current_semester_index,
        finish_semester=finish_semester_str,
        has_begun_current_semester=has_begun_current_semester,
        last_transcript_semester=last_transcript_semester_str,
        semesters_left=semesters_left,
        remaining_semesters=remaining_semesters_list,
        credit_score_counter=round(credit_score_counter, 2),
        credits_per_semester_needed=credits_per_semester_needed,
        standard_credits_per_semester=STANDARD_SEMESTER_CREDITS,
        has_major=has_major,
        risk_level=risk_level,
        degree_total_credits=round(degree_total_credits, 2),
        total_program_credits=round(total_program_credits, 2),
        passed_credits=round(passed_credits_total, 2),
        breakdown={
            "failed_courses_credits": failed_credits_total,
            "failed_courses": [item.model_dump() for item in failed_course_items],
            "degree_total_credits": round(degree_total_credits, 2),
            "major_total_credits": round(major_total_credits, 2),
            "total_program_credits": round(total_program_credits, 2),
            "passed_credits": round(passed_credits_total, 2),
            "remaining_degree_credits": remaining_degree_credits,
            "remaining_degree_courses": [item.model_dump() for item in remaining_degree_items],
            "remaining_major_credits": remaining_major_credits if has_major else 0.0,
            "remaining_major_courses": [item.model_dump() for item in remaining_major_items],
            "major_credits_added": major_credits_added,
            "undeclared_major_credits": UNDECLARED_MAJOR_CREDITS,
        },
        summary=summary_msg,
    )

