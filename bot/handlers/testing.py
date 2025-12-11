from __future__ import annotations

from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..services.models import Question, QuestionResult, QuestionType
from ..services.question_engine import QuestionEngine
from ..services.result_store import ResultStore
from ..services.state import Session, UserProfile
from .states import TestStates

router = Router(name="test-block")

QUESTION_ENGINE: QuestionEngine | None = None
RESULT_STORE: ResultStore | None = None
SUMMARY_CHUNK_LIMIT = 3500
ROLE_CALLBACK_PREFIX = "role|"


def setup_dependencies(
    question_engine: QuestionEngine,
    result_store: ResultStore,
) -> None:
    global QUESTION_ENGINE, RESULT_STORE
    QUESTION_ENGINE = question_engine
    RESULT_STORE = result_store


def get_engine() -> QuestionEngine:
    if QUESTION_ENGINE is None:
        raise RuntimeError("Question engine is not configured")
    return QUESTION_ENGINE


def get_result_store() -> ResultStore:
    if RESULT_STORE is None:
        raise RuntimeError("Result store is not configured")
    return RESULT_STORE


def block_title(session: Session, block_number: int) -> str:
    return session.block_titles.get(block_number, f"Блок {block_number}")


def block_total(session: Session, block_number: int) -> int:
    return len(session.block_one) if block_number == 1 else len(session.block_two)


def format_answer_text(question: Question, answer: Any) -> str:
    # Keep answer formatting compact for review/summary blocks
    if question.type == QuestionType.matching:
        mapping = dict(answer or {})
        if not mapping:
            return "—"
        right_lookup = {item.id: item.label for item in question.matching_right}
        lines: List[str] = []
        for item in question.matching_left:
            right_id = mapping.get(item.id)
            if not right_id:
                lines.append(f"{item.id}. {item.label} → —")
                continue
            right_label = right_lookup.get(right_id, right_id)
            lines.append(f"{item.id}. {item.label} → {right_id}. {right_label}")
        return "\n".join(lines)
    choices_map = {choice.id: choice.text for choice in question.choices}
    if isinstance(answer, (list, tuple, set)):
        ids = [str(value) for value in answer]
    elif answer is None:
        ids = []
    else:
        ids = [str(answer)]
    if question.type == QuestionType.single_choice and len(ids) > 1:
        ids = ids[:1]
    texts: List[str] = []
    for choice in question.choices:
        if choice.id in ids:
            texts.append(choice.text)
    if not texts:
        return "—" if not ids else "; ".join(ids)
    return "; ".join(texts)


def append_answer_block(lines: List[str], title: str, question: Question, answer: Any) -> None:
    text = format_answer_text(question, answer)
    if "\n" in text:
        lines.append(f"{title}:")
        lines.extend(text.splitlines())
    else:
        lines.append(f"{title}: {text}")


def correct_answer_payload(question: Question) -> Any:
    if question.type == QuestionType.matching:
        return question.correct_mapping
    return [choice.id for choice in question.choices if choice.is_correct]


def build_review_text(session: Session, result: QuestionResult) -> str:
    index = session.review_index or 0
    total = max(1, len(session.answers))
    status = "Верно ✅" if result.is_correct else "Неверно ❌"
    lines = [
        f"Просмотр ответов • {index + 1}/{total}",
        f"{block_title(session, result.question.block)} — {status}",
        "",
        result.question.prompt,
        "",
    ]
    append_answer_block(lines, "Ваш ответ", result.question, result.user_answer)
    if not result.is_correct:
        append_answer_block(
            lines,
            "Правильный ответ",
            result.question,
            correct_answer_payload(result.question),
        )
    lines.append("")
    lines.append(result.question.explanation)
    lines.append("")
    lines.append("Используйте «Назад»/«Вперёд», чтобы просмотреть другие ответы.")
    return "\n".join(lines).strip()


def resolve_display_question(session: Session) -> tuple[Question, QuestionResult | None]:
    if session.review_index is not None:
        if 0 <= session.review_index < len(session.answers):
            result = session.answers[session.review_index]
            return result.question, result
        session.review_index = None
    return session.current_question(), None


def build_question_text(
    session: Session,
    question: Question,
    review_result: QuestionResult | None = None,
) -> str:
    def choice_index_map() -> dict[str, int]:
        return {choice.id: idx for idx, choice in enumerate(question.choices, start=1)}

    if review_result:
        return build_review_text(session, review_result)
    block = session.current_block
    block_total_count = block_total(session, block)
    block_index = session.current_index + 1
    overall = session.answered_count() + 1
    lines = [
        f"{block_title(session, block)} • вопрос {block_index}/{block_total_count}",
        f"Общий прогресс: {overall}/{session.total_questions()}",
        "",
        question.prompt,
    ]
    if question.type in (QuestionType.single_choice, QuestionType.multi_choice):
        lines.append("")
        lines.append("Варианты ответов:")
        for idx, choice in enumerate(question.choices, start=1):
            lines.append(f"{idx}. {choice.text}")
    if question.type == QuestionType.multi_choice:
        selected = session.multi_choice_state.get(question.id, set())
        if selected:
            index_lookup = choice_index_map()
            texts = [
                f"{index_lookup.get(choice.id, '?')}. {choice.text}"
                for choice in question.choices
                if choice.id in selected
            ]
            lines.append("")
            lines.append("Выбрано: " + "; ".join(texts))
    if question.type == QuestionType.matching:
        mapping = session.matching_state.get(question.id, {})
        lines.append("")
        lines.append("Текущее сопоставление:")
        right_lookup = {item.id: item.label for item in question.matching_right}
        for item in question.matching_left:
            target = mapping.get(item.id)
            label = right_lookup.get(target, "—" if not target else f"{target}")
            if target:
                label = f"{target}: {right_lookup.get(target, '')}"
            lines.append(f"{item.id}. {item.label} → {label}")
        focus = session.matching_focus.get(question.id)
        if focus:
            lines.append("")
            lines.append(f"Выбрана позиция {focus}. Теперь нажмите букву справа.")
    return "\n".join(lines)


def build_keyboard(
    session: Session,
    question: Question,
    review_result: QuestionResult | None = None,
) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    if review_result:
        add_navigation_buttons(builder, session)
        return builder
    if question.type == QuestionType.single_choice:
        for idx, choice in enumerate(question.choices, start=1):
            builder.button(
                text=str(idx),
                callback_data=f"sc|{question.id}|{choice.id}",
            )
        builder.adjust(1)
        add_navigation_buttons(builder, session)
        return builder
    if question.type == QuestionType.multi_choice:
        selected = session.multi_choice_state.get(question.id, set())
        for idx, choice in enumerate(question.choices, start=1):
            prefix = "✅" if choice.id in selected else "▫️"
            builder.button(
                text=f"{prefix} {idx}",
                callback_data=f"mc|toggle|{question.id}|{choice.id}",
            )
        builder.button(text="Очистить", callback_data=f"mc|reset|{question.id}")
        builder.button(text="Отправить", callback_data=f"mc|submit|{question.id}")
        builder.adjust(1)
        add_navigation_buttons(builder, session)
        return builder
    if question.type == QuestionType.matching:
        focus = session.matching_focus.get(question.id)
        left_row: List[InlineKeyboardButton] = []
        for item in question.matching_left:
            prefix = "▶" if focus == item.id else item.id
            left_row.append(
                InlineKeyboardButton(
                    text=prefix,
                    callback_data=f"match|select|{question.id}|{item.id}",
                )
            )
        builder.row(*left_row)
        right_row: List[InlineKeyboardButton] = []
        for item in question.matching_right:
            right_row.append(
                InlineKeyboardButton(
                    text=item.id,
                    callback_data=f"match|assign|{question.id}|{item.id}",
                )
            )
        builder.row(*right_row)
        builder.button(text="Сбросить", callback_data=f"match|reset|{question.id}")
        builder.button(text="Отправить", callback_data=f"match|submit|{question.id}")
        builder.adjust(1)
        add_navigation_buttons(builder, session)
        return builder
    add_navigation_buttons(builder, session)
    return builder


def add_navigation_buttons(builder: InlineKeyboardBuilder, session: Session) -> None:
    if not session.answers:
        return
    buttons = [
        InlineKeyboardButton(text="◀️ Назад", callback_data="nav|prev"),
    ]
    if session.review_index is not None:
        buttons.append(
            InlineKeyboardButton(text="▶️ Вперёд", callback_data="nav|next")
        )
    builder.row(*buttons)


async def render_question_message(message: Message, state: FSMContext, session: Session) -> None:
    question, review_result = resolve_display_question(session)
    text = build_question_text(session, question, review_result=review_result)
    markup = build_keyboard(session, question, review_result=review_result).as_markup()
    bot = message.bot
    if session.question_message_id:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=session.question_message_id,
            text=text,
            reply_markup=markup,
        )
    else:
        sent = await message.answer(text, reply_markup=markup)
        session.question_message_id = sent.message_id
    await state.update_data(session=session)


def feedback_text(result: QuestionResult) -> str:
    prefix = "Верно ✅" if result.is_correct else "Неверно ❌"
    text = f"{prefix}\n{result.question.explanation}"
    if len(text) > 190:
        text = text[:187] + "..."
    return text


def chunk_text_for_telegram(text: str, limit: int = SUMMARY_CHUNK_LIMIT) -> List[str]:
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    buffer = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not buffer else buffer + "\n\n" + paragraph
        if len(candidate) <= limit:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            buffer = ""
        if len(paragraph) <= limit:
            buffer = paragraph
            continue
        for idx in range(0, len(paragraph), limit):
            chunks.append(paragraph[idx : idx + limit])
    if buffer:
        chunks.append(buffer)
    return chunks


async def send_summary(message: Message, summary: str) -> None:
    chunks = chunk_text_for_telegram(summary)
    if not chunks:
        return
    chunks[0] = "Итоговый отчёт\n\n" + chunks[0]
    for chunk in chunks:
        await message.answer(chunk)


async def finish_session(message: Message, state: FSMContext, session: Session) -> None:
    bot = message.bot
    session.review_index = None
    if session.question_message_id:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=session.question_message_id,
            text="Тест завершён. Формируем индивидуальный отчёт...",
            reply_markup=None,
        )
        session.question_message_id = None
    summary = build_summary(session)
    await send_summary(message, summary)
    await state.clear()


def build_summary(session: Session) -> str:
    mistakes = [answer for answer in session.answers if not answer.is_correct]
    total = session.total_questions()
    correct_total = sum(1 for answer in session.answers if answer.is_correct)
    block_one_results = [a for a in session.answers if a.question.block == 1]
    block_two_results = [a for a in session.answers if a.question.block == 2]
    block_one_correct = sum(1 for a in block_one_results if a.is_correct)
    block_two_correct = sum(1 for a in block_two_results if a.is_correct)

    lines: List[str] = [
        f"Итоги для {session.profile.full_name} ({session.profile.position}):",
        f"Всего: {correct_total}/{total} верно, ошибок: {total - correct_total}.",
    ]
    if block_one_results:
        lines.append(f"{block_title(session, 1)}: {block_one_correct}/{len(session.block_one)} верно.")
    if block_two_results:
        lines.append(f"{block_title(session, 2)}: {block_two_correct}/{len(session.block_two)} верно.")

    if not mistakes:
        lines.append("")
        lines.append("Ошибок нет — отличная работа!")
        return "\n".join(lines)

    def inline_answer(text: str) -> str:
        return text.replace("\n", "; ")

    lines.append("")
    lines.append("Ошибки в вопросах:")
    for idx, result in enumerate(mistakes, start=1):
        user_answer = inline_answer(format_answer_text(result.question, result.user_answer))
        correct_answer = inline_answer(
            format_answer_text(
                result.question,
                correct_answer_payload(result.question),
            )
        )
        lines.append(
            f"{idx}. {result.question.prompt} "
            f"Ответ: {user_answer}. "
            f"Правильно: {correct_answer}."
        )

    topics = sorted(
        {
            result.question.topic
            for result in mistakes
            if result.question.topic
        }
    )
    lines.append("")
    lines.append("Темы с ошибками:")
    if topics:
        for topic in topics:
            lines.append(f"- {topic}")
    else:
        lines.append("- Нет тем с ошибками")
    return "\n".join(lines)


async def log_result(
    message: Message,
    result: QuestionResult,
    session: Session,
    state: FSMContext,
) -> None:
    get_result_store().append(
        user_id=message.from_user.id if message.from_user else 0,
        profile=session.profile,
        result=result,
        session_id=(await state.get_data()).get("session_id"),
    )


async def handle_transition(message: Message, state: FSMContext, session: Session) -> None:
    bot = message.bot
    if session.question_message_id:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=session.question_message_id,
            text=f"{block_title(session, 1)} завершён. Готовим второй блок...",
            reply_markup=None,
        )
        session.question_message_id = None
    await message.answer(
        f"{block_title(session, 1)} завершён ✅\n"
        f"Теперь {block_title(session, 2)}. "
        f"Впереди {len(session.block_two)} вопросов по выбранной роли."
    )
    await state.update_data(session=session)


def ensure_session(data: Dict[str, object]) -> Session:
    session = data.get("session")
    if not isinstance(session, Session):
        raise RuntimeError("Session not initialized")
    return session


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    greeting = (
        "Привет! Этот бот проводит аттестацию: сначала 15 общих вопросов по тестам "
        "с указанием кодов, затем блок по выбранной роли "
        "(Менеджер ОКС/ОП, Администратор МО, Медсестра МО). "
        "Ответы даём только кнопками, видно сразу, верно или нет.\n\n"
        "Для начала укажите, пожалуйста, ваше ФИО."
    )
    await message.answer(greeting)
    await state.set_state(TestStates.waiting_full_name)


@router.message(TestStates.waiting_full_name)
async def collect_full_name(message: Message, state: FSMContext) -> None:
    full_name = (message.text or "").strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, укажите ФИО полностью.")
        return
    await state.update_data(full_name=full_name)
    engine = get_engine()
    roles = engine.list_roles()
    if not roles:
        await message.answer("Роли для аттестации не настроены. Обратитесь к администратору бота.")
        return
    builder = InlineKeyboardBuilder()
    for role in roles:
        builder.button(
            text=role.title,
            callback_data=f"{ROLE_CALLBACK_PREFIX}{role.slug}",
        )
    builder.adjust(1)
    intro_lines = [
        "Спасибо! Теперь выберите должность для аттестации:",
    ]
    for role in roles:
        intro_lines.append(f"- {role.title}")
    await message.answer("\n".join(intro_lines), reply_markup=builder.as_markup())
    await state.set_state(TestStates.choosing_role)


@router.callback_query(F.data.startswith(ROLE_CALLBACK_PREFIX), TestStates.choosing_role)
async def handle_role_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    slug = callback.data.replace(ROLE_CALLBACK_PREFIX, "", 1)
    engine = get_engine()
    role = engine.get_role(slug)
    if not role:
        await callback.answer("Неизвестная роль.")
        return
    data = await state.get_data()
    full_name = data.get("full_name")
    if not full_name:
        await callback.answer("Не удалось получить ФИО, начните заново.")
        await state.clear()
        return
    profile = UserProfile(full_name=full_name, position=role.title)
    block_one, block_two = engine.build_blocks(slug)
    if not block_one:
        await callback.message.answer("Не удалось собрать вопросы общего блока. Обратитесь к администратору.")
        await callback.answer()
        return
    if not block_two:
        await callback.message.answer("Для выбранной роли пока нет вопросов. Обратитесь к администратору.")
        await callback.answer()
        return
    session = Session(
        profile=profile,
        block_one=block_one,
        block_two=block_two,
        block_titles={
            1: "Блок 1 — Общие тесты",
            2: f"Блок 2 — {role.title}",
        },
        role_slug=slug,
    )
    session_id = uuid4_hex()
    await state.update_data(session=session, session_id=session_id)
    await state.set_state(TestStates.answering)
    await callback.message.answer(
        f"Отлично, {full_name}! "
        "Начинаем с общих вопросов, затем перейдём к блоку по выбранной роли.\n"
        "На каждый вопрос отвечаем кнопками. Вопросы появляются один за другим в одном сообщении."
    )
    await render_question_message(callback.message, state, session)
    await callback.answer("Роль выбрана, начинаем!")


@router.message(TestStates.choosing_role)
async def remind_role_choice(message: Message) -> None:
    await message.answer("Выберите должность из списка кнопок выше, чтобы продолжить тест.")


def uuid4_hex() -> str:
    import uuid

    return uuid.uuid4().hex


async def process_final_step(
    message: Message,
    state: FSMContext,
    session: Session,
    advance_status: str,
) -> None:
    if advance_status == "switch":
        await handle_transition(message, state, session)
        await render_question_message(message, state, session)
    elif advance_status == "done":
        await finish_session(message, state, session)
    else:
        await render_question_message(message, state, session)


async def finalize_answer(
    message: Message,
    state: FSMContext,
    session: Session,
    question: Question,
    user_answer: object,
) -> QuestionResult:
    result = get_engine().evaluate(question, user_answer)
    session.answers.append(result)
    await log_result(message, result, session, state)
    advance_status = session.advance()
    await state.update_data(session=session)
    await process_final_step(message, state, session, advance_status)
    return result


def ensure_active_question(session: Session, question_id: str) -> Question:
    question = session.current_question()
    if question.id != question_id:
        raise ValueError("Stale question")
    return question


@router.callback_query(F.data.startswith("sc|"), TestStates.answering)
async def handle_single_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    _, question_id, choice_id = callback.data.split("|")
    data = await state.get_data()
    session = ensure_session(data)
    try:
        question = ensure_active_question(session, question_id)
    except ValueError:
        await callback.answer("Этот вопрос уже закрыт.")
        return
    result = await finalize_answer(
        callback.message,
        state,
        session,
        question,
        choice_id,
    )
    await callback.answer(feedback_text(result), show_alert=True)


@router.callback_query(F.data.startswith("mc|"), TestStates.answering)
async def handle_multi_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    parts = callback.data.split("|")
    if len(parts) < 3:
        await callback.answer()
        return
    _, action, question_id, *rest = parts
    data = await state.get_data()
    session = ensure_session(data)
    try:
        question = ensure_active_question(session, question_id)
    except ValueError:
        await callback.answer("Этот вопрос уже закрыт.")
        return
    selected = session.multi_choice_state.setdefault(question_id, set())
    if action == "toggle":
        choice_id = rest[0]
        if choice_id in selected:
            selected.remove(choice_id)
        else:
            selected.add(choice_id)
        await state.update_data(session=session)
        await callback.answer("Выбор обновлён")
        await render_question_message(callback.message, state, session)
        return
    if action == "reset":
        selected.clear()
        await state.update_data(session=session)
        await callback.answer("Выбор очищен")
        await render_question_message(callback.message, state, session)
        return
    if action == "submit":
        if not selected:
            await callback.answer("Выберите хотя бы один вариант.")
            return
        result = await finalize_answer(
            callback.message,
            state,
            session,
            question,
            list(selected),
        )
        session.multi_choice_state.pop(question_id, None)
        await callback.answer(feedback_text(result), show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("match|"), TestStates.answering)
async def handle_matching(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    parts = callback.data.split("|")
    if len(parts) < 3:
        await callback.answer()
        return
    _, action, question_id, *rest = parts
    data = await state.get_data()
    session = ensure_session(data)
    try:
        question = ensure_active_question(session, question_id)
    except ValueError:
        await callback.answer("Этот вопрос уже закрыт.")
        return
    mapping = session.matching_state.setdefault(question_id, {})
    session.matching_focus.setdefault(question_id, None)
    if action == "select":
        session.matching_focus[question_id] = rest[0]
        await state.update_data(session=session)
        await callback.answer("Позиция выбрана")
        await render_question_message(callback.message, state, session)
        return
    if action == "assign":
        left = session.matching_focus.get(question_id)
        if not left:
            await callback.answer("Сначала выберите номер слева.")
            return
        right = rest[0]
        # ensure right not used elsewhere
        for key, value in list(mapping.items()):
            if value == right:
                del mapping[key]
        mapping[left] = right
        session.matching_focus[question_id] = None
        await state.update_data(session=session)
        await callback.answer("Пара зафиксирована")
        await render_question_message(callback.message, state, session)
        return
    if action == "reset":
        mapping.clear()
        session.matching_focus[question_id] = None
        await state.update_data(session=session)
        await callback.answer("Сопоставление очищено")
        await render_question_message(callback.message, state, session)
        return
    if action == "submit":
        if len(mapping) != len(question.matching_left):
            await callback.answer("Заполните все пары перед отправкой.")
            return
        cleaned = dict(mapping)
        result = await finalize_answer(
            callback.message,
            state,
            session,
            question,
            cleaned,
        )
        session.matching_state.pop(question_id, None)
        session.matching_focus.pop(question_id, None)
        await callback.answer(feedback_text(result), show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("nav|"), TestStates.answering)
async def handle_navigation(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    _, direction = callback.data.split("|", 1)
    data = await state.get_data()
    session = ensure_session(data)
    if not session.answers:
        await callback.answer("Пока нет пройденных вопросов.")
        return
    if direction == "prev":
        if session.review_index is None:
            session.review_index = len(session.answers) - 1
        else:
            session.review_index = max(0, session.review_index - 1)
        await render_question_message(callback.message, state, session)
        await callback.answer("Показан предыдущий вопрос.")
        return
    if direction == "next":
        if session.review_index is None:
            await callback.answer("Вы уже на текущем вопросе.")
            return
        if session.review_index < len(session.answers) - 1:
            session.review_index += 1
            await render_question_message(callback.message, state, session)
            await callback.answer("Показан следующий пройденный вопрос.")
            return
        session.review_index = None
        await render_question_message(callback.message, state, session)
        await callback.answer("Возвращаемся к текущему вопросу.")
        return
    await callback.answer()
