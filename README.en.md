# dsh-vrc-unity-supporter

[日本語](README.md) | English | [简体中文](README.zh-CN.md) | [한국어](README.ko.md)

This plugin lets you modify VRChat avatars with an AI agent.

The agent answers in Japanese unless you write to it in another language. Write in English and it answers in English.

## Installation

### Let the AI agent do it (recommended)

Paste the following message into the chat of DSH, Claude Code or Codex and send it. The agent walks you through checking what is missing, installing the plugin and the first check, in order.

```text
I want to use a plugin called "dsh-vrc-unity-supporter" to modify VRChat avatars.
On my Windows PC, please help me from installation to the first check, in this order.
Go one step at a time, and wait whenever I need to do something myself.

1. Check with commands whether these are installed:
   Git / Python 3.10 or later / Unity Hub and Unity 2022.3.22f1 / VCC or ALCOM
   For anything missing, show me the official download page and wait for me to install it.
   Do not install anything yourself.
2. Find out whether the app I am using is DeepSeek Harness, Claude Code or Codex, and install the plugin.
   - For Claude Code (including the desktop app):
     Ask me before running these two commands in PowerShell, then run them.
       claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
       claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
     If the claude command is not found, show me the Windows steps at
     https://code.claude.com/docs/en/setup and wait for me to install it.
   - For Codex:
     Ask me before running this command in PowerShell, then run it.
       codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
     Then guide me through installing "VRChat Avatar (Unity)" from Plugins in the Codex app.
     If the codex command is not found, show me the steps at https://developers.openai.com/codex/
     and wait for me to install it.
   - For DeepSeek Harness:
     Guide me through adding "dsh-vrc-unity-supporter" in Plugins → Add plugin.
3. Ask me for the folder of the Unity project I want to modify (the folder that has Assets and ProjectSettings).
4. Finally, tell me to start a new session in that folder and send this sentence:
   "Look into the avatars in this project"

Do not change any files in the Unity project until then.

GitHub repository URL: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/tree/master
```

The plugin works in new sessions started after you install it.

### Install in DSH

1. Open DSH and choose **Plugins** → **Add plugin**.
2. Paste the following package name into the field and install it.

   ```text
   dsh-vrc-unity-supporter
   ```

3. Create a **new session** and check that **VRChat Avatar** appears in the list of presets.

<details>
<summary>Installing from a ZIP</summary>

1. On this GitHub page, choose **Code** → **Download ZIP**.
2. Right-click the downloaded ZIP and choose **Extract All**.
3. Quit DSH, then double-click **`install.cmd`** in the extracted folder.
4. When it says it has finished, restart DSH and choose **VRChat Avatar** in a **new session**.

`install.cmd` uses the command bundled with DSH to download the published version from npm and install it. Stay connected to the internet while it installs. [Installer details and uninstalling (Japanese)](installer/README.md)

</details>

### Install in Claude Code

Claude Code works both in the **Code tab of the Claude desktop app** and in the terminal.

**If you use the desktop app**

1. Open PowerShell and run these two commands in order.

   ```powershell
   claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   ```powershell
   claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
   ```

   If it says `claude` is not found, install the `claude` command with the Windows steps in [Claude Code setup](https://code.claude.com/docs/en/setup), then run them again.
2. In the **Code** tab of the desktop app, choose your Unity project folder and start a new session.
3. Check that `dsh-vrc-unity-supporter` appears and is enabled under **+** next to the prompt box → **Plugins** → **Manage plugins**.

**If you use the terminal**

Open Claude Code in your Unity project folder and run these in order.

```text
/plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
/plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
```

After installing, run `/reload-plugins` or start a new session.

### Install in Codex

1. Open PowerShell and run this to add the marketplace.

   ```powershell
   codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   If it says `codex` is not found, install the `codex` command with the steps in the [Codex documentation](https://developers.openai.com/codex/), then run it again.
2. Reopen the Codex app, choose the `dsh-vrc-unity-supporter` marketplace in **Plugins**, and install **VRChat Avatar (Unity)**.
3. Start a new thread in your Unity project folder.

In Codex, the skills' commands run inside a sandbox. When it runs Unity or Blender, Codex may ask whether it may run them outside the sandbox. Check what it is going to run before you approve.

### Requirements

If you let the AI agent install the plugin, it checks these for you. To prepare them yourself, set up the following on Windows.

| Requirement | What to do |
| --- | --- |
| **DeepSeek Harness Desktop, Claude Code or Codex** | For DSH, install it from **Download Desktop → Windows (64-bit)** on the official site and finish the first-time setup on screen. For Claude Code, use the desktop app or the terminal version. For Codex, use the app and the `codex` command. [DSH official site](https://www.deepseek.com/en/harness/) · [Claude Code overview](https://code.claude.com/docs/en/overview) · [Codex documentation](https://developers.openai.com/codex/) |
| **Git for Windows** | Used to record the state before a change so you can go back later. The records stay on your PC. [Download Git](https://git-scm.com/install/win) |
| **Python 3.10 or later** | Used to read the structure of your avatars. After installing it, reopen the app you use (DSH, Claude Code or Codex). [Download Python for Windows](https://www.python.org/downloads/windows/) |
| **Unity Hub and Unity 2022.3.22f1** | Set up a valid license in Unity Hub and check that your project opens with this version. [VRChat's guide to installing Unity](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) |
| **VCC or ALCOM and an avatar project** | Use whichever project manager you normally use. The project you work on must have **VRChat SDK - Avatars** and open in Unity. [VCC setup](https://vcc.docs.vrchat.com/guides/getting-started/) · [Download ALCOM](https://vrc-get.anatawa12.com/alcom/) |

Some features need more (VRCFury, Modular Avatar, Avatar Optimizer, PhotoCraft, Blender). See the table in [What it can do](#what-it-can-do).

## Try it

1. Open the folder of the Unity project you want to modify: the folder that has `Assets`, `Packages` and `ProjectSettings`. Open it as the workspace in DSH, or as the working folder in Claude Code and Codex.
2. In DSH, set the new session's preset to **VRChat Avatar**, the model to **DeepSeek V4.1 Flash** and the effort to **MAX**. In Claude Code, just start a new session; in Codex, a new thread.
3. Send this sentence in the chat. At this stage it only reads the project's files.

   ```text
   Look into the avatars in this project
   ```

4. Once you see your avatars and outfits, ask for a change, replacing the outfit name with one from your project. Before it applies anything, save the scene and close Unity.

   ```text
   Let me switch Outfit_Hoodie on and off from "Outfit/Hoodie". Start with it on
   ```

5. The agent shows what it will change. Check it, then ask it to apply. If the outfit name is unclear, it lists candidates from the saved scene and asks you.
6. After applying, it shows whether the scene was saved and whether the SDK build preprocessing confirmed the menu and animation. To try it inside VRChat, choose **VRChat SDK → Show Control Panel → Builder → Offline Testing → Build & Test** in Unity. In VRChat, pick the test avatar under **SDK Test Avatars** and switch the outfit on and off from the menu. [VRChat's local testing guide](https://creators.vrchat.com/avatars/#local-avatar-testing)

## What it can do

| Feature | Example request | Also needs |
| --- | --- | --- |
| Look into the avatars | "Look into the avatars in this project" | Nothing |
| Switch outfits from the menu | "Let me switch Outfit_Hoodie on and off from 'Outfit/Hoodie'" | VRCFury |
| Make color variants | "Make a navy color variant of the hoodie" | PhotoCraft, the avatar's PSD |
| Adjust lilToon colors, shadows and outlines | "Make the hair shadows lighter and the outline thinner" | VRCFury, lilToon or Poiyomi materials |
| Adjust body shape and fix clipping | "Remove the body under the clothes and make the chest a little bigger" | Modular Avatar, Avatar Optimizer |
| Attach accessories, hair and outfits | "Attach this wolf-cut hair" | Modular Avatar |
| Make things in Blender, wear unsupported outfits | "Put this coat made for Selestia on Salt" | Blender, Modular Avatar |
| Adjust swinging parts | "Make the back hair swing more softly, and stop people grabbing the tail" | Nothing |
| Change the view position and single sizes | "The view is too low, fix it. Make the head a little bigger" | Modular Avatar, to change only a hand or the chest |
| Change expressions | "Make the right fist a smile, and let me pick a half-closed-eye look from the menu" | Modular Avatar |
| Carry changes over to an updated avatar | "I updated Salt to the new version; carry my changes over" | Nothing (beyond what each change needs) |
| Check the performance rank and parameter memory | "Check the performance rank", "How many parameter bits are left?" | Nothing |

Add VRCFury, Modular Avatar and Avatar Optimizer to your project with VCC or ALCOM. [Installing VRCFury](https://vrcfury.com/download/)

### Switch outfits from the menu

Lets you switch an outfit placed in the scene on and off from the VRChat menu. Place the avatar and the outfit in the same scene and save it first.

```text
Let me switch Outfit_Hoodie on and off from "Outfit/Hoodie". Start with it on
```

- **Wear only one**: ask "Let me switch between the hoodie and the coat so that only one is worn at a time", and the toggles go into the same group. Turning one on turns the other off.
- **List and remove**: check the toggles you made with "List the outfit toggles". Ask "Remove the hoodie toggle" to remove only that toggle (the outfit itself stays).

### Make color variants

Makes color variants from the layered PSD that comes with an avatar or outfit. You can change the colors of outfits, skin, hair and eyes, or add a logo or pattern you prepared. The original PSD, textures and materials stay as they are; a variant is added as a separate material. You can switch between it and the original look from the menu.

```text
Make a navy color variant of the hoodie. The PSD is in Downloads\Salt_v1.0.1
```

The agent reads the PSD's layers and shows which layers it will change and how before it renders them. Then it captures the avatar in Unity and checks before/after images side by side. Check your variants with "List the color variants", and remove one with "Delete the Hoodie_Blue color variant".

- Install the free image editor **PhotoCraft**. PSDs are edited from the command line, so you never have to open its window. [Download PhotoCraft](https://getartcraft.com/apps/photocraft) · [Detailed guide (Japanese)](docs/PHOTOCRAFT.md)
- Many avatars' terms of use forbid distributing textures made from their PSDs. Use them only inside your project.

### Adjust lilToon colors, shadows and outlines

Even for outfits and hair without a PSD, you can adjust the look through lilToon material values (Poiyomi Toon 9 and 10 materials that are not locked work too): main color and color correction (hue, saturation, brightness), shadow color and strength, outline color and width, emission, rim light, matcap, and the upper and lower brightness limits. The original material stays as it is; a copy with the changed values is added. You can switch between it and the original look from the menu.

```text
Make the hair shadows lighter and the outline thinner. I want it to look like this all the time
```

The agent reads the materials of the hair or outfit that is currently shown and their current values, and shows the values it will change (before → after). Then it checks before/after images side by side and applies after you confirm. If you say "all the time", the toggle starts on (switch it off in the menu to go back to the original). You remove it the same way as a color variant.

- Black, white and gray hair or clothes have no color to shift, so changing hue or saturation does almost nothing. Adjust brightness, rim light or outline instead, or make a color variant from the PSD.
- It does not change values such as render mode, transparency or stencil. Shaders other than lilToon and Poiyomi, such as UnityChan Toon Shader, are not supported yet.

### Adjust body shape and fix clipping

Adjusts the avatar's shape without changing the FBX.

- **Body and face**: changes the values of the avatar's shape keys (chest size, waist and so on).
- **Outfits follow the body**: when you change the body shape, the outfit's matching shape keys follow it (Modular Avatar's Blendshape Sync).
- **Remove hidden parts**: removes the body mesh hidden under clothes at build time (Avatar Optimizer's Remove Mesh By BlendShape). This prevents clipping and lowers the polygon count.

```text
Remove the body under the clothes while the hoodie is worn, and make the chest a little bigger
```

The agent reads the shape keys and shows the values it will change and the parts it will remove. It then shows before/after images and triangle counts built the same way VRChat builds them, and applies after you confirm. Undo it with "Undo the Fit_Hoodie body adjustment". Undoing removes only the values this plugin changed and the settings it added; links that came with the avatar stay.

### Attach accessories, hair and outfits

Attaches existing hats, hair, accessories and outfits (prefabs or FBX) to the avatar.

- **Attach to a bone**: attaches hats, ribbons or hair made for the avatar to a bone such as the head (Modular Avatar's Bone Proxy).
- **Merge the armature**: things with their own armature, such as outfits, are merged into the avatar's armature (Modular Avatar's Setup Outfit).
- **Show and hide from the menu**: you can switch attached items on and off from the menu, and hide the original hair and so on only while they are worn.
- **Hold and put down**: have the avatar hold a prop such as a sword or a cup, and leave it where it is with "Put down" in the menu. Props fixed in the world are possible too.

```text
Attach this wolf-cut hair, and let me switch the original hair from the menu
```

The agent looks into candidates and bones, shows how it will attach the item, checks the position in before/after images built the same way VRChat builds them, and applies after you confirm. You can also ask "List the attached accessories" or "Remove WolfHair".

### Make things in Blender, wear unsupported outfits

With **Blender** installed, it can also do the following. Blender runs in the background, so no window opens.

- **Make simple shapes**: combines spheres, cubes, cylinders, cones and rings into small items such as ribbons or horns.
- **Wear unsupported outfits**: deforms hair or outfits made for another avatar to fit this avatar's armature, and pushes parts that sink into the body outward. If you have the FBX of the avatar the outfit was made for, it also transfers body differences such as chest, hips and arm thickness to the outfit. It adds the avatar's body shape keys (such as `Breasts_big`) to the outfit too, so the outfit follows when you change the body shape. After attaching, it goes on to remove the body hidden under the clothes and capture built before/after images.

```text
Put this coat made for Selestia on Salt. The original body is at Assets/Booth/SELESTIA.fbx
```

What it fits automatically: bone positions, directions and lengths, body differences from the original avatar, pushing out of the body, and following the body shape keys. Parts where length or body shape differ a lot may need manual work in Blender. Check each outfit's terms of use to see whether you may use it on another avatar.

Blender is free from [blender.org](https://www.blender.org/download/) (or `winget install BlenderFoundation.Blender`).

### Adjust swinging parts

Changes how hair, skirts, tails and other parts swing, through the values of the avatar's PhysBones. The original prefab stays as it is; the change is saved in the scene.

- **How they swing**: start from presets such as soft, stiff or heavy, then fine-tune pull, gravity and more.
- **Grabbing and posing**: stop other people from grabbing or posing them.
- **Keep them out of the body**: add colliders on the thighs or body so skirts and straps do not pass through the legs.

```text
Make the back hair swing more softly, and stop people grabbing the tail
```

The agent lists the swinging parts and their values (including how many bones each one moves) and shows what changes (before → after) before applying. Images cannot show how something swings, so check it in Gesture Manager or VRChat afterwards. Ask "Undo the SoftHair swing adjustment" to go back.

### Change the view position and single sizes

- **View position**: put the first-person view between the eyes again, or move it up or down a little.
- **Single sizes**: make the head a little bigger or the hands a little smaller, one bone at a time. A bigger head also enlarges the hair, ears and any hat on it. You can also change only that part, such as just the palm or the chest (Modular Avatar Scale Adjuster).

```text
The view is too low, fix it. Make the head a little bigger
```

The agent shows a before/after image with the view position marked in red before applying. Ask "Undo BigHead" to go back.

### Change expressions

Replace the expressions on hand gestures, pick an expression from the menu and keep it, or switch shape keys such as a blush, tears or sweat on and off. The avatar's own animators stay as they are; DSH adds a layer for the expressions (Modular Avatar).

```text
Make the right fist a smile, and let me pick a half-closed-eye look from the menu
```

The agent looks at the face's shape keys and the avatar's own gesture expressions (which hand sign moves which shape keys), shows the recipe, and confirms with a face image for each expression before applying. The author's expressions stay; only the shape keys in the recipe are overridden. Ask "Remove the Face expressions" to take them off.

### Carry changes over to an updated avatar

When the author updates the avatar, the changes made with this plugin (outfit toggles, color variants, body shape, accessories, swinging parts, view position and sizes, expressions) are applied again to the new version.

```text
I updated Salt to the new version; carry my changes over. The new version is in Assets/DSHTest/SaltV2.unity
```

The agent lists the changes on the current avatar and the values changed by hand (in the Inspector, for example). It then reads the new version and checks, change by change, that the meshes, shape keys and bones it uses are there, with close names for anything renamed. Changes that are ready are applied again after one confirmation. Values changed by hand are not copied; they are shown as a list to redo.

### Check the performance rank

Ask "Check the performance rank" and it shows the PC and Mobile performance ranks, the items that set the rank (such as the number of skinned meshes), and what to change to reach the next rank up. These are estimates counted from the original prefab before the build, so check the final rank in the VRChat SDK build panel.

Ask "How many parameter bits are left?" to count the synced parameters (the limit is 256 bits), including what VRCFury and Modular Avatar add when the avatar is built. After a measurement, adding an outfit toggle or accessory shows how many bits remain, and a change that would go over the limit stops before it is applied.

## How it keeps you safe, and how to undo

- **It reads first**: while looking into your project, it only reads files. It starts Unity and records with Git only when it applies a change.
- **It confirms before applying**: the agent shows the target, the planned changes and the files it will create before applying. If the scene or recipe changes after you confirm, it asks again.
- **Git restore points**: for a project that has never used Git, it guides you through making a restore point on your PC. If a project already managed with Git has unrecorded changes, it asks you to record them first.
- **Keep Unity closed**: applying and capturing start a separate Unity. Save the scene and close any Unity that has the project open.
- **It checks the motion before you look**: expressions, menu items and "Put down" are checked by driving an avatar built as for VRChat with gestures and menu items (in place of Gesture Manager). Swinging parts are run in Unity's play mode while the avatar sways, walks and sits, to measure how they swing and how far they go into the legs. Please do the final check of how things swing and the first-person view.
- **It restores the scene on failure**: if the check after saving in Unity fails, it puts the scene back as it was before the run.
- **You can keep going**: a scene saved and checked by this plugin can be changed again without recording it in Git again, until you change it by hand.

You can undo changes made by this plugin by asking as below. Before removing anything, it confirms what it will undo.

| To undo | Example request |
| --- | --- |
| Outfit toggles | "Remove the hoodie toggle" |
| Color variants and lilToon adjustments | "Delete the Hoodie_Blue color variant" |
| Body adjustments | "Undo the Fit_Hoodie body adjustment" |
| Accessories and hair | "Remove WolfHair" |
| Swing adjustments | "Undo the SoftHair swing adjustment" |
| View position and single sizes | "Undo BigHead" |
| Expressions | "Remove the Face expressions" |

For other changes, put the scene back from the Git restore point. Ask in the chat how to do it.

## Tested environment

| Item | DSH | Claude Code |
| --- | --- | --- |
| App | DeepSeek Harness Desktop (Windows) | Claude desktop app |
| Model | DeepSeek V4.1 Flash (shown as `DeepSeek-V41-Flash`) | Opus 5.5 |
| Effort (reasoning strength) | `MAX` | Medium or higher |

Other combinations have not been tested. The Codex version has not been tested yet.

## Troubleshooting

- **VRChat Avatar does not appear.** Check in Plugins that the plugin is installed, and create a new session in DSH.
- **Claude Code does not use the skills.** Check that `dsh-vrc-unity-supporter` is enabled: in the desktop app under **+** → **Plugins** → **Manage plugins**, in the terminal with `/plugin`. Then start a new session (or run `/reload-plugins` in the terminal).
- **It says `claude` is not found.** Install the `claude` command with the Windows steps in [Claude Code setup](https://code.claude.com/docs/en/setup), and reopen PowerShell.
- **Codex does not use the skills.** Check in **Plugins** in the Codex app that **VRChat Avatar (Unity)** is installed, and start a new thread. To get the latest version, run `codex plugin marketplace upgrade dsh-vrc-unity-supporter`.
- **Unity stops partway in Codex.** The first compile takes a few minutes, and Unity may still be running. Ask in the chat "Check whether Unity is still running", then ask again.
- **The project is not found.** Check that the folder open in your app has `Assets` and `ProjectSettings`.
- **It says "Blender was not found".** Install Blender and reopen your app. If you installed it somewhere else, set the environment variable `DSH_BLENDER` to the full path of `blender.exe`.
- **Color variants say "PhotoCraft CLI was not found".** Install PhotoCraft and reopen your app. If you installed it somewhere else, set the environment variable `PHOTOCRAFT_CLI` to the full path of `photocraft-cli.exe`.
- **Capturing (before/after images) fails.** Capturing starts Unity with the GPU. Close Unity and ask again; if it still fails, check the log location shown in the chat.
- **A body adjustment cannot be undone.** Body adjustments applied before 0.10.0 have no record for undoing. Put the scene back from the Git restore point.
- **It asks for a Git name and email address.** Ask in the chat "How do I set the Git name and email address for this project?"
- **The installer stops partway.** Quit DSH from the system tray as well, and check the error shown on screen. [Installer troubleshooting (Japanese)](installer/README.md#うまくいかないとき)
- **The plugin is still 0.2.0.** Update to the latest version. In 0.2.0, the Editor scripts must be placed by hand. [0.2.0 setup (Japanese)](https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/blob/v0.2.0/README.md#プロジェクトへの初期配置)

<details>
<summary>Tests and publishing, for maintainers</summary>

On Windows, `python -B -m unittest discover -s tests -v` runs the regression tests for the read, outfit toggle, color variant, body shape, accessory and Blender CLIs (they use fake Unity, Blender and PhotoCraft, so none of those are needed). On a PC with Unity 2022.3.22f1, a test also compiles the helpers in `templates/Editor/` against Unity's DLLs (skipped elsewhere). On GitHub, `.github/workflows/ci.yml` runs the same tests and `verify-package.ps1` on Windows with Python 3.10 / 3.13 for every push and PR. Check the Claude Code manifest with `claude plugin validate . --strict`. When you bump the version, keep `package.json`, `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` the same (`verify-package.ps1` compares them). For Codex, the manifest is `.codex-plugin/plugin.json`, the marketplace is `.agents/plugins/marketplace.json`, and the entry skill is `codex/skills/vrc-avatar/`. Shared skills are in `skills/`; the Claude Code entry skill (`claude/skills/vrc-avatar/`) and the Codex entry skill both route to every skill. Build the ZIP for BOOTH after committing, with `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-booth.ps1`, into `dist/booth/` (the README inside the ZIP is `booth/00_README_JA.txt`, the product page draft is `booth/LISTING.md`). To use your own Editor scripts, place the helpers from `templates/Editor/` in `Assets/DSH/Editor/`. `templates/AGENTS.template.md` is an optional project note.

```powershell
npm login
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1
```

`publish.ps1` runs the following in order, and **stops without breaking anything** if a prerequisite is missing.

1. `verify-package.ps1` (BOM / skill names / JSON / `dsh.bundle.patch` / plugin manifests)
2. `npm pack --dry-run` to check the package contents
3. Checks npm / gh authentication (if you are not logged in, it shows the command to run and exits)
4. `npm publish --access public` (skipped if the same version exists; if you do not use two-factor authentication, pass an npm token to `-Token`)
5. `gh repo create ... --push`, `git tag`, and pushing the tag

With `-DryRun`, it stops before step 4 and only shows what it would do.

</details>

## License

MIT. For third-party terms, see [THIRD-PARTY.md](THIRD-PARTY.md).
This package is not affiliated with VRChat Inc., Unity Technologies, or the authors of any VPM package.
