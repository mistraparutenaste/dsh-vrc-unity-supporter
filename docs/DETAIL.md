![Offline read of the hierarchy, a generated Editor script, and a verified result](preview.svg)

## What it does

- **Read the project** without opening Unity: avatars, scenes, prefabs, installed packages and missing references.
- **Outfit toggles**: make an outfit placed in the scene switchable from the Expression menu.
- **Color variants**: make outfit, skin, hair and eye color variants, or add a logo, from the avatar's layered PSDs, and switch them from the menu (uses [PhotoCraft](https://getartcraft.com/apps/photocraft)).
- **Verify**: check the generated menu and animations with VRChat SDK preprocessing; color variants are also rendered before and after in Unity.

## Safety

- It starts read-only, and shows the targets and the files it will create before any change.
- Changes go through Unity Editor scripts; scene and prefab YAML is never edited directly.
- Original PSDs, textures and materials are never overwritten, and every change can be reviewed and restored with Git.
- It never uploads.

## Requirements

Unity 2022.3.22f1 with an activated licence, VCC or ALCOM, a project with VRChat SDK - Avatars, Git, and Python 3.10 or later. Outfit toggles and color variants use VRCFury.
