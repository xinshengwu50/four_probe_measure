# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 兰新宇, 吴新胜, 孙毅泽
# See LICENSE and NOTICE in the repository root.

"""42-byte enum-current/structure frame; backwards compatible33AUTO/37legacy."""
NEW_FRAME_LENGTH=33
LEGACY_FRAME_LENGTH=37
STRUCTURED_FRAME_LENGTH=42

# Fixed markers bound every binary field to four bytes. Reject an impossible
# prefix immediately, including when a truncated START is followed by RST.
_CONFIG_MARKERS = (
    ((0,0xAA),(1,0xBB),(6,0xCC),(11,0xDD),(16,0xEE),
     (17,0xFF),(22,0x66),(27,0x77),(32,0xAA)),
    ((0,0xAA),(1,0xBB),(6,0xCC),(11,0xDD),(16,0xEE),
     (21,0xFF),(26,0x66),(31,0x77),(36,0xAA)),
    ((0,0xAA),(1,0xBB),(6,0xCC),(11,0xDD),(16,0xEE),
     (21,0xFF),(26,0x66),(31,0x77),(36,0x88),(41,0xAA)),
)

def config_frame_length(data):
    if not any(all(position >= len(data) or data[position] == marker
                   for position, marker in markers) for markers in _CONFIG_MARKERS):
        return 0
    if len(data)<17:return None
    if data[0]!=0xAA or any(data[p]!=v for p,v in [(1,0xBB),(6,0xCC),(11,0xDD),(16,0xEE)]):return 0
    if len(data)<23:return None
    if data[17]==0xFF and data[22]==0x66:return NEW_FRAME_LENGTH
    if data[21]!=0xFF:return 0
    # The first37 bytes alone distinguish legacyAA tail from new88 field.
    if len(data)<37:return None
    if data[36]==0x88:return STRUCTURED_FRAME_LENGTH
    if data[36]==0xAA:return LEGACY_FRAME_LENGTH
    return 0

def split_config_frame(frame):
    data=bytes(frame)
    if len(data) not in (33,37,42) or data[0]!=0xAA:raise ValueError('expected33/37/42-byte config frame')
    fields={};position=1
    markers=(0xBB,0xCC,0xDD,0xEE,0xFF,0x66,0x77)+((0x88,) if len(data)==42 else ())
    for marker in markers:
        size=0 if marker==0xEE and len(data)==33 else 4
        if position+1+size>len(data) or data[position]!=marker:raise ValueError('invalid marker0x%02X'%marker)
        fields[marker]=data[position+1:position+1+size];position+=1+size
    if position!=len(data)-1 or data[position]!=0xAA:raise ValueError('invalid frame tail')
    return fields
