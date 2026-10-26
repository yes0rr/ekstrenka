"""HTML-страницы (интерфейс после регистрации/входа)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import get_current_user, render
from ..models import Answer, Attempt, AttemptStatus, Log, Mode, Role, Test, User
from ..services import loads

router = APIRouter(tags=["pages"], include_in_schema=False)


def _guard(user: User | None) -> RedirectResponse | None:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return None


# ----------------------------- главная -----------------------------
@router.get("/")
def index(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect

    if user.role == Role.teacher.value:
        tests = db.scalars(
            select(Test).options(selectinload(Test.questions))
            .where(Test.author_id == user.id).order_by(Test.created_at.desc())
        ).all()
        attempts = db.scalars(
            select(Attempt).options(selectinload(Attempt.student), selectinload(Attempt.test))
            .join(Test).where(Test.author_id == user.id)
            .order_by(Attempt.started_at.desc()).limit(8)
        ).all()
        students_count = db.scalar(select(func.count(User.id)).where(User.role == Role.student.value)) or 0
        return render(
            request, "dashboard_teacher.html", user,
            tests=tests, attempts=attempts, students_count=students_count,
            published_count=sum(1 for t in tests if t.is_published),
            finished_count=db.scalar(
                select(func.count(Attempt.id)).join(Test).where(
                    Test.author_id == user.id, Attempt.status == "finished"
                )
            ) or 0,
        )

    tests = db.scalars(
        select(Test).options(selectinload(Test.questions), selectinload(Test.author))
        .where(Test.is_published.is_(True)).order_by(Test.created_at.desc())
    ).all()
    attempts = db.scalars(
        select(Attempt).options(selectinload(Attempt.test))
        .where(Attempt.student_id == user.id).order_by(Attempt.started_at.desc()).limit(10)
    ).all()
    return render(
        request, "dashboard_student.html", user,
        tests=tests, attempts=attempts,
        my_finished=sum(1 for a in attempts if a.status == "finished"),
    )


# ----------------------------- преподаватель -----------------------------
@router.get("/teacher/tests")
def teacher_tests(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    tests = db.scalars(
        select(Test).options(selectinload(Test.questions))
        .where(Test.author_id == user.id).order_by(Test.created_at.desc())
    ).all()
    return render(request, "teacher_tests.html", user, tests=tests)


@router.get("/teacher/tests/new")
def teacher_test_new(request: Request, user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    return render(request, "teacher_test_new.html", user)


@router.get("/teacher/tests/{test_id}")
def teacher_test_edit(test_id: int, request: Request, db: Session = Depends(get_db),
                      user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    test = db.scalar(
        select(Test).options(selectinload(Test.questions), selectinload(Test.author)).where(Test.id == test_id)
    )
    if not test or test.author_id != user.id:
        return RedirectResponse("/teacher/tests", status_code=303)
    questions = [
        {
            "id": q.id,
            "text": q.text,
            "kind": q.kind,
            "options": loads(q.options, []),
            "correct": loads(q.correct, None),
            "points": q.points,
            "hint": q.hint,
        }
        for q in test.questions
    ]
    return render(request, "teacher_test_edit.html", user, test=test, questions=questions)


@router.get("/teacher/results")
def teacher_results(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    attempts = db.scalars(
        select(Attempt)
        .options(
            selectinload(Attempt.student),
            selectinload(Attempt.test).selectinload(Test.questions),
            selectinload(Attempt.answers),
        )
        .join(Test).where(Test.author_id == user.id)
        .order_by(Attempt.started_at.desc())
    ).all()
    return render(request, "teacher_results.html", user, attempts=attempts)


@router.get("/teacher/logs")
def teacher_logs(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    logs = db.scalars(
        select(Log).options(selectinload(Log.user)).order_by(Log.created_at.desc()).limit(200)
    ).all()
    return render(request, "teacher_logs.html", user, logs=logs)


@router.get("/teacher/users")
def teacher_users(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    if user.role != Role.teacher.value:
        return RedirectResponse("/", status_code=303)
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return render(request, "teacher_users.html", user, users=users)


# ----------------------------- учащийся -----------------------------
@router.get("/student/tests/{test_id}")
def student_run_test(test_id: int, request: Request, db: Session = Depends(get_db),
                     user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    test = db.scalar(
        select(Test).options(selectinload(Test.questions), selectinload(Test.author)).where(Test.id == test_id)
    )
    if not test or not test.is_published:
        return RedirectResponse("/", status_code=303)
    return render(request, "student_run.html", user, test=test, Mode=Mode)


@router.get("/student/attempts")
def student_attempts(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    attempts = db.scalars(
        select(Attempt)
        .options(selectinload(Attempt.test).selectinload(Test.questions), selectinload(Attempt.answers))
        .where(Attempt.student_id == user.id).order_by(Attempt.started_at.desc())
    ).all()
    return render(request, "student_attempts.html", user, attempts=attempts)


@router.get("/student/attempts/{attempt_id}")
def student_attempt_result(attempt_id: int, request: Request, db: Session = Depends(get_db),
                           user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    attempt = db.scalar(
        select(Attempt)
        .options(
            selectinload(Attempt.test).selectinload(Test.questions),
            selectinload(Attempt.answers).selectinload(Answer.question),
        )
        .where(Attempt.id == attempt_id)
    )
    if not attempt or (attempt.student_id != user.id and user.role != Role.teacher.value):
        return RedirectResponse("/", status_code=303)
    return render(request, "student_result.html", user, attempt=attempt, loads=loads)


# ----------------------------- инструкция по экстренной помощи -----------------------------
@router.get("/instruction/emergency-help")
def emergency_help_instruction(request: Request, user: User | None = Depends(get_current_user)):
    if (redirect := _guard(user)) is not None:
        return redirect
    return render(request, "emergency_help.html", user)


# ----------------------------- обучение / тренировочный режим -----------------------------
@router.get("/training")
def training_page(request: Request, db: Session = Depends(get_db),
                  user: User | None = Depends(get_current_user)):
    """Точка входа «Обучение»: список опубликованных испытаний.

    Раньше здесь была заглушка с модальным окном — камера включалась, а дальше
    ничего не происходило. Теперь это честный список со ссылками на прохождение.
    """
    if (redirect := _guard(user)) is not None:
        return redirect
    tests = db.scalars(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.is_published.is_(True))
        .order_by(Test.mode.desc(), Test.created_at.desc())
    ).all()
    open_attempts = {}
    if user.role == Role.student.value:
        rows = db.scalars(
            select(Attempt).where(
                Attempt.student_id == user.id,
                Attempt.status == AttemptStatus.in_progress.value,
            )
        ).all()
        open_attempts = {a.test_id: a.id for a in rows}
    return render(request, "training.html", user, tests=tests, open_attempts=open_attempts)
