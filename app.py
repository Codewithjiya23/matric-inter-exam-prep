import base64
import html
import json
import re

import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-6"
MAX_FILE_MB = 20

st.set_page_config(page_title="Imtihan Tayyari", page_icon="📚", layout="centered")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu&display=swap');
.urdu { direction: rtl; text-align: right; font-family: 'Noto Nastaliq Urdu', serif; line-height: 2.2; font-size: 1.1rem; }
</style>
""",
    unsafe_allow_html=True,
)

client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

LANGS = {
    "English": "Explain in simple, clear English.",
    "اردو (Urdu)": "Explain in simple Urdu written in Urdu script (اردو). Keep technical terms from the textbook as they appear.",
    "Roman Urdu": "Explain in Roman Urdu: Urdu written in English letters, the way Pakistani students text "
    "(e.g. 'Yeh jawab sahi hai kyunke...'). Keep technical terms in English.",
}


# ---------- helpers ----------
def build_chapter_block(uploaded):
    """Turn the uploaded file into a Claude content block."""
    data = uploaded.getvalue()
    name = uploaded.name.lower()
    if name.endswith(".pdf"):
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(data).decode(),
            },
            "cache_control": {"type": "ephemeral"},
        }
    if name.endswith((".png", ".jpg", ".jpeg")):
        mt = "image/png" if name.endswith(".png") else "image/jpeg"
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mt,
                "data": base64.standard_b64encode(data).decode(),
            },
            "cache_control": {"type": "ephemeral"},
        }
    return {
        "type": "text",
        "text": "CHAPTER TEXT:\n" + data.decode("utf-8", errors="ignore"),
        "cache_control": {"type": "ephemeral"},
    }


def ask_json(chapter_block, instructions):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system="You are a careful Pakistani exam tutor. Use ONLY the supplied textbook chapter as your source. "
        "Reply with valid JSON only: no markdown fences, no extra text.",
        messages=[
            {
                "role": "user",
                "content": [chapter_block, {"type": "text", "text": instructions}],
            }
        ],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def generate_questions(chapter_block, cfg):
    types = []
    if cfg["mcq"]:
        types.append(f"{cfg['mcq']} MCQs (4 options A-D, one correct)")
    if cfg["short"]:
        types.append(f"{cfg['short']} short-answer questions (2-3 lines, 2 marks each)")
    if cfg["long"]:
        types.append(f"{cfg['long']} long/descriptive questions (5 marks each)")
    prompt = f"""Student: {cfg['level']}, subject: {cfg['subject']}, Pakistani board paper style, difficulty: {cfg['difficulty']}.
Create: {', '.join(types)}.
Questions must come strictly from this chapter and be written in the same language as the chapter.
Cover the whole chapter, including definitions, key concepts, numericals/examples if any.
JSON schema:
{{"questions":[{{"id":1,"type":"mcq|short|long","question":"...","options":["A) ..","B) ..","C) ..","D) .."],"answer":"A","marks":1}}]}}
Omit "options" and "answer" for short/long questions. MCQs are 1 mark each."""
    return ask_json(chapter_block, prompt)["questions"]


def grade(chapter_block, questions, answers, lang):
    payload = [
        {**q, "student_answer": answers.get(q["id"]) or "(left blank)"} for q in questions
    ]
    prompt = f"""Grade this student's answers strictly against the chapter.
{LANGS[lang]}
Questions with student answers:
{json.dumps(payload, ensure_ascii=False)}

Rules:
- MCQ: score is full marks if the student's letter equals "answer", else 0.
- Short/long: give partial credit for each correct key point from the chapter. Blank = 0.
- "feedback": what the student got right and what was missing (in the requested language).
- "explanation": teach the concept simply so the student understands why (in the requested language).
- "model_answer": a concise ideal answer based on the chapter (in the chapter's language).
- "chapter_reference": the heading/page/section in the chapter where the answer is found.
JSON schema:
{{"results":[{{"id":1,"score":0,"max":1,"verdict":"correct|partial|incorrect","feedback":"","explanation":"","model_answer":"","chapter_reference":""}}]}}"""
    return ask_json(chapter_block, prompt)["results"]


def show_text(text, lang):
    if lang.startswith("اردو"):
        st.markdown(
            f"<div class='urdu'>{html.escape(text).replace(chr(10), '<br>')}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.write(text)


# ---------- sidebar ----------
with st.sidebar:
    st.header("⚙️ Settings")
    level = st.selectbox("Class", ["Class 9 (Matric)", "Class 10 (Matric)", "FSc / FA Part 1 (Class 11)", "FSc / FA Part 2 (Class 12)"])
    subject = st.text_input("Subject", placeholder="e.g. Physics, Biology, Urdu, Pak Studies")
    difficulty = st.select_slider("Difficulty", ["Easy", "Medium", "Hard"], value="Medium")
    st.subheader("Number of questions")
    n_mcq = st.number_input("MCQs", 0, 15, 5)
    n_short = st.number_input("Short questions", 0, 10, 3)
    n_long = st.number_input("Long questions", 0, 5, 1)
    lang = st.radio("Explanation language", list(LANGS), index=2)

# ---------- main ----------
st.title("📚 Imtihan Tayyari")
st.caption("Upload a chapter from your textbook, practice, and get your answers checked.")

uploaded = st.file_uploader(
    "Upload chapter (PDF, photo, or .txt)", type=["pdf", "png", "jpg", "jpeg", "txt"]
)

if uploaded:
    if uploaded.size > MAX_FILE_MB * 1024 * 1024:
        st.error(f"File is too large. Please upload under {MAX_FILE_MB} MB (try a single chapter).")
        st.stop()

    if st.session_state.get("file_id") != (uploaded.name, uploaded.size):
        st.session_state.clear()
        st.session_state["file_id"] = (uploaded.name, uploaded.size)
        st.session_state["chapter"] = build_chapter_block(uploaded)

    if st.button("✨ Generate practice questions", type="primary"):
        if not (n_mcq or n_short or n_long):
            st.warning("Choose at least one question type in the sidebar.")
        else:
            with st.spinner("Reading your chapter and writing questions..."):
                try:
                    st.session_state["questions"] = generate_questions(
                        st.session_state["chapter"],
                        dict(level=level, subject=subject or "the subject", difficulty=difficulty,
                             mcq=n_mcq, short=n_short, long=n_long),
                    )
                    st.session_state.pop("results", None)
                except Exception as e:
                    st.error(f"Could not generate questions. Try again. ({e})")

questions = st.session_state.get("questions")
if questions:
    st.divider()
    answers = {}
    with st.form("quiz"):
        for q in questions:
            st.markdown(f"**Q{q['id']}. {q['question']}**  _({q.get('marks', 1)} mark)_")
            if q["type"] == "mcq":
                answers[q["id"]] = st.radio(
                    "Choose", q["options"], index=None, key=f"a{q['id']}", label_visibility="collapsed"
                )
                if answers[q["id"]]:
                    answers[q["id"]] = answers[q["id"]][0]  # keep the letter only
            else:
                answers[q["id"]] = st.text_area(
                    "Your answer", key=f"a{q['id']}", height=120 if q["type"] == "long" else 80,
                    label_visibility="collapsed",
                )
        submitted = st.form_submit_button("✅ Check my answers", type="primary")

    if submitted:
        with st.spinner("Checking against your chapter..."):
            try:
                st.session_state["results"] = grade(st.session_state["chapter"], questions, answers, lang)
                st.session_state["graded_lang"] = lang
            except Exception as e:
                st.error(f"Could not check answers. Try again. ({e})")

results = st.session_state.get("results")
if results and questions:
    st.divider()
    got = sum(r["score"] for r in results)
    total = sum(r["max"] for r in results)
    st.subheader(f"Score: {got} / {total}  ({round(100 * got / max(total, 1))}%)")
    st.progress(got / max(total, 1))
    by_id = {q["id"]: q for q in questions}
    icon = {"correct": "🟢", "partial": "🟡", "incorrect": "🔴"}
    glang = st.session_state.get("graded_lang", lang)
    for r in results:
        q = by_id.get(r["id"], {})
        with st.expander(f"{icon.get(r['verdict'], '⚪')} Q{r['id']} — {r['score']}/{r['max']}"):
            st.markdown(f"**{q.get('question', '')}**")
            st.markdown("**Feedback**")
            show_text(r["feedback"], glang)
            st.markdown("**Explanation**")
            show_text(r["explanation"], glang)
            st.markdown("**Model answer**")
            show_text(r["model_answer"], "English")
            st.caption(f"📖 Chapter reference: {r['chapter_reference']}")
    st.info("Tip: change the explanation language in the sidebar and press 'Check my answers' again to get it in another language.")
