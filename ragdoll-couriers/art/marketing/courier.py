"""The courier: a chunky blocky figure for thumbnails and the game icon (players use their own avatars
in game). Every limb is its own object with its origin at the joint, so poses are just rotations."""

import math

import bpy
from mathutils import Euler

from lib import Mesh

# joint -> (position relative to the hips, colour) ; limbs hang down from their joint
POSES = {
    # rotations in degrees (x, y, z) per joint; root is the whole body. +Y swings an arm out to -X: left arms
    # (at -X) take +Y, right arms -Y, or they cross the face
    "ride": {"l_arm": (-75, 0, 8), "r_arm": (-75, 0, -8), "l_leg": (-85, 0, 6), "r_leg": (-85, 0, -6), "head": (-5, 0, 0), "torso": (12, 0, 0)},
    "fly": {"l_arm": (-20, 140, 0), "r_arm": (30, -130, 0), "l_leg": (35, -28, 0), "r_leg": (-60, 22, 0), "head": (25, 0, 15), "torso": (-15, 10, 0)},
    "tumble": {"l_arm": (-160, 40, 0), "r_arm": (60, -100, 0), "l_leg": (-30, -40, 0), "r_leg": (70, 30, 0), "head": (-20, 20, 0), "torso": (20, 0, -10)},
    "wave": {"l_arm": (0, 0, 0), "r_arm": (0, 160, 0), "l_leg": (0, 0, 0), "r_leg": (0, 0, 0), "head": (0, 0, 10), "torso": (0, 0, 0)},
}


def _part(name, builder, loc, parent):
    m = Mesh(name)
    builder(m)
    obj = m.done(sharp=35)
    obj.location = loc
    obj.parent = parent
    return obj


def courier(pose="fly", location=(0, 0, 0), rotation=(0, 0, 0), shirt="orange", scale=1.0, face=None, hair=None):
    face = face or ("smile" if pose in ("ride", "wave") else "shock")
    """Builds a posed courier. Returns the root empty (move/rotate it) and the list of mesh objects."""
    root = bpy.data.objects.new("Courier", None)
    root.location = location
    root.rotation_euler = Euler([math.radians(a) for a in rotation])
    root.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(root)
    p = POSES[pose]

    def torso(m):
        m.box((2, 1, 2), (0, 0, 1), shirt, bevel=0.2)
        m.box((2.04, 1.04, 0.35), (0, 0, 0.2), "navy", bevel=0.1)  # belt line
        m.box((0.5, 1.06, 2.0), (0.35, 0, 1.05), "navy", rot=(0, 35, 0), bevel=0.05)  # satchel strap
        m.box((1.0, 0.5, 0.8), (-0.75, 0.6, 0.35), "yellow", bevel=0.15)  # satchel
        m.box((0.6, 0.06, 0.4), (0.5, 0.52, 1.5), "white", bevel=0.03)  # badge

    def head(m):
        m.box((1.25, 1.2, 1.2), (0, 0, 0.6), "skin", bevel=0.3, segments=3)
        if face == "shock":  # the thumbnail face: wide eyes, brows up, mouth open (reads at phone size)
            for sx in (-1, 1):
                m.sphere(0.2, (sx * 0.28, 0.6, 0.74), "white", scale=(1, 0.5, 1.15), segments=12, rings=8)
                m.sphere(0.09, (sx * 0.26, 0.69, 0.74), "black", segments=8, rings=6)
                m.box((0.34, 0.08, 0.09), (sx * 0.3, 0.62, 1.02), "darkbrown", rot=(0, sx * -18, 0), bevel=0.03)
            m.sphere(0.2, (0, 0.6, 0.34), "darkbrown", scale=(1.1, 0.4, 0.9), segments=12, rings=8)
            m.sphere(0.12, (0, 0.65, 0.27), "red", scale=(1.2, 0.4, 0.6), segments=10, rings=6)  # tongue
        elif face == "smile":  # face="none" leaves the head blank for a painted face decal (marketing/build_poster_icon.py)
            for sx in (-1, 1):
                m.sphere(0.11, (sx * 0.27, 0.6, 0.72), "black", segments=8, rings=6)  # eyes
            m.box((0.45, 0.05, 0.1), (0, 0.61, 0.38), "darkbrown", bevel=0.03)  # smile
        if hair == "bacon":  # messy ginger default-avatar hair: what front-page players read as "me"
            m.box((1.38, 1.32, 0.4), (0, -0.02, 1.28), "ginger", bevel=0.17)  # crown
            m.box((1.36, 0.35, 1.0), (0, -0.5, 0.85), "ginger", bevel=0.15)  # back
            for sx in (-1, 1):
                m.box((0.16, 1.0, 0.55), (sx * 0.66, -0.05, 1.0), "ginger", bevel=0.07)  # sides
            for k, x in enumerate((-0.5, -0.2, 0.1, 0.4)):  # fringe locks swept across the forehead
                m.sphere(0.24, (x, 0.5, 1.36 - k * 0.03), "ginger", scale=(0.8, 0.7, 1.7), rot=(25, -40, 0), segments=10, rings=6)
            for k, (x, y) in enumerate(((-0.35, 0.1), (0.15, -0.15), (0.45, 0.25), (-0.1, 0.35))):  # spiky top
                m.sphere(0.22, (x, y, 1.5), "ginger", scale=(0.8, 0.8, 1.9), rot=(15 - k * 10, -35 + k * 15, 0), segments=8, rings=5)
        else:
            m.box((1.35, 1.3, 0.45), (0, 0, 1.32), "red", bevel=0.18)  # cap
            m.box((1.1, 0.7, 0.12), (0, 0.85, 1.12), "red", bevel=0.05)  # brim
            m.box((0.5, 0.06, 0.3), (0, 0.66, 1.35), "white", bevel=0.02)  # cap badge

    def arm(m):
        m.box((0.9, 0.9, 1.4), (0, 0, -0.7), shirt, bevel=0.2)
        m.box((0.85, 0.85, 0.7), (0, 0, -1.65), "skin", bevel=0.25)  # hand

    def leg(m):
        m.box((0.95, 0.95, 1.6), (0, 0, -0.8), "navy", bevel=0.15)
        m.box((1.0, 1.25, 0.45), (0, 0.12, -1.8), "charcoal", bevel=0.15)  # shoe

    t = _part("C_Torso", torso, (0, 0, 2.0), root)
    t.rotation_euler = Euler([math.radians(a) for a in p["torso"]])
    parts = [t]
    for name, builder, loc in (("C_Head", head, (0, 0, 2.05)), ("C_LArm", arm, (-1.45, 0, 1.9)), ("C_RArm", arm, (1.45, 0, 1.9))):
        o = _part(name, builder, loc, t)  # head and arms ride on the torso
        key = {"C_Head": "head", "C_LArm": "l_arm", "C_RArm": "r_arm"}[name]
        o.rotation_euler = Euler([math.radians(a) for a in p[key]])
        parts.append(o)
    for name, key, x in (("C_LLeg", "l_leg", -0.5), ("C_RLeg", "r_leg", 0.5)):
        o = _part(name, leg, (x, 0, 2.0), root)
        o.rotation_euler = Euler([math.radians(a) for a in p[key]])
        parts.append(o)
    return root, parts
