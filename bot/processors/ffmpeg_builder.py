"""
Builds FFmpeg filter chains and output options for all FFmpeg-based methods.
OpenCV-based methods (54, 58, 63, 64) are handled separately.

Each build_* function receives:
    intensity (1-100) – controls parameter magnitude
    seed (int)        – for reproducible randomness within a run
    info (dict)       – video info: width, height, fps, duration, has_audio

Returns:
    vf_parts  (list[str]) – video filter fragments
    af_parts  (list[str]) – audio filter fragments
    out_opts  (dict)      – output encoding options (key→value)
"""
from __future__ import annotations

import math
import random
from typing import Any, Optional


# ── Intensity → magnitude helpers ─────────────────────────────────────────────

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def intensity_val(intensity: int, lo: float, hi: float) -> float:
    """Map intensity 1-100 linearly to [lo, hi]."""
    t = max(0.0, min(1.0, (intensity - 1) / 99.0))
    return lerp(lo, hi, t)

def rng(seed: int, method_id: int) -> random.Random:
    return random.Random(seed ^ (method_id * 0x9E3779B9))


def _perspective_no_black(w, h, x0, y0, x1, y1, x2, y2, x3, y3):
    """Build perspective filter + auto-crop + scale to remove black borders."""
    left = max(x0, x2)
    right = min(x1, x3)
    top = max(y0, y1)
    bottom = min(y2, y3)
    cw = right - left
    ch = bottom - top
    if cw <= 0 or ch <= 0:
        return (f"perspective=x0={x0}:y0={y0}:x1={x1}:y1={y1}"
                f":x2={x2}:y2={y2}:x3={x3}:y3={y3}:interpolation=linear")
    ar = w / h
    if cw / ch > ar:
        cw = int(ch * ar)
    else:
        ch = int(cw / ar)
    cw -= cw % 2
    ch -= ch % 2
    cx = left + (right - left - cw) // 2
    cy = top + (bottom - top - ch) // 2
    return (
        f"perspective=x0={x0}:y0={y0}:x1={x1}:y1={y1}"
        f":x2={x2}:y2={y2}:x3={x3}:y3={y3}:interpolation=linear,"
        f"crop={cw}:{ch}:{cx}:{cy},"
        f"scale={w}:{h}:flags=lanczos"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 1 – Geometric
# ══════════════════════════════════════════════════════════════════════════════

def build_1_hflip(intensity, seed, info):
    return ["hflip"], [], {}

def build_2_vflip(intensity, seed, info):
    return ["vflip"], [], {}

def build_3_rotate(intensity, seed, info):
    r = rng(seed, 3)
    max_angle = intensity_val(intensity, 0.3, 7)
    angle_deg = r.uniform(-max_angle, max_angle)
    angle_rad = math.radians(angle_deg)
    abs_rad = abs(angle_rad)
    w, h = info["width"], info["height"]
    cos_a, sin_a = math.cos(abs_rad), math.sin(abs_rad)
    zoom = max(
        (w * cos_a + h * sin_a) / w,
        (w * sin_a + h * cos_a) / h,
    )
    sw = int(math.ceil(w * zoom))
    sh = int(math.ceil(h * zoom))
    sw += sw % 2
    sh += sh % 2
    f = (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"rotate={angle_rad:.6f}:ow=iw:oh=ih:fillcolor=black,"
        f"crop={w}:{h}"
    )
    return [f], [], {}

def build_4_skew(intensity, seed, info):
    r = rng(seed, 4)
    max_deg = intensity_val(intensity, 0.2, 4)
    angle_rad = math.radians(r.uniform(-max_deg, max_deg))
    w, h = info["width"], info["height"]
    shift = int(h * math.tan(abs(angle_rad)))
    if r.random() < 0.5:
        x0, y0 = shift, 0
        x1, y1 = w - shift, 0
        x2, y2 = 0, h
        x3, y3 = w, h
    else:
        x0, y0 = 0, shift
        x1, y1 = w, 0
        x2, y2 = 0, h - shift
        x3, y3 = w, h
    f = _perspective_no_black(w, h, x0, y0, x1, y1, x2, y2, x3, y3)
    return [f], [], {}

def build_5_crop(intensity, seed, info):
    r = rng(seed, 5)
    pct = intensity_val(intensity, 0.003, 0.07)
    p = r.uniform(pct * 0.5, pct)
    w, h = info["width"], info["height"]
    cw = int(w * (1 - 2 * p))
    ch = int(h * (1 - 2 * p))
    f = f"crop={cw}:{ch}:{int(w*p)}:{int(h*p)},scale={w}:{h}:flags=lanczos"
    return [f], [], {}

def build_6_zoom(intensity, seed, info):
    r = rng(seed, 6)
    max_zoom = intensity_val(intensity, 0.005, 0.07)
    zoom = 1.0 + r.uniform(0, max_zoom)
    w, h = info["width"], info["height"]
    nw = int(w * zoom)
    nh = int(h * zoom)
    f = f"scale={nw}:{nh}:flags=lanczos,crop={w}:{h}:{(nw-w)//2}:{(nh-h)//2}"
    return [f], [], {}

def build_7_pan(intensity, seed, info):
    r = rng(seed, 7)
    max_pct = intensity_val(intensity, 0.003, 0.04)
    dx_pct = r.uniform(-max_pct, max_pct)
    dy_pct = r.uniform(-max_pct, max_pct)
    w, h = info["width"], info["height"]
    dx = int(w * dx_pct)
    dy = int(h * dy_pct)
    pad_w = w + abs(dx) * 2
    pad_h = h + abs(dy) * 2
    px = abs(dx) + dx
    py = abs(dy) + dy
    f = (f"pad={pad_w}:{pad_h}:{abs(dx)}:{abs(dy)}:black,"
         f"crop={w}:{h}:{px}:{py}")
    return [f], [], {}

def build_8_perspective(intensity, seed, info):
    r = rng(seed, 8)
    max_shift = int(intensity_val(intensity, 2, 25))
    w, h = info["width"], info["height"]
    shifts = [r.randint(0, max_shift) for _ in range(8)]
    x0, y0 = shifts[0], shifts[1]
    x1, y1 = w - shifts[2], shifts[3]
    x2, y2 = shifts[4], h - shifts[5]
    x3, y3 = w - shifts[6], h - shifts[7]
    f = _perspective_no_black(w, h, x0, y0, x1, y1, x2, y2, x3, y3)
    return [f], [], {}

def build_9_aspect_padding(intensity, seed, info):
    r = rng(seed, 9)
    pct = intensity_val(intensity, 0.005, 0.04)
    pad = int(info["height"] * r.uniform(pct * 0.5, pct))
    w, h = info["width"], info["height"]
    axis = r.choice(["h", "v"])
    if axis == "h":
        f = f"pad={w}:{h + pad * 2}:0:{pad}:black,scale={w}:{h}:flags=lanczos"
    else:
        f = f"pad={w + pad * 2}:{h}:{pad}:0:black,scale={w}:{h}:flags=lanczos"
    return [f], [], {}

def build_69_horizontal_parallax(intensity, seed, info):
    r = rng(seed, 69)
    max_shift = int(intensity_val(intensity, 2, 20))
    shift = r.randint(max(1, max_shift // 2), max(1, max_shift))
    w, h = info["width"], info["height"]
    if r.random() < 0.5:
        x0, y0 = 0, shift
        x1, y1 = w, 0
        x2, y2 = 0, h - shift
        x3, y3 = w, h
    else:
        x0, y0 = 0, 0
        x1, y1 = w, shift
        x2, y2 = 0, h
        x3, y3 = w, h - shift
    f = _perspective_no_black(w, h, x0, y0, x1, y1, x2, y2, x3, y3)
    return [f], [], {}

def build_70_vertical_parallax(intensity, seed, info):
    r = rng(seed, 70)
    max_shift = int(intensity_val(intensity, 2, 20))
    shift = r.randint(max(1, max_shift // 2), max(1, max_shift))
    w, h = info["width"], info["height"]
    if r.random() < 0.5:
        x0, y0 = 0, 0
        x1, y1 = w, 0
        x2, y2 = shift, h
        x3, y3 = w - shift, h
    else:
        x0, y0 = shift, 0
        x1, y1 = w - shift, 0
        x2, y2 = 0, h
        x3, y3 = w, h
    f = _perspective_no_black(w, h, x0, y0, x1, y1, x2, y2, x3, y3)
    return [f], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 2 – Color
# ══════════════════════════════════════════════════════════════════════════════

def build_10_brightness(intensity, seed, info):
    r = rng(seed, 10)
    max_delta = intensity_val(intensity, 0.02, 0.12)
    val = r.uniform(-max_delta, max_delta)
    return [f"eq=brightness={val:.4f}"], [], {}

def build_11_contrast(intensity, seed, info):
    r = rng(seed, 11)
    max_delta = intensity_val(intensity, 0.02, 0.10)
    base = 1.0 + r.uniform(-max_delta, max_delta)
    return [f"eq=contrast={base:.4f}"], [], {}

def build_12_saturation(intensity, seed, info):
    r = rng(seed, 12)
    max_delta = intensity_val(intensity, 0.03, 0.12)
    base = 1.0 + r.uniform(-max_delta, max_delta)
    return [f"eq=saturation={base:.4f}"], [], {}

def build_13_hue(intensity, seed, info):
    r = rng(seed, 13)
    max_deg = intensity_val(intensity, 0.5, 6)
    deg = r.uniform(-max_deg, max_deg)
    return [f"hue=h={deg:.2f}"], [], {}

def build_14_gamma(intensity, seed, info):
    r = rng(seed, 14)
    lo, hi = intensity_val(intensity, 0.95, 0.85), intensity_val(intensity, 1.05, 1.15)
    gamma = r.uniform(lo, hi)
    return [f"eq=gamma={gamma:.4f}"], [], {}

def build_15_temperature(intensity, seed, info):
    r = rng(seed, 15)
    max_shift = intensity_val(intensity, 200, 800)
    shift = r.uniform(-max_shift, max_shift)
    factor = shift / 5000.0
    rs = min(0.3, max(-0.3, factor))
    bs = min(0.3, max(-0.3, -factor))
    return [f"colorbalance=rs={rs:.4f}:gs=0:bs={bs:.4f}:rm=0:gm=0:bm=0:rh=0:gh=0:bh=0"], [], {}

def build_17_curves(intensity, seed, info):
    r = rng(seed, 17)
    amp = intensity_val(intensity, 0.01, 0.04)
    def rand_curve():
        mid_shift = r.uniform(-amp, amp)
        return f"0/0 0.5/{0.5 + mid_shift:.4f} 1/1"
    rc, gc, bc = rand_curve(), rand_curve(), rand_curve()
    return [f"curves=r='{rc}':g='{gc}':b='{bc}'"], [], {}

def build_19_vignette(intensity, seed, info):
    r = rng(seed, 19)
    angle = intensity_val(intensity, 0.1, 0.4)
    angle += r.uniform(-0.05, 0.05)
    return [f"vignette=angle={angle:.3f}:mode=forward"], [], {}

def build_20_chroma_noise(intensity, seed, info):
    r = rng(seed, 20)
    strength = max(3, int(intensity_val(intensity, 3, 15)))
    return [f"noise=c1s={strength}:c1f=t+u:c2s={strength}:c2f=t+u"], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 3 – Sharpness
# ══════════════════════════════════════════════════════════════════════════════

def build_21_sharpen(intensity, seed, info):
    la = intensity_val(intensity, 0.1, 0.7)
    return [f"unsharp=lx=5:ly=5:la={la:.2f}:cx=5:cy=5:ca=0"], [], {}

def build_23_unsharp(intensity, seed, info):
    r = rng(seed, 23)
    amount = intensity_val(intensity, 20, 100)
    radius = intensity_val(intensity, 0.3, 1.0)
    lx = max(3, int(radius * 2) | 1)
    la = amount / 100.0
    return [f"unsharp=lx={lx}:ly={lx}:la={la:.2f}"], [], {}

def build_24_selective_sharpen(intensity, seed, info):
    la = intensity_val(intensity, 0.1, 0.5)
    return [f"unsharp=lx=3:ly=3:la={la:.2f}:cx=3:cy=3:ca=0"], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 4 – Noise
# ══════════════════════════════════════════════════════════════════════════════

def build_27_film_grain(intensity, seed, info):
    strength = int(intensity_val(intensity, 1, 8))
    return [f"noise=alls={strength}:allf=t+p"], [], {}

def build_28_random_noise(intensity, seed, info):
    strength = max(3, int(intensity_val(intensity, 3, 12)))
    return [f"noise=alls={strength}:allf=t+u"], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 5 – Temporal
# ══════════════════════════════════════════════════════════════════════════════

def build_33_fps_change(intensity, seed, info):
    r = rng(seed, 33)
    orig_fps = info.get("fps", 30)
    max_delta = intensity_val(intensity, 1, 3)
    new_fps = orig_fps + r.uniform(-max_delta, max_delta)
    new_fps = max(10, round(new_fps, 2))
    return [], [], {"r": str(new_fps)}

def build_34_speed(intensity, seed, info):
    r = rng(seed, 34)
    max_delta = intensity_val(intensity, 0.02, 0.05)
    speed = 1.0 + r.uniform(-max_delta, max_delta)
    vf = f"setpts={1/speed:.4f}*PTS"
    af = f"atempo={speed:.4f}" if info.get("has_audio") else None
    return [vf], ([af] if af else []), {}

def build_37_trim_edges(intensity, seed, info):
    r = rng(seed, 37)
    max_ms = intensity_val(intensity, 50, 500)
    trim_start = r.uniform(0, max_ms) / 1000.0
    trim_end   = r.uniform(0, max_ms) / 1000.0
    duration   = info.get("duration", 0)
    if duration > 0:
        new_end = duration - trim_end
    else:
        new_end = None
    return [], [], {"ss": str(trim_start), "t": str(max(0, new_end - trim_start)) if new_end else ""}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 6 – Audio
# ══════════════════════════════════════════════════════════════════════════════

def build_41_eq(intensity, seed, info):
    if not info.get("has_audio"):
        return [], [], {}
    r = rng(seed, 41)
    max_gain = intensity_val(intensity, 1, 3)
    freqs = [80, 250, 1000, 4000, 12000]
    parts = []
    for freq in freqs:
        gain = r.uniform(-max_gain, max_gain)
        parts.append(f"equalizer=f={freq}:width_type=o:width=2:g={gain:.2f}")
    return [], [",".join(parts)], {}

def build_42_audio_noise(intensity, seed, info):
    if not info.get("has_audio"):
        return [], [], {}
    r = rng(seed, 42)
    max_delta = intensity_val(intensity, 0.001, 0.005)
    vol = 1.0 + r.uniform(-max_delta, max_delta)
    hp_freq = int(intensity_val(intensity, 15, 25))
    af = f"volume={vol:.6f},highpass=f={hp_freq}"
    return [], [af], {}

def build_44_audio_reencode(intensity, seed, info):
    if not info.get("has_audio"):
        return [], [], {}
    r = rng(seed, 44)
    codecs   = ["aac", "libmp3lame", "aac"]
    bitrates = [96, 128, 192]
    codec    = r.choice(codecs)
    bitrate  = r.choice(bitrates)
    return [], [], {"c:a": codec, "b:a": f"{bitrate}k"}

def build_45_stereo_pan(intensity, seed, info):
    if not info.get("has_audio"):
        return [], [], {}
    r = rng(seed, 45)
    max_pct = intensity_val(intensity, 0.03, 0.10)
    pan = r.uniform(-max_pct, max_pct)
    shift = pan
    af = f"pan=stereo|c0={1+shift:.4f}*c0+{shift:.4f}*c1|c1={shift:.4f}*c0+{1+shift:.4f}*c1"
    return [], [af], {}

def build_46_loudnorm(intensity, seed, info):
    if not info.get("has_audio"):
        return [], [], {}
    r = rng(seed, 46)
    target = -14 + r.uniform(-1, 1)
    return [], [f"loudnorm=I={target:.1f}:TP=-2:LRA=11"], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 7 – Encoding & Metadata
# ══════════════════════════════════════════════════════════════════════════════

def build_47_reencode(intensity, seed, info):
    r = rng(seed, 47)
    codecs = ["libx264", "libx265"] if not info.get("use_gpu") else ["h264_nvenc", "hevc_nvenc"]
    codec = r.choice(codecs)
    if "x265" in codec or "hevc" in codec:
        crf = 24
    else:
        crf = 18
    return [], [], {"c:v": codec, "crf": str(crf)}

def build_48_bitrate(intensity, seed, info):
    r = rng(seed, 48)
    orig_bitrate = info.get("video_bitrate", 0)
    if orig_bitrate < 500:
        return [], [], {}
    max_pct = intensity_val(intensity, 0.10, 0.25)
    factor = 1 + r.uniform(-max_pct, max_pct)
    new_bitrate = max(2000, int(orig_bitrate * factor))
    return [], [], {"b:v": f"{new_bitrate}k"}

def build_49_container(intensity, seed, info):
    r = rng(seed, 49)
    containers = ["mp4", "mkv"]
    return [], [], {"_container": r.choice(containers)}

def build_50_clear_metadata(intensity, seed, info):
    return [], [], {"map_metadata": "-1", "map_chapters": "-1"}

def build_51_new_metadata(intensity, seed, info):
    import uuid
    r = rng(seed, 51)

    IPHONE_MODELS = [
        "iPhone 12", "iPhone 12 Pro", "iPhone 12 Pro Max",
        "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max",
        "iPhone 14", "iPhone 14 Pro", "iPhone 14 Pro Max",
        "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max",
        "iPhone 16", "iPhone 16 Pro", "iPhone 16 Pro Max",
    ]
    IOS_VERSIONS = [
        "16.0", "16.1.2", "16.3", "16.5.1", "16.6",
        "17.0", "17.1.1", "17.2", "17.3.1", "17.4", "17.5.1",
        "18.0", "18.0.1", "18.1", "18.1.2", "18.2",
    ]
    CAPCUT_VERSIONS = [
        "3.5.0", "3.6.0", "3.7.0", "3.8.0", "3.9.0",
        "4.0.0", "4.1.0", "4.2.0", "4.3.0",
    ]
    GPS_LOCATIONS = [
        (40.7128, -74.0060), (51.5074, -0.1278), (48.8566, 2.3522),
        (35.6762, 139.6503), (55.7558, 37.6173), (52.5200, 13.4050),
        (41.9028, 12.4964), (37.7749, -122.4194), (34.0522, -118.2437),
        (43.6532, -79.3832), (25.2048, 55.2708), (1.3521, 103.8198),
        (39.9042, 116.4074), (-33.8688, 151.2093), (19.4326, -99.1332),
    ]
    TIMEZONES = [
        "+00:00", "+01:00", "+02:00", "+03:00", "+04:00",
        "+05:00", "+05:30", "+08:00", "+09:00", "+10:00",
        "-05:00", "-06:00", "-07:00", "-08:00",
    ]

    year = r.randint(2022, 2025)
    month = r.randint(1, 12)
    day = r.randint(1, 28)
    hour = r.randint(6, 22)
    minute = r.randint(0, 59)
    second = r.randint(0, 59)
    tz = r.choice(TIMEZONES)
    timestamp = f"{year}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}{tz}"

    device_type = r.choice(["iphone", "iphone", "iphone", "capcut"])

    opts = {}

    if device_type == "iphone":
        model = r.choice(IPHONE_MODELS)
        ios_ver = r.choice(IOS_VERSIONS)
        img_num = r.randint(1000, 9999)
        lat, lon = r.choice(GPS_LOCATIONS)
        lat += r.uniform(-0.01, 0.01)
        lon += r.uniform(-0.01, 0.01)

        opts["metadata:g:0"] = f"title=IMG_{img_num}"
        opts["metadata:g:1"] = f"artist="
        opts["metadata:g:2"] = f"creation_time={timestamp}"
        opts["metadata:g:3"] = f"com.apple.quicktime.make=Apple"
        opts["metadata:g:4"] = f"com.apple.quicktime.model={model}"
        opts["metadata:g:5"] = f"com.apple.quicktime.software={ios_ver}"
        opts["metadata:g:6"] = f"com.apple.quicktime.creationdate={timestamp}"
        opts["metadata:g:7"] = f"make=Apple"
        opts["metadata:g:8"] = f"model={model}"
        opts["metadata:g:9"] = f"date={year}-{month:02d}-{day:02d}"
        opts["metadata:g:10"] = f"location={lat:+.4f}{lon:+.4f}/"
        opts["metadata:g:11"] = f"com.apple.quicktime.location.ISO6709={lat:+.4f}{lon:+.4f}/"
        opts["metadata:s:v:0"] = f"handler_name=Core Media Video"
        if info.get("has_audio"):
            opts["metadata:s:a:0"] = f"handler_name=Core Media Audio"
    else:
        capcut_ver = r.choice(CAPCUT_VERSIONS)
        project_id = r.randint(100000, 999999)
        opts["metadata:g:0"] = f"title=CapCut Export {project_id}"
        opts["metadata:g:1"] = f"comment=Made with CapCut"
        opts["metadata:g:2"] = f"creation_time={timestamp}"
        opts["metadata:g:3"] = f"encoder=CapCut {capcut_ver}"
        opts["metadata:g:4"] = f"date={year}-{month:02d}-{day:02d}"
        opts["metadata:s:v:0"] = f"handler_name=VideoHandler"

    return [], [], opts

def build_52_gop(intensity, seed, info):
    r = rng(seed, 52)
    gop = int(intensity_val(intensity, 25, 90))
    gop += r.randint(-5, 5)
    return [], [], {"g": str(max(10, gop))}

def build_53_pixel_format(intensity, seed, info):
    r = rng(seed, 53)
    fmts = ["yuv420p", "yuv422p", "yuv444p"]
    fmt = r.choice(fmts)
    return [], [], {"pix_fmt": fmt}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 8 – Overlays
# ══════════════════════════════════════════════════════════════════════════════

def build_55_watermark(intensity, seed, info):
    import uuid
    r = rng(seed, 55)
    alpha = intensity_val(intensity, 0.03, 0.08)
    text  = str(uuid.UUID(int=r.getrandbits(128)))[:8]
    w, h  = info["width"], info["height"]
    x     = r.randint(5, w // 3)
    y     = r.randint(5, h // 3)
    f = (f"drawtext=text='{text}':x={x}:y={y}:fontsize=14"
         f":fontcolor=white@{alpha:.3f}")
    return [f], [], {}

def build_59_light_vignette(intensity, seed, info):
    r = rng(seed, 59)
    angle = intensity_val(intensity, 0.15, 0.4)
    angle += r.uniform(-0.03, 0.03)
    return [f"vignette=angle={angle:.3f}:mode=forward"], [], {}

def build_60_subpixel_shift(intensity, seed, info):
    r = rng(seed, 60)
    w, h = info["width"], info["height"]
    amount = max(1, round(intensity_val(intensity, 0.5, 3)))
    side = r.randint(0, 3)
    if side == 0:
        f = f"crop={w-amount}:{h}:{amount}:0,scale={w}:{h}:flags=lanczos"
    elif side == 1:
        f = f"crop={w-amount}:{h}:0:0,scale={w}:{h}:flags=lanczos"
    elif side == 2:
        f = f"crop={w}:{h-amount}:0:{amount},scale={w}:{h}:flags=lanczos"
    else:
        f = f"crop={w}:{h-amount}:0:0,scale={w}:{h}:flags=lanczos"
    return [f], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 9 – Advanced
# ══════════════════════════════════════════════════════════════════════════════

def build_61_seed(intensity, seed, info):
    r = rng(seed, 61)
    tag = f"uid_{r.getrandbits(64):016x}"
    return [], [], {f"metadata:g:99": f"comment={tag}"}

def build_62_interpolation(intensity, seed, info):
    r = rng(seed, 62)
    flags = r.choice(["lanczos", "bicubic", "bilinear"])
    w, h = info["width"], info["height"]
    f = f"scale={w-1}:{h-1}:flags={flags},scale={w}:{h}:flags={flags}"
    return [f], [], {}


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCH TABLE
# ══════════════════════════════════════════════════════════════════════════════

BUILDERS: dict[int, Any] = {
    1:  build_1_hflip,
    2:  build_2_vflip,
    3:  build_3_rotate,
    4:  build_4_skew,
    5:  build_5_crop,
    6:  build_6_zoom,
    7:  build_7_pan,
    8:  build_8_perspective,
    9:  build_9_aspect_padding,
    69: build_69_horizontal_parallax,
    70: build_70_vertical_parallax,
    10: build_10_brightness,
    11: build_11_contrast,
    12: build_12_saturation,
    13: build_13_hue,
    14: build_14_gamma,
    15: build_15_temperature,
    17: build_17_curves,
    19: build_19_vignette,
    20: build_20_chroma_noise,
    21: build_21_sharpen,
    23: build_23_unsharp,
    24: build_24_selective_sharpen,
    27: build_27_film_grain,
    28: build_28_random_noise,
    33: build_33_fps_change,
    34: build_34_speed,
    37: build_37_trim_edges,
    41: build_41_eq,
    42: build_42_audio_noise,
    44: build_44_audio_reencode,
    45: build_45_stereo_pan,
    46: build_46_loudnorm,
    47: build_47_reencode,
    48: build_48_bitrate,
    49: build_49_container,
    50: build_50_clear_metadata,
    51: build_51_new_metadata,
    52: build_52_gop,
    53: build_53_pixel_format,
    # 54: opencv
    55: build_55_watermark,
    # 58: opencv
    59: build_59_light_vignette,
    60: build_60_subpixel_shift,
    61: build_61_seed,
    62: build_62_interpolation,
    # 63: opencv
    # 64: opencv
}

# Methods handled by OpenCV pipeline (not FFmpeg)
OPENCV_METHODS = {54, 58, 63, 64}
