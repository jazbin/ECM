#!/usr/bin/env python3
import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple, BinaryIO

MAGIC = b"ECMIOv1\x00"
HEADER_FMT_V1 = "<8sIIIddII"   # magic, fileType, version, N, time, deltaT, keyMode, nInputs
HEADER_FMT_V2 = "<8sIIIddIIQ"  # v1 + stepId
HEADER_SIZE_V1 = struct.calcsize(HEADER_FMT_V1)  # 44 bytes
HEADER_SIZE_V2 = struct.calcsize(HEADER_FMT_V2)  # 52 bytes

@dataclass
class Header:
    magic: bytes
    fileType: int
    version: int
    N: int
    time: float
    deltaT: float
    keyMode: int
    nInputs: int
    stepId: int = 0

def read_header(f: BinaryIO) -> Header:
    data = f.read(HEADER_SIZE_V1)
    if len(data) != HEADER_SIZE_V1:
        raise ValueError("Truncated header")
    magic, fileType, version, N, time, deltaT, keyMode, nInputs = struct.unpack(HEADER_FMT_V1, data)
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r}")
    if version not in (1, 2):
        raise ValueError(f"Unsupported version: {version}")
    stepId = 0
    if version >= 2:
        data2 = f.read(8)
        if len(data2) != 8:
            raise ValueError("Truncated header (stepId)")
        (stepId,) = struct.unpack("<Q", data2)
    return Header(magic, fileType, version, N, time, deltaT, keyMode, nInputs, stepId)

def write_header(f: BinaryIO, h: Header) -> None:
    version = int(h.version)
    if version >= 2:
        data = struct.pack(
            HEADER_FMT_V2,
            MAGIC,
            int(h.fileType),
            2,
            int(h.N),
            float(h.time),
            float(h.deltaT),
            int(h.keyMode),
            int(h.nInputs),
            int(h.stepId),
        )
        f.write(data)
    else:
        data = struct.pack(
            HEADER_FMT_V1,
            MAGIC,
            int(h.fileType),
            1,
            int(h.N),
            float(h.time),
            float(h.deltaT),
            int(h.keyMode),
            int(h.nInputs),
        )
        f.write(data)

def read_inputs(f: BinaryIO, nInputs: int) -> Dict[str, float]:
    inputs: Dict[str, float] = {}
    for _ in range(nInputs):
        (nameLen,) = struct.unpack("<I", f.read(4))
        name = f.read(nameLen).decode("utf-8")
        (val,) = struct.unpack("<d", f.read(8))
        inputs[name] = val
    return inputs

def write_inputs(f: BinaryIO, inputs: Dict[str, float]) -> None:
    for name, val in inputs.items():
        name_b = name.encode("utf-8")
        f.write(struct.pack("<I", len(name_b)))
        f.write(name_b)
        f.write(struct.pack("<d", float(val)))

def read_records_T(f: BinaryIO, N: int) -> Tuple[List[int], List[float]]:
    keys: List[int] = []
    temps: List[float] = []
    rec_fmt = "<id"  # int32 key, double T
    rec_size = struct.calcsize(rec_fmt)
    for _ in range(N):
        data = f.read(rec_size)
        if len(data) != rec_size:
            raise ValueError("Truncated input records")
        k, T = struct.unpack(rec_fmt, data)
        keys.append(int(k))
        temps.append(float(T))
    return keys, temps

def read_records_q(f: BinaryIO, N: int) -> Tuple[List[int], List[float]]:
    keys: List[int] = []
    q: List[float] = []
    rec_fmt = "<id"  # int32 key, double qVol
    rec_size = struct.calcsize(rec_fmt)
    for _ in range(N):
        data = f.read(rec_size)
        if len(data) != rec_size:
            raise ValueError("Truncated output records")
        k, qq = struct.unpack(rec_fmt, data)
        keys.append(int(k))
        q.append(float(qq))
    return keys, q

def write_records(f: BinaryIO, keys: List[int], vals: List[float]) -> None:
    if len(keys) != len(vals):
        raise ValueError("keys/vals length mismatch")
    for k, v in zip(keys, vals):
        f.write(struct.pack("<i", int(k)))
        f.write(struct.pack("<d", float(v)))
