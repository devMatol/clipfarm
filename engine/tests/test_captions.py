from clipfarm_engine.captions.ass import CaptionStyle, Word, build_ass, chunk_words, to_srt, ts

WORDS = [Word(1.0, 1.3, "Putain,"), Word(1.3, 1.6, "oh"), Word(1.6, 2.0, "non"), Word(2.0, 2.4, "Argh!"),
         Word(3.5, 3.8, "C'est"), Word(3.8, 4.4, "incroyable"), Word(4.4, 4.7, "mec")]


def test_timestamp_format():
    assert ts(0) == "0:00:00.00"
    assert ts(3725.5) == "1:02:05.50"


def test_chunks_are_short_and_split_on_punctuation_and_gaps():
    chunks = chunk_words(WORDS, CaptionStyle())
    assert all(len(c) <= 3 for c in chunks)
    assert chunks[1][-1].text == "Argh!"          # sentence end closes the chunk
    assert chunks[2][0].text == "C'est"           # 1.1 s gap opens a new one


def test_one_dialogue_per_word_with_highlight():
    ass = build_ass(WORDS)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == len(WORDS)
    assert all("\\c&H0000FFFF&" in d for d in dialogues)
    assert "PlayResY: 1920" in ass


def test_offset_shifts_to_clip_time_and_drops_words_before():
    ass = build_ass(WORDS, offset=3.0)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert dialogues[0].split(",")[1] == "0:00:00.50"
    assert len(dialogues) == 3


def test_braces_cannot_inject_ass_tags():
    ass = build_ass([Word(0, 1, "{\\b1}hack")])
    assert "{\\b1}" not in ass


def test_srt_export():
    srt = to_srt(WORDS)
    assert srt.startswith("1\n00:00:01,000 --> ")


def test_french_punctuation_tokens_are_glued_and_stretched_words_clamped():
    words = [Word(0.0, 0.4, "manette"), Word(0.45, 3.0, "!"), Word(3.4, 7.4, "prendre"), Word(7.5, 7.8, "la")]
    ass = build_ass(words)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 3                      # "!" is not a word of its own
    assert "MANETTE!" in dialogues[0]
    start, end = dialogues[1].split(",")[1:3]       # "prendre" highlighted at most 0.9 s
    assert (start, end) == ("0:00:03.40", "0:00:04.30")


def test_french_elision_is_glued_and_dialogues_never_overlap():
    words = [Word(0.50, 0.55, "C"), Word(0.58, 0.70, "'est"), Word(0.60, 0.72, "vrai"), Word(0.70, 1.6, "moi"),
             Word(2.0, 2.2, "j'"), Word(2.2, 2.5, "adore")]
    ass = build_ass(words)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    text = " ".join(dialogues)
    assert "C'EST" in text and "J'ADORE" in text and " 'EST" not in text
    times = [(d.split(",")[1], d.split(",")[2]) for d in dialogues]
    for (s1, e1), (s2, _) in zip(times, times[1:]):
        assert e1 <= s2, (e1, s2)
