![Offline read of the hierarchy, a generated Editor script, and a verified result](preview.svg)

## What it does

- **Read the project** without opening Unity: avatars, scenes, prefabs, installed packages and missing references.
- **Outfit toggles**: make an outfit placed in the scene switchable from the Expression menu.
- **Color variants**: make outfit, skin, hair and eye color variants, or add a logo, from the avatar's layered PSDs, and switch them from the menu (uses [PhotoCraft](https://getartcraft.com/apps/photocraft)).
- **lilToon adjustments**: without a PSD, make copies of lilToon materials with changed values (main color, color correction, shadows, outline, emission, rim light) and switch them from the menu.
- **Body shape**: change blendshapes, make outfits follow the body, and remove body parts hidden under clothes at build time, without editing the FBX.
- **Accessories**: attach hats, hair, accessories or outfits to a bone or merge their armature, switch them from the menu, and hide the original hair while they are on.
- **Blender**: make accessories (bands, strings, turned and flat shapes, mirrored pairs, rested against the head or hair, with sway bones and a PhysBone). Hair and outfits made for another avatar are fitted to this avatar's skeleton and to the body-shape difference from the avatar they were made for, get the avatar's body shape keys, and are then attached, made to follow the body, and the body hidden underneath removed (uses [Blender](https://www.blender.org/)).
- **Expressions**: replace hand-gesture expressions, pick and keep an expression from the menu, and add toggles such as a blush, by adding a layer without changing the avatar's animators.
- **Held props**: have the avatar hold a prop and leave it in place with "Put down" in the menu, or fix a prop in the world.
- **Avatar updates**: apply the changes made with this plugin again to a new version of the avatar, and list the values changed by hand.
- **Swinging parts**: change PhysBone values of hair, skirts and tails (how they swing, whether they can be grabbed or posed), and add colliders on the legs or body so they do not pass through.
- **View position and sizes**: put the view position between the eyes again, and make the head, hands or other single bones bigger or smaller.
- **Menu tidying**: list the menu as built (with the items VRCFury and Modular Avatar add) and move, rename, reorder or set icons on its items without changing the author's menus (uses VRCFury).
- **Polygon reduction**: reduce triangles at build time with [Meshia](https://github.com/RamType0/Meshia.MeshSimplification), without changing the FBX. The face and small meshes are kept.
- **Quest (Android) version**: make the Android version from the same scene with [VRCQuestTools](https://github.com/kurotu/VRCQuestTools) (mobile shaders, smaller textures, fewer PhysBones), measured as an Android build. The PC version does not change.
- **Parameter memory**: count the synced parameters (256-bit limit) as built, and show what is left before a toggle is added.
- **Try-and-adjust loops**: turn requests such as "swing more softly" into a measurable goal, try and adjust without saving, and show the result before applying.
- **PhysBone simulation**: run the avatar in play mode while it sways, walks and sits, and measure each swinging part's swing, settling time and depth into the legs; recipes can be tried in memory and compared.
- **Playback test**: drive the built avatar with gestures and menu items and check that expressions and toggles work (in place of Gesture Manager).
- **Verify**: check the generated menu and animations with VRChat SDK preprocessing; color variants are also rendered before and after in Unity.

## Safety

- It starts read-only, and shows the targets and the files it will create before any change.
- Changes go through Unity Editor scripts; scene and prefab YAML is never edited directly.
- Original PSDs, textures, materials, FBX and prefabs are never overwritten, and every change can be reviewed and restored with Git.
- It never uploads.

## Requirements

Unity 2022.3.22f1 with an activated licence, VCC or ALCOM, a project with VRChat SDK - Avatars, Git, and Python 3.10 or later. Outfit toggles and color variants use VRCFury.
