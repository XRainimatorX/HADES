# Annotation Guideline

The rules every labeller follows, so that two people labelling the same image draw the same boxes. HADES v0.1 has one question only: **is this object a consumer drone?** (PRD, section III). There is one class, `0: drone` (`data/classes.yaml`).

**Needs confirmation:** the numbers in rules 3 and 4 (a third of the drone, 8 pixels) and the other thresholds in sections 2–5 are proposals written when the guideline was drafted; the Project Owner confirms or changes them before labelling starts.

**Living document:** a rule is changed only with the Project Owner's approval, and labels made under an older rule are re-checked.

---

## Label format

One text file per image, with the same name and a `.txt` extension, one line per drone:

```text
<class_id> <x_center> <y_center> <width> <height>
0 0.4953 0.3125 0.0336 0.0396
```

```text
class_id    always 0
the rest    decimals from 0.0 to 1.0, relative to the image size (not pixels)
x_center    box centre, as a fraction of the image width, measured from the left edge
y_center    box centre, as a fraction of the image height, measured from the top edge
width       box width as a fraction of the image width
height      box height as a fraction of the image height
```

**A value outside 0.0 to 1.0 is a mistake in the label, not in the picture.** If a box reaches past the image edge, cut it at the edge (clamp it) when you create the label. File names and extensions are lower-case: `clip03_000120.jpg`, `clip03_000120.txt`. `validate_dataset()` checks all of this.

## 1. What counts as a drone

```text
Label    Any consumer-grade drone: a multicopter (quadcopter and similar) or a small fixed-wing
         drone of the kind sold to the public, in flight or hovering.
Do not   A bird, a kite, a balloon, a plane, a helicopter, an insect, a plastic bag, or a drone
         toy that is on the ground or in someone's hand.
Example  A white quadcopter hovering over a field, four arms and rotors visible: one box, class 0.
         A crow flying at the same place: no box.
Unsure   If two careful people could disagree about what the object is, do not label it. Note the
         image name in the labelling log so the Project Owner can rule on it.
```

## 2. How tightly a box is drawn

```text
Rule     The smallest rectangle that contains every visible part of the drone: body, arms,
         rotors, landing legs. Not the motion blur, not the shadow, not the camera on a gimbal
         if it hangs well below the body (include it only if it touches the body in the picture).
         The box is axis-aligned (not tilted).
Check    Zoom to 200 %. Each of the four edges of the box should touch an edge of the drone.
         A gap wider than about one tenth of the drone's width is too loose; a cut-off rotor
         is too tight.
Example  A quadcopter seen from the side: the left edge touches the tip of the left rotor, the
         right edge the tip of the right rotor, the top the highest rotor, the bottom the
         lowest landing leg.
```

## 3. A drone that is partly visible

```text
Rule     Label the part you can see, if it is at least a third of the drone, or if you are sure
         what it is. The box covers only the visible part. Where the drone is cut by the image
         edge, the box ends at the edge.
Example  A drone flying out of the top of the picture, with its lower half still in view: a box
         from the top edge of the picture down to the lowest visible part.
         Only a single rotor tip at the edge of the picture: no box.
```

## 4. A drone that is very small

```text
Rule     Label it if the drone is at least 8 pixels wide and 8 pixels high in the image and you
         can tell it is a drone (or what else it could be is much less likely). Below 8 pixels,
         or when it is only a dark dot that could be anything, do not label it.
Why      A box drawn around something no one can recognise teaches the model to alert on noise.
Example  A drone about 12 pixels wide against a clear sky, with a clear shape: one small box.
         A 5-pixel dark dot near the horizon: no box.
```

## 5. A drone hidden behind something

```text
Rule     Label only what is visible. If the drone is fully hidden (behind a tree, a building or
         a cloud), the image has no drone for this frame: no box. If a thin object crosses the
         drone (a wire, a branch) but the drone is still clearly there, draw one box around the
         whole drone and ignore the thin object.
Example  A drone passing behind a tree trunk: the frames where it is fully behind the trunk have
         no box; the frames where more than a third of it is in view have a box around the
         visible part.
         A power line across a drone's body: one box around the whole drone.
```

## 6. Images that contain no drone

```text
Rule     Keep them. They teach the model what is not a drone. Create an empty label file with the
         same name (no lines at all). Never delete the label file and never write a line with
         zeros.
Include  Empty sky, birds, aircraft, trees, buildings, glare and backlight: the things the
         model must not alert on.
Example  clip07_000450.jpg shows a flock of birds. clip07_000450.txt exists and is empty.
```

## Working rules

```text
Source     Label frames made by extract_frames() from the project's own footage. Do not add
           images found elsewhere unless the Project Owner has approved the source and the
           licence.
Clips      Frames of one source clip stay together: the split is made by clip, so the test
           images never resemble the training images because they came from the same video.
Check      Before handing in a batch, open some images with the boxes drawn on top and confirm
           the boxes sit on the drones. A label file that merely exists does not count.
Tool       The labelling tool must export the YOLO format and be approved by the Project Owner.
Videos     Original source videos are never committed to the repository.
```

## In one sentence

> Draw one tight box around every drone you can clearly see, leave an empty label file for every picture without one, and when you are not sure, do not label it and ask.
