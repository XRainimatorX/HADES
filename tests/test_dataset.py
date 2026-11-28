"""Tests for ml/dataset.py (work package C), following Issue C section 8.

Every test builds its dataset from the fixture videos in a temporary folder, never inside
``data/``, and checks values returned by the functions.
"""

# pylint: disable=use-implicit-booleaness-not-comparison

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest
from conftest import require_real_video

from ml.dataset import MANIFEST_COLUMNS, build_split, extract_frames, validate_dataset

CLASSES = 'schema_version: "0.2"\nnames:\n  0: drone\n'
DRONE_LABEL = "0 0.4953 0.3125 0.0336 0.0396\n"


def _clip_copies(tmp_path: Path, drone: Path, empty: Path) -> dict[str, Path]:
    """Four source clips (three with a drone, one without) copied from the fixture videos."""
    clips = {}
    for name, source in (
        ("clipa", drone),
        ("clipb", drone),
        ("clipc", drone),
        ("clipd", empty),
    ):
        target = tmp_path / "videos" / f"{name}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(require_real_video(source), target)
        clips[name] = target
    return clips


def _label_all(dataset: Path, clips_with_drone: set[str]) -> None:
    """Write a label file for every image under images/: a box if its clip has a drone."""
    for image in sorted((dataset / "images").rglob("*.jpg")):
        clip = image.stem.rsplit("_", 1)[0]
        label = dataset / "labels" / image.relative_to(dataset / "images").with_suffix(".txt")
        label.parent.mkdir(parents=True, exist_ok=True)
        label.write_text(DRONE_LABEL if clip in clips_with_drone else "", encoding="utf-8")


@pytest.fixture(name="unsplit")
def fixture_unsplit(tmp_path: Path, drone_daylight_01: Path, no_drone_01: Path) -> Path:
    """A labelled dataset with all images in one folder, before build_split()."""
    (tmp_path / "classes.yaml").write_text(CLASSES, encoding="utf-8")
    dataset = tmp_path / "dataset_v1"
    for path in _clip_copies(tmp_path, drone_daylight_01, no_drone_01).values():
        extract_frames(str(path), str(dataset / "images"), every_n=40)
    _label_all(dataset, {"clipa", "clipb", "clipc"})
    return dataset


@pytest.fixture(name="split")
def fixture_split(unsplit: Path) -> Path:
    """The same dataset after build_split()."""
    build_split(str(unsplit), (0.5, 0.25, 0.25), seed=42)
    return unsplit


def _manifest(dataset: Path) -> list[dict[str, str]]:
    with open(dataset / "split_manifest.csv", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# --- extract_frames -------------------------------------------------------------------------


def test_extract_frames_names_files_correctly_and_returns_their_paths(
    tmp_path: Path, drone_daylight_01: Path
) -> None:
    """Names are <clip>_<6 digits>.jpg, numbered by frame, lower-case, every n-th from 0."""
    video = tmp_path / "clip03.mp4"
    shutil.copy(require_real_video(drone_daylight_01), video)
    paths = extract_frames(str(video), str(tmp_path / "out"), every_n=30)
    names = [Path(p).name for p in paths]
    assert names[:3] == ["clip03_000000.jpg", "clip03_000030.jpg", "clip03_000060.jpg"]
    assert all(Path(p).is_file() and Path(p).suffix == ".jpg" for p in paths)
    assert [Path(p).parent for p in paths] == [tmp_path / "out"] * len(paths)


def test_extract_frames_every_frame_when_n_is_one(tmp_path: Path, drone_daylight_01: Path) -> None:
    """With n = 1 consecutive frame numbers are saved."""
    video = tmp_path / "c.mp4"
    shutil.copy(require_real_video(drone_daylight_01), video)
    paths = extract_frames(str(video), str(tmp_path / "out"), every_n=1)
    assert [Path(p).name for p in paths[:3]] == ["c_000000.jpg", "c_000001.jpg", "c_000002.jpg"]


def test_extract_frames_rejects_a_bad_step_and_a_missing_video(tmp_path: Path) -> None:
    """every_n below 1 and an unreadable video are errors that say what is wrong."""
    with pytest.raises(ValueError, match="every_n"):
        extract_frames("x.mp4", str(tmp_path), every_n=0)
    with pytest.raises(RuntimeError, match="missing.mp4"):
        extract_frames(str(tmp_path / "missing.mp4"), str(tmp_path / "out"), every_n=5)


# --- build_split ----------------------------------------------------------------------------


def test_build_split_keeps_every_source_clip_within_a_single_split(unsplit: Path) -> None:
    """No clip has rows in two splits, and every split has at least one clip."""
    path = build_split(str(unsplit), (0.5, 0.25, 0.25), seed=42)
    assert path == str(unsplit / "split_manifest.csv")
    rows = _manifest(unsplit)
    splits_of: dict[str, set[str]] = {}
    for row in rows:
        splits_of.setdefault(row["source_clip"], set()).add(row["split"])
    assert set(splits_of) == {"clipa.mp4", "clipb.mp4", "clipc.mp4", "clipd.mp4"}
    assert all(len(splits) == 1 for splits in splits_of.values())
    assert {row["split"] for row in rows} == {"train", "val", "test"}


def test_build_split_writes_the_manifest_columns_and_moves_the_files(unsplit: Path) -> None:
    """The header is the one in docs/spec.md; images and labels are in their split folders."""
    build_split(str(unsplit), (0.5, 0.25, 0.25), seed=42)
    header = (unsplit / "split_manifest.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(MANIFEST_COLUMNS) == "image,split,source_clip,frame_index,num_objects"
    row = _manifest(unsplit)[0]
    assert row["image"] == f"images/{row['split']}/{Path(row['image']).name}"
    assert (unsplit / row["image"]).is_file()
    assert (unsplit / "labels" / row["split"] / f"{Path(row['image']).stem}.txt").is_file()
    assert not list((unsplit / "images").glob("*.jpg"))
    for entry in _manifest(unsplit):
        stem = Path(entry["image"]).stem
        assert entry["frame_index"] == str(int(stem.rsplit("_", 1)[1]))
        assert entry["num_objects"] == ("0" if entry["source_clip"] == "clipd.mp4" else "1")


def test_build_split_with_the_same_seed_gives_the_same_manifest_twice(
    tmp_path: Path, drone_daylight_01: Path, no_drone_01: Path
) -> None:
    """Two fresh datasets split with the same seed have identical manifests."""
    manifests = []
    for run in ("one", "two"):
        base = tmp_path / run
        base.mkdir()
        (base / "classes.yaml").write_text(CLASSES, encoding="utf-8")
        for path in _clip_copies(base, drone_daylight_01, no_drone_01).values():
            extract_frames(str(path), str(base / "dataset_v1" / "images"), every_n=40)
        _label_all(base / "dataset_v1", {"clipa", "clipb", "clipc"})
        build_split(str(base / "dataset_v1"), (0.5, 0.25, 0.25), seed=7)
        manifests.append((base / "dataset_v1" / "split_manifest.csv").read_text(encoding="utf-8"))
    assert manifests[0] == manifests[1]


def test_build_split_is_a_no_op_when_run_again_and_different_seeds_can_differ(
    unsplit: Path,
) -> None:
    """Re-running with the same seed changes nothing; another seed may regroup the clips."""
    build_split(str(unsplit), (0.5, 0.25, 0.25), seed=1)
    first = (unsplit / "split_manifest.csv").read_text(encoding="utf-8")
    build_split(str(unsplit), (0.5, 0.25, 0.25), seed=1)
    assert (unsplit / "split_manifest.csv").read_text(encoding="utf-8") == first
    outcomes = set()
    for seed in range(8):
        build_split(str(unsplit), (0.5, 0.25, 0.25), seed=seed)
        outcomes.add((unsplit / "split_manifest.csv").read_text(encoding="utf-8"))
    assert len(outcomes) > 1
    assert validate_dataset(str(unsplit)) == []


@pytest.mark.parametrize("ratios", [(0.5, 0.5, 0.5), (1.2, -0.1, -0.1), (0.5, 0.5, 0.0, 0.0)])
def test_build_split_rejects_bad_ratios(unsplit: Path, ratios: tuple[float, ...]) -> None:
    """Ratios must be three non-negative numbers summing to 1."""
    with pytest.raises(ValueError, match="ratios"):
        build_split(str(unsplit), ratios, seed=1)  # type: ignore[arg-type]


def test_build_split_refuses_an_image_without_a_label_or_with_a_bad_name(unsplit: Path) -> None:
    """The error names the image that is the problem."""
    image = next((unsplit / "images").glob("*.jpg"))
    (unsplit / "labels" / f"{image.stem}.txt").unlink()
    with pytest.raises(ValueError, match=image.name):
        build_split(str(unsplit), (0.5, 0.25, 0.25), seed=1)
    (unsplit / "labels" / f"{image.stem}.txt").write_text("", encoding="utf-8")
    renamed = image.with_name("badname.jpg")
    image.rename(renamed)
    with pytest.raises(ValueError, match="badname.jpg"):
        build_split(str(unsplit), (0.5, 0.25, 0.25), seed=1)


def test_build_split_refuses_a_folder_without_images(tmp_path: Path) -> None:
    """Nothing to split is an error, not an empty manifest."""
    with pytest.raises(ValueError, match="No .jpg images"):
        build_split(str(tmp_path), (0.7, 0.15, 0.15), seed=1)


def test_build_split_with_two_clips_leaves_the_split_without_a_clip_empty(
    tmp_path: Path, drone_daylight_01: Path
) -> None:
    """A split with ratio 0 gets no clip; the others get one each."""
    (tmp_path / "classes.yaml").write_text(CLASSES, encoding="utf-8")
    dataset = tmp_path / "dataset_v1"
    for name in ("x", "y"):
        video = tmp_path / f"{name}.mp4"
        shutil.copy(require_real_video(drone_daylight_01), video)
        extract_frames(str(video), str(dataset / "images"), every_n=60)
    _label_all(dataset, {"x", "y"})
    build_split(str(dataset), (0.5, 0.5, 0.0), seed=3)
    assert {row["split"] for row in _manifest(dataset)} == {"train", "val"}


# --- validate_dataset -----------------------------------------------------------------------


def test_validate_dataset_returns_an_empty_list_for_a_valid_dataset(split: Path) -> None:
    """A dataset built by the tools validates cleanly, with and without drones in each split."""
    assert validate_dataset(str(split)) == []


def _a_labelled_image(dataset: Path) -> tuple[Path, Path]:
    """An image of a clip with a drone, and its label file."""
    for row in _manifest(dataset):
        if row["num_objects"] == "1":
            image = dataset / row["image"]
            return image, dataset / "labels" / row["split"] / f"{image.stem}.txt"
    raise AssertionError("no labelled image")


def test_validate_dataset_reports_a_missing_label_file(split: Path) -> None:
    """An image with no label file is named."""
    image, label = _a_labelled_image(split)
    label.unlink()
    relative = image.relative_to(split).as_posix()
    assert f"{relative}: no label file" in validate_dataset(str(split))


def test_validate_dataset_reports_a_label_file_without_an_image(split: Path) -> None:
    """A label whose image is gone is named."""
    image, label = _a_labelled_image(split)
    image.unlink()
    relative = label.relative_to(split).as_posix()
    assert f"{relative}: no image" in validate_dataset(str(split))


def test_validate_dataset_reports_a_label_line_with_the_wrong_number_of_values(
    split: Path,
) -> None:
    """Four values, and six values, are both reported with the line number."""
    _, label = _a_labelled_image(split)
    relative = label.relative_to(split).as_posix()
    label.write_text("0 0.5 0.5 0.1\n0 0.5 0.5 0.1 0.1 0.2\n", encoding="utf-8")
    problems = validate_dataset(str(split))
    assert f"{relative}: line 1 has 4 values, expected 5" in problems
    assert f"{relative}: line 2 has 6 values, expected 5" in problems


def test_validate_dataset_reports_a_value_outside_zero_to_one(split: Path) -> None:
    """The offending value and its line are in the message."""
    _, label = _a_labelled_image(split)
    relative = label.relative_to(split).as_posix()
    label.write_text("0 1.02 0.5 0.1 0.1\n", encoding="utf-8")
    assert f"{relative}: line 1 value 1.02 outside 0–1" in validate_dataset(str(split))
    label.write_text("0 0.5 -0.1 0.1 0.1\n0 nan 0.5 0.1 0.1\n", encoding="utf-8")
    problems = validate_dataset(str(split))
    assert f"{relative}: line 1 value -0.1 outside 0–1" in problems
    assert f"{relative}: line 2 value nan outside 0–1" in problems


def test_validate_dataset_accepts_the_edges_zero_and_one(split: Path) -> None:
    """0.0 and 1.0 are inside the range."""
    _, label = _a_labelled_image(split)
    label.write_text("0 0.0 1.0 1.0 0.0\n", encoding="utf-8")
    assert validate_dataset(str(split)) == []


def test_validate_dataset_reports_an_unknown_class_number(split: Path) -> None:
    """Class 1 is not in classes.yaml; a non-integer class is also reported."""
    _, label = _a_labelled_image(split)
    relative = label.relative_to(split).as_posix()
    label.write_text("1 0.5 0.5 0.1 0.1\nx 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    problems = validate_dataset(str(split))
    assert f"{relative}: line 1 class 1 not in classes.yaml" in problems
    assert f"{relative}: line 2 class 'x' is not an integer" in problems


def test_validate_dataset_reports_a_value_that_is_not_a_number(split: Path) -> None:
    """Text where a decimal belongs is reported."""
    _, label = _a_labelled_image(split)
    relative = label.relative_to(split).as_posix()
    label.write_text("0 abc 0.5 0.1 0.1\n", encoding="utf-8")
    assert f"{relative}: line 1 value 'abc' is not a number" in validate_dataset(str(split))


def test_validate_dataset_reports_a_manifest_that_does_not_match_the_files(split: Path) -> None:
    """A wrong object count, a missing row, a ghost row, a wrong split and a wrong clip."""
    rows = _manifest(split)
    victim = next(row for row in rows if row["num_objects"] == "1")
    other = next(row for row in rows if row is not victim)
    mismatched = [dict(row) for row in rows if row is not other]
    for row in mismatched:
        if row["image"] == victim["image"]:
            row["num_objects"] = "3"
            row["split"] = "test" if row["split"] != "test" else "train"
            row["source_clip"] = "other.mp4"
    mismatched.append({**other, "image": "images/train/ghost_000000.jpg"})
    with open(split / "split_manifest.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(mismatched)
    problems = validate_dataset(str(split))
    assert f"split_manifest.csv: {other['image']} is not listed" in problems
    assert (
        "split_manifest.csv: images/train/ghost_000000.jpg is listed but the image does not exist"
        in problems
    )
    assert f"split_manifest.csv: {victim['image']} says 3 objects, label has 1" in problems
    assert any(p.startswith(f"split_manifest.csv: {victim['image']} says split") for p in problems)
    assert f"split_manifest.csv: {victim['image']} says source clip other.mp4" in problems


def test_validate_dataset_reports_a_missing_or_malformed_manifest(split: Path) -> None:
    """No manifest, and a manifest with the wrong columns, are both reported."""
    manifest = split / "split_manifest.csv"
    manifest.write_text("image,split\nimages/train/x.jpg,train\n", encoding="utf-8")
    assert any("columns are" in p for p in validate_dataset(str(split)))
    manifest.unlink()
    assert "split_manifest.csv: not found" in validate_dataset(str(split))


def test_validate_dataset_reports_a_clip_in_two_splits(split: Path) -> None:
    """Moving one frame of a clip to another split is caught even if the manifest is updated."""
    row = _manifest(split)[0]
    stem = Path(row["image"]).stem
    other = "test" if row["split"] != "test" else "train"
    for kind, suffix in (("images", ".jpg"), ("labels", ".txt")):
        (split / kind / other).mkdir(parents=True, exist_ok=True)
        shutil.move(
            str(split / kind / row["split"] / f"{stem}{suffix}"),
            str(split / kind / other / f"{stem}{suffix}"),
        )
    clip = stem.rsplit("_", 1)[0]
    assert any(
        p.startswith(f"source clip {clip} appears in more than one split")
        for p in validate_dataset(str(split))
    )


def test_validate_dataset_reports_upper_case_extensions_and_misplaced_files(split: Path) -> None:
    """IMG.JPG, a .png and a file outside the split folders are each reported."""
    image, label = _a_labelled_image(split)
    image.rename(image.with_suffix(".JPG"))
    label.rename(label.with_suffix(".TXT"))
    (split / "images" / "train" / "extra.png").write_bytes(b"x")
    (split / "images" / "stray.jpg").write_bytes(b"x")
    problems = validate_dataset(str(split))
    assert any(p.endswith(".JPG: upper-case extension, expected .jpg") for p in problems)
    assert any(p.endswith(".TXT: upper-case extension, expected .txt") for p in problems)
    assert "images/train/extra.png: wrong type, expected .jpg" in problems
    assert "images/stray.jpg: not inside images/<train|val|test>/" in problems


def test_validate_dataset_reports_missing_classes_folders_and_the_dataset_itself(
    tmp_path: Path, split: Path
) -> None:
    """A missing dataset folder, classes.yaml or label folder is reported, not a crash."""
    assert validate_dataset(str(tmp_path / "nope")) == [f"{tmp_path / 'nope'}: folder not found"]
    (split.parent / "classes.yaml").unlink()
    assert "classes.yaml: not found next to dataset_v1/" in validate_dataset(str(split))
    (split.parent / "classes.yaml").write_text("names: []\n", encoding="utf-8")
    assert "classes.yaml: has no 'names' mapping" in validate_dataset(str(split))
    shutil.rmtree(split / "labels")
    assert "labels/: folder not found" in validate_dataset(str(split))


def test_validate_dataset_ignores_hidden_files_and_blank_label_lines(split: Path) -> None:
    """A .gitkeep and blank lines in a label file are not problems."""
    (split / "images" / "train" / ".gitkeep").write_text("", encoding="utf-8")
    _, label = _a_labelled_image(split)
    label.write_text("\n" + DRONE_LABEL + "\n", encoding="utf-8")
    assert validate_dataset(str(split)) == []
