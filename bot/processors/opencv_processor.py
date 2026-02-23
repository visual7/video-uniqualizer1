"""
OpenCV-based processors for methods that require frame-by-frame manipulation:
  54 – steganographic UUID mark in LSB
  58 – hidden pixel (random pixel color change per frame)
  63 – local warp deformation
  64 – DCT coefficient modification
"""
from __future__ import annotations

import os
import random
import uuid
import math
import tempfile
from pathlib import Path
from typing import Optional, Callable


def _get_cv2():
    import cv2
    return cv2

def _get_np():
    import numpy as np
    return np


# ── Helpers ────────────────────────────────────────────────────────────────────

def _open_video(path: str):
    cv2 = _get_cv2()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap

def _get_video_props(cap) -> dict:
    cv2 = _get_cv2()
    return {
        "fps":    cap.get(cv2.CAP_PROP_FPS) or 30,
        "width":  int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "count":  int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }

def _open_writer(path: str, fps: float, width: int, height: int):
    cv2 = _get_cv2()
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    return writer


# ── Method 54: Steganographic UUID in LSB ────────────────────────────────────

def apply_54_steganography(
    input_path: str,
    output_path: str,
    intensity: int,
    seed: int,
    progress_cb: Optional[Callable] = None,
) -> None:
    """
    Embeds a UUID in the LSB of a few pixels in each frame.
    Invisible to the naked eye but changes hash.
    """
    cv2 = _get_cv2()
    np  = _get_np()

    rng = random.Random(seed ^ 0xDEADBEEF)
    mark_uuid = str(uuid.UUID(int=rng.getrandbits(128)))
    mark_bytes = mark_uuid.encode("ascii")

    cap   = _open_video(input_path)
    props = _get_video_props(cap)
    writer = _open_writer(output_path, props["fps"], props["width"], props["height"])

    total = max(1, props["count"])
    frame_rng = random.Random(seed)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        if h > 0 and w > 0:
            # Embed some bytes in LSB of random pixels
            byte_to_embed = mark_bytes[frame_idx % len(mark_bytes)]
            bits = [(byte_to_embed >> i) & 1 for i in range(8)]
            for bit_idx, bit in enumerate(bits):
                px = frame_rng.randint(0, w - 1)
                py = frame_rng.randint(0, h - 1)
                ch = bit_idx % 3
                val = int(frame[py, px, ch])
                frame[py, px, ch] = np.uint8((val & 0xFE) | bit)

        writer.write(frame)
        frame_idx += 1

        if progress_cb and frame_idx % 30 == 0:
            progress_cb(frame_idx / total)

    cap.release()
    writer.release()


# ── Method 58: Hidden pixel modification ─────────────────────────────────────

def apply_58_hidden_pixels(
    input_path: str,
    output_path: str,
    intensity: int,
    seed: int,
    progress_cb: Optional[Callable] = None,
) -> None:
    """
    Randomly modifies 1–5 pixels per frame by small color deltas.
    Completely invisible but ensures unique hash per frame.
    """
    cv2 = _get_cv2()
    np  = _get_np()

    n_pixels = max(1, int(intensity_val(intensity, 1, 5)))
    rng = random.Random(seed ^ 0xCAFEBABE)

    cap    = _open_video(input_path)
    props  = _get_video_props(cap)
    writer = _open_writer(output_path, props["fps"], props["width"], props["height"])

    total = max(1, props["count"])
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        for _ in range(n_pixels):
            px = rng.randint(0, w - 1)
            py = rng.randint(0, h - 1)
            for ch in range(3):
                delta = rng.randint(-3, 3)
                frame[py, px, ch] = np.clip(int(frame[py, px, ch]) + delta, 0, 255)

        writer.write(frame)
        frame_idx += 1

        if progress_cb and frame_idx % 30 == 0:
            progress_cb(frame_idx / total)

    cap.release()
    writer.release()


# ── Method 63: Local warp deformation ────────────────────────────────────────

def apply_63_local_warp(
    input_path: str,
    output_path: str,
    intensity: int,
    seed: int,
    progress_cb: Optional[Callable] = None,
) -> None:
    """
    Applies random local warp deformations to random rectangular regions.
    Amplitude 1–3px based on intensity.
    """
    cv2 = _get_cv2()
    np  = _get_np()

    amp = max(1, int(intensity_val(intensity, 1, 4)))  # pixel amplitude
    rng = random.Random(seed ^ 0xBEEFCAFE)

    cap    = _open_video(input_path)
    props  = _get_video_props(cap)
    h, w   = props["height"], props["width"]
    writer = _open_writer(output_path, props["fps"], w, h)

    # Build warp map (applied consistently to all frames for consistency)
    map_x = np.zeros((h, w), dtype=np.float32)
    map_y = np.zeros((h, w), dtype=np.float32)
    for y in range(h):
        for x in range(w):
            map_x[y, x] = x
            map_y[y, x] = y

    # Add a few random local perturbations
    n_regions = max(1, int(intensity_val(intensity, 1, 5)))
    for _ in range(n_regions):
        rx = rng.randint(w // 4, 3 * w // 4)
        ry = rng.randint(h // 4, 3 * h // 4)
        rw = rng.randint(w // 8, w // 4)
        rh = rng.randint(h // 8, h // 4)
        dx = rng.uniform(-amp, amp)
        dy = rng.uniform(-amp, amp)
        x1, x2 = max(0, rx - rw // 2), min(w - 1, rx + rw // 2)
        y1, y2 = max(0, ry - rh // 2), min(h - 1, ry + rh // 2)
        map_x[y1:y2, x1:x2] += dx
        map_y[y1:y2, x1:x2] += dy

    map_x = np.clip(map_x, 0, w - 1)
    map_y = np.clip(map_y, 0, h - 1)

    total = max(1, props["count"])
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        warped = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR)
        writer.write(warped)
        frame_idx += 1

        if progress_cb and frame_idx % 30 == 0:
            progress_cb(frame_idx / total)

    cap.release()
    writer.release()


# ── Method 64: DCT coefficient modification ──────────────────────────────────

def apply_64_dct_modification(
    input_path: str,
    output_path: str,
    intensity: int,
    seed: int,
    progress_cb: Optional[Callable] = None,
) -> None:
    """
    Applies a subtle DCT-domain modification to luma channel.
    Modifies mid-frequency coefficients by a small fraction.
    """
    cv2 = _get_cv2()
    np  = _get_np()

    strength = intensity_val(intensity, 0.005, 0.02)
    rng = random.Random(seed ^ 0x12345678)

    cap    = _open_video(input_path)
    props  = _get_video_props(cap)
    writer = _open_writer(output_path, props["fps"], props["width"], props["height"])

    # Block size for DCT
    block = 8

    total = max(1, props["count"])
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Work in YCrCb color space on Y channel
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        y = ycrcb[:, :, 0].astype(np.float32)
        h, w = y.shape

        # Process 8×8 blocks
        for i in range(0, h - block, block):
            for j in range(0, w - block, block):
                tile = y[i:i+block, j:j+block]
                dct_tile = cv2.dct(tile)
                # Modify AC coefficients at mid-frequency (rows 2-4, cols 2-4)
                for r in range(1, 4):
                    for c in range(1, 4):
                        if r + c < 2:
                            continue
                        dct_tile[r, c] *= (1 + rng.uniform(-strength, strength))
                y[i:i+block, j:j+block] = cv2.idct(dct_tile)

        y = np.clip(y, 0, 255).astype(np.uint8)
        ycrcb[:, :, 0] = y
        result = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        writer.write(result)
        frame_idx += 1

        if progress_cb and frame_idx % 30 == 0:
            progress_cb(frame_idx / total)

    cap.release()
    writer.release()


def intensity_val(intensity: int, lo: float, hi: float) -> float:
    """Map intensity 1-100 linearly to [lo, hi]."""
    t = max(0.0, min(1.0, (intensity - 1) / 99.0))
    return lo + (hi - lo) * t


# ── Dispatcher ────────────────────────────────────────────────────────────────

OPENCV_BUILDERS = {
    54: apply_54_steganography,
    58: apply_58_hidden_pixels,
    63: apply_63_local_warp,
    64: apply_64_dct_modification,
}
