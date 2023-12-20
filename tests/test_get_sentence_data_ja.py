import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath("scripts/pre-training"))
from flickr_combined import get_sentence_data_ja  # type: ignore


def test_get_sentence_data_ja() -> None:
    """
    2:[/EN#2/bodyparts ボサボサ髪]の1:[/EN#1/people ２人の若い男]が、4:[/EN#8/scene 庭]をうろつきながら3:[/EN#3/bodyparts 手]に視線を向けている。
    1:[/EN#1/people ２人の若者で白人男性]が、外の、2:[/EN#4/scene 低木の茂み]の近くにいる。
    2:[/EN#5/clothing 緑のシャツ]を着た1:[/EN#1/people ２人の男]が3:[/EN#9/scene 庭]に立っている。
    2:[/EN#7/clothing 青いシャツ]を着て、3:[/EN#9/scene 庭]に立っている1:[/EN#6/people 男]。
    1:[/EN#1/people ２人の友だち]が一緒に過ごす2:[/EN#10/other 時]を楽しむ。
    """
    sentence_annotations = get_sentence_data_ja(Path("tests/data/1000092795.txt"))
    assert len(sentence_annotations) == 5
    sentence_annotation = sentence_annotations[0]
    assert sentence_annotation["sentence"] == "ボサボサ髪の２人の若い男が、庭をうろつきながら手に視線を向けている。"
    assert sentence_annotation["phrases"] == [
        {
            "phrase": "ボサボサ髪",
            "phrase_id": "2",
            "phrase_type": "bodyparts",
            "first_char_index": 0,
        },
        {
            "phrase": "２人の若い男",
            "phrase_id": "1",
            "phrase_type": "people",
            "first_char_index": 6,
        },
        {"phrase": "庭", "phrase_id": "8", "phrase_type": "scene", "first_char_index": 14},
        {"phrase": "手", "phrase_id": "3", "phrase_type": "bodyparts", "first_char_index": 23},
    ]
