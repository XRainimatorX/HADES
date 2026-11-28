"""Frame extraction, dataset split and validation (work package C).

Layout, as defined in ``docs/spec.md`` (section C)::

    data/
    ├── classes.yaml
    └── dataset_v1/
        ├── images/{train,val,test}/<clip>_<6-digit frame number>.jpg
        ├── labels/{train,val,test}/<clip>_<6-digit frame number>.txt
        └── split_manifest.csv

``extract_frames()`` writes images; they are labelled by hand; ``build_split()`` then moves the
images and their labels into the three splits, one whole source clip at a time; and
``validate_dataset()`` checks the result. The manifest records ``<clip>.mp4`` as the source clip
because the name of a frame file carries only the clip's name, not its extension.
"""

from __future__ import annotations

import csv
import math
import random  # nosec B311
import re
import shutil
from pathlib import Path

import cv2
import yaml

SPLITS = ("train", "val", "test")
MANIFEST_NAME = "split_manifest.csv"
MANIFEST_COLUMNS = ["image", "split", "source_clip", "frame_index", "num_objects"]
SOURCE_CLIP_EXTENSION = ".mp4"
_FRAME_NAME = re.compile(r"^(?P<clip>.+)_(?P<frame>\d{6})$")
_RATIO_TOLERANCE = 1e-6


def extract_frames(video_path: str, out_dir: str, every_n: int) -> list[str]:
    """Save every n-th frame of a video as an image and return the saved paths.

    Frames are numbered from 0 and the files are named ``<clip>_<frame number, 6 digits>.jpg``
    with a lower-case extension, where ``<clip>`` is the video's file name without its extension.
    The first frame (number 0) is always saved.

    Raises:
        ValueError: ``every_n`` is less than 1.
        RuntimeError: the video cannot be opened, or an image cannot be written.
    """
    if every_n < 1:
        raise ValueError(f"every_n must be at least 1, got {every_n}")
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    clip = Path(video_path).stem
    saved: list[str] = []
    try:
        index = 0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if index % every_n == 0:
                path = target / f"{clip}_{index:06d}.jpg"
                if not cv2.imwrite(str(path), image):
                    raise RuntimeError(f"Cannot write image: {path}")
                saved.append(str(path))
            index += 1
    finally:
        capture.release()
    return saved


def _parse_frame_name(stem: str) -> tuple[str, int] | None:
    """Split ``<clip>_<6 digits>`` into the clip name and the frame number."""
    match = _FRAME_NAME.match(stem)
    if match is None:
        return None
    return match.group("clip"), int(match.group("frame"))


def _split_clips(
    clip_sizes: dict[str, int], ratios: tuple[float, float, float], seed: int
) -> dict[str, str]:
    """Give every clip to one split so the image counts follow the ratios as closely as possible.

    The clips are shuffled with the seed. Each split that has a ratio above zero first receives
    one clip (if there are enough), so no split is left empty; the rest go to the split that is
    furthest below its target.
    """
    clips = sorted(clip_sizes)
    random.Random(seed).shuffle(clips)  # nosec B311
    total = sum(clip_sizes.values())
    targets = {name: total * ratio for name, ratio in zip(SPLITS, ratios)}
    counts = {name: 0 for name in SPLITS}
    assignment: dict[str, str] = {}
    wanted = [name for name, ratio in zip(SPLITS, ratios) if ratio > 0]
    for position, clip in enumerate(clips):
        if position < len(wanted):
            choice = wanted[position]
        else:
            choice = max(wanted, key=lambda name: targets[name] - counts[name])
        assignment[clip] = choice
        counts[choice] += clip_sizes[clip]
    return assignment


def _count_objects(label_path: Path) -> int:
    """The number of non-blank lines in a label file."""
    text = label_path.read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.strip())


def _find_label(labels_dir: Path, stem: str) -> Path | None:
    """The label file for an image, wherever it is under ``labels/``."""
    matches = sorted(labels_dir.rglob(f"{stem}.txt"))
    return matches[0] if matches else None


def _move_into_splits(
    root: Path, items: list[tuple[Path, Path, str, int]], assignment: dict[str, str]
) -> list[list[str]]:
    """Move each image and label into its split folder; return the manifest rows."""
    rows: list[list[str]] = []
    for image, label, clip, frame in items:
        split = assignment[clip]
        new_image = root / "images" / split / image.name
        new_label = root / "labels" / split / label.name
        for old, new in ((image, new_image), (label, new_label)):
            if old != new:
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(new))
        rows.append(
            [
                new_image.relative_to(root).as_posix(),
                split,
                f"{clip}{SOURCE_CLIP_EXTENSION}",
                str(frame),
                str(_count_objects(new_label)),
            ]
        )
    return rows


def _collect_items(root: Path) -> list[tuple[Path, Path, str, int]]:
    """Pair every image with its label file; return (image, label, clip, frame number)."""
    images_dir, labels_dir = root / "images", root / "labels"
    images = sorted(images_dir.rglob("*.jpg"))
    if not images:
        raise ValueError(f"No .jpg images under {images_dir}")
    items: list[tuple[Path, Path, str, int]] = []
    for image in images:
        parsed = _parse_frame_name(image.stem)
        if parsed is None:
            raise ValueError(f"{image.name} is not named <clip>_<6-digit frame number>.jpg")
        label = _find_label(labels_dir, image.stem)
        if label is None:
            raise ValueError(f"{image.name} has no label file under {labels_dir}")
        items.append((image, label, parsed[0], parsed[1]))
    return items


def build_split(dataset_dir: str, ratios: tuple[float, float, float], seed: int) -> str:
    """Assign images to splits by source video, write the manifest, return its path.

    Every ``.jpg`` under ``images/`` (in any folder) must have a label file ``<name>.txt`` under
    ``labels/``. All images of one source clip go to the same split. The images and labels are
    moved into ``images/<split>/`` and ``labels/<split>/``. The same seed on the same files
    always gives the same split, so running it again changes nothing.

    Raises:
        ValueError: the ratios are not three non-negative numbers summing to 1, an image is not
            named ``<clip>_<6 digits>.jpg``, there are no images, or an image has no label file.
    """
    if len(ratios) != 3 or any(r < 0 for r in ratios):
        raise ValueError(f"ratios must be three non-negative numbers, got {ratios}")
    if not math.isclose(sum(ratios), 1.0, abs_tol=_RATIO_TOLERANCE):
        raise ValueError(f"ratios must sum to 1, got {sum(ratios)}")
    root = Path(dataset_dir)
    items = _collect_items(root)

    sizes: dict[str, int] = {}
    for _, _, clip, _ in items:
        sizes[clip] = sizes.get(clip, 0) + 1
    assignment = _split_clips(sizes, ratios, seed)

    rows = _move_into_splits(root, items, assignment)
    rows.sort()
    manifest = root / MANIFEST_NAME
    with open(manifest, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(MANIFEST_COLUMNS)
        writer.writerows(rows)
    return str(manifest)


def _class_ids(root: Path) -> tuple[set[int], list[str]]:
    """The class numbers in ``classes.yaml`` (next to the dataset folder), and any problem."""
    path = root.parent / "classes.yaml"
    if not path.is_file():
        return set(), [f"{path.name}: not found next to {root.name}/"]
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    names = data.get("names") if isinstance(data, dict) else None
    if not isinstance(names, dict) or not names:
        return set(), [f"{path.name}: has no 'names' mapping"]
    return {int(key) for key in names}, []


def _file_problems(root: Path) -> tuple[dict[str, Path], dict[str, Path], list[str]]:
    """Find the images and labels in the split folders; report names and folders that are wrong."""
    problems: list[str] = []
    images: dict[str, Path] = {}
    labels: dict[str, Path] = {}
    for kind, suffix, found in (("images", ".jpg", images), ("labels", ".txt", labels)):
        base = root / kind
        if not base.is_dir():
            problems.append(f"{kind}/: folder not found")
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            relative = path.relative_to(root).as_posix()
            split = path.relative_to(base).parts[0]
            if len(path.relative_to(base).parts) != 2 or split not in SPLITS:
                problems.append(f"{relative}: not inside {kind}/<train|val|test>/")
            elif path.suffix != suffix:
                reason = "upper-case extension" if path.suffix.lower() == suffix else "wrong type"
                problems.append(f"{relative}: {reason}, expected {suffix}")
            else:
                found[relative] = path
    return images, labels, problems


def _label_problems(relative: str, path: Path, class_ids: set[int]) -> list[str]:
    """Check every line of one label file."""
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            problems.append(f"{relative}: line {number} has {len(parts)} values, expected 5")
            continue
        try:
            class_id = int(parts[0])
        except ValueError:
            problems.append(f"{relative}: line {number} class '{parts[0]}' is not an integer")
        else:
            if class_id not in class_ids:
                problems.append(f"{relative}: line {number} class {class_id} not in classes.yaml")
        for text in parts[1:]:
            try:
                value = float(text)
            except ValueError:
                problems.append(f"{relative}: line {number} value '{text}' is not a number")
                continue
            if not 0.0 <= value <= 1.0:
                problems.append(f"{relative}: line {number} value {text} outside 0–1")
    return problems


def _manifest_problems(root: Path, images: dict[str, Path], labels: dict[str, Path]) -> list[str]:
    """Compare the manifest with the files."""
    path = root / MANIFEST_NAME
    if not path.is_file():
        return [f"{MANIFEST_NAME}: not found"]
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_COLUMNS:
            return [
                f"{MANIFEST_NAME}: columns are {reader.fieldnames}, expected {MANIFEST_COLUMNS}"
            ]
        rows = list(reader)
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        image = row["image"]
        if image in seen:
            problems.append(f"{MANIFEST_NAME}: {image} is listed more than once")
            continue
        seen.add(image)
        if image not in images:
            problems.append(f"{MANIFEST_NAME}: {image} is listed but the image does not exist")
            continue
        problems.extend(_row_problems(row, image, labels))
    for image in sorted(set(images) - seen):
        problems.append(f"{MANIFEST_NAME}: {image} is not listed")
    return problems


def _row_problems(row: dict[str, str], image: str, labels: dict[str, Path]) -> list[str]:
    """Check one manifest row against the name, folder and label of its image."""
    problems: list[str] = []
    split = Path(image).parts[1]
    parsed = _parse_frame_name(Path(image).stem)
    if row["split"] != split:
        problems.append(f"{MANIFEST_NAME}: {image} says split {row['split']}, is in {split}")
    if parsed is not None:
        if row["source_clip"] != f"{parsed[0]}{SOURCE_CLIP_EXTENSION}":
            problems.append(f"{MANIFEST_NAME}: {image} says source clip {row['source_clip']}")
        if row["frame_index"] != str(parsed[1]):
            problems.append(f"{MANIFEST_NAME}: {image} says frame {row['frame_index']}")
    label = labels.get(f"labels/{split}/{Path(image).stem}.txt")
    if label is not None and row["num_objects"] != str(_count_objects(label)):
        problems.append(
            f"{MANIFEST_NAME}: {image} says {row['num_objects']} objects, "
            f"label has {_count_objects(label)}"
        )
    return problems


def _clip_split_problems(images: dict[str, Path]) -> list[str]:
    """A source clip must not have frames in more than one split."""
    splits_of: dict[str, set[str]] = {}
    for relative in images:
        parsed = _parse_frame_name(Path(relative).stem)
        if parsed is not None:
            splits_of.setdefault(parsed[0], set()).add(Path(relative).parts[1])
    return [
        f"source clip {clip} appears in more than one split: {', '.join(sorted(splits))}"
        for clip, splits in sorted(splits_of.items())
        if len(splits) > 1
    ]


def validate_dataset(dataset_dir: str) -> list[str]:
    """Return a list of problems; empty means the dataset is valid.

    Reports: an image with no label file, a label file with no image, a label line without
    exactly five values, a class number not in ``classes.yaml``, a value outside 0.0–1.0, any
    mismatch between the manifest and the files, a file with an upper-case extension or in the
    wrong folder, and a source clip that appears in more than one split.
    """
    root = Path(dataset_dir)
    if not root.is_dir():
        return [f"{dataset_dir}: folder not found"]
    class_ids, problems = _class_ids(root)
    images, labels, found = _file_problems(root)
    problems.extend(found)
    for relative in sorted(images):
        label = "labels" + relative[len("images") : -len(".jpg")] + ".txt"
        if label not in labels:
            problems.append(f"{relative}: no label file")
    for relative in sorted(labels):
        image = "images" + relative[len("labels") : -len(".txt")] + ".jpg"
        if image not in images:
            problems.append(f"{relative}: no image")
        else:
            problems.extend(_label_problems(relative, labels[relative], class_ids))
    problems.extend(_clip_split_problems(images))
    problems.extend(_manifest_problems(root, images, labels))
    return problems
