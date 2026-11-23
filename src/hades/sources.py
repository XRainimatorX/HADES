"""Video input (work package A): picam, webcam and video-file sources."""

from __future__ import annotations

from typing import Optional

from hades.contracts import FramePacket

import cv2
import time

from dataclasses import replace

class VideoSource:
    """Implements ``contracts.Source`` for a camera or video file."""

    def open(self) -> None:
        """Connect to the camera or open the video file."""
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        """Return the newest frame, or None when the input has stopped."""
        raise NotImplementedError

    def close(self) -> None:
        """Release the camera or file; safe to call more than once."""
        raise NotImplementedError

class VideoFileSource(VideoSource):

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.capture = None
        self.frame_id = 0

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.video_path)

        #checking whether video file is opened
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Could not open video file")

        #assign initial frame to be 0
        self.frame_id = 0

    def read(self) -> Optional[FramePacket]:
        if self.capture is None:
            raise RuntimeError("Video is not opened")

        success, frame = self.capture.read()

        if not success:
            return None

        timestamp = time.monotonic_ns()
        frame.flags.writeable = False

        packet = FramePacket(
            frame_id = self.frame_id,
            timestamp = timestamp,
            image = frame,
            source_type = "video"
        )

        self.frame_id += 1

        return packet

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

#For webcam the actual image dimension depend on the camera settings
class WebcamSource(VideoSource):

    #for int = 0, zero is refering to the webcam from ur local compurter
    #what camera are we gonna use? the camera index is dependent on the camera we're using
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.capture = None
        self.frame_id = 0

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.camera_index)

        #checking whether webcam is opened
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Could not open webcam")

        #assign initial frame to be 0
        self.frame_id = 0

    def read(self) -> Optional[FramePacket]:
        if self.capture is None:
            raise RuntimeError("Video is not opened")

        success, frame = self.capture.read()

        if not success:
            return None

        timestamp = time.monotonic_ns()
        frame.flags.writeable = False

        packet = FramePacket(
            frame_id = self.frame_id,
            timestamp = timestamp,
            image = frame,
            source_type = "webcam"
        )

        self.frame_id += 1

        return packet

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

#assuming the virtual camera uses a prerecorded video as input
#idk how does the simulation work 
class VirtualPiCamSource(VideoSource):

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.capture = None
        self.frame_id = 0

    def open(self) -> None:
        self.capture = cv2.VideoCapture(self.video_path)

        #checking whether video file is opened
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Could not open video file")

        #assign initial frame to be 0
        self.frame_id = 0

    def read(self) -> Optional[FramePacket]:
        if self.capture is None:
            raise RuntimeError("Video is not opened")

        success, frame = self.capture.read()

        if not success:
            return None

        timestamp = time.monotonic_ns()
        frame.flags.writeable = False

        packet = FramePacket(
            frame_id = self.frame_id,
            timestamp = timestamp,
            image = frame,
            source_type = "picam"
        )

        self.frame_id += 1

        return packet

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None