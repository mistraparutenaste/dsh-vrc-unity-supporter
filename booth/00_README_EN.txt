VRChat Avatar (Unity) - dsh-vrc-unity-supporter  version {{VERSION}}
====================================================================

A plugin that lets an AI agent (DeepSeek Harness / Claude Code / Codex)
help you modify VRChat avatars. It reads your project without opening Unity,
applies changes with Unity Editor scripts, and checks the result.
It does not upload.

The agent answers in Japanese unless you write to it in another language.
Write in English and it answers in English.


# Read this first
--------------------------------------------------------------------

- The plugin is free, but you also need an AI agent app and have to pay
  for it separately (a paid plan or API usage).

- It supports Unity 2022.3.22f1 (the version VRChat supports for creators).
  Unity 6 projects are not supported.

- Back up your project before making changes.
  The plugin makes a Git restore point and asks for your approval before
  it applies a change, but it cannot prevent every failure.


# Requirements (Windows 10 / 11)
--------------------------------------------------------------------

  - An AI agent app (one of these)
      DeepSeek Harness Desktop / Claude Code / Codex
  - Git for Windows
  - Python 3.10 or later
  - Unity Hub and Unity 2022.3.22f1 (with an activated license)
  - A project managed with VCC or ALCOM that has VRChat SDK - Avatars

  Some features also need VRCFury, Modular Avatar, Avatar Optimizer,
  PhotoCraft or Blender.


# Before you extract the ZIP
--------------------------------------------------------------------

  Right-click the downloaded ZIP -> Properties -> tick "Unblock" at the
  bottom -> OK, then extract it.
  Keep the extracted folder somewhere you will not delete it
  (for example, in Documents). Claude Code and Codex load the plugin
  from this folder.


# Installation
--------------------------------------------------------------------

The easiest way is to let your AI agent do it. Open your agent app with
this folder as the working folder, and send this message:

  Please read 00_README_EN.txt in this folder and help me install the
  plugin for the app I am using, following its installation steps.
  Ask me before running each command, and wait whenever I need to do
  something myself.

To install it yourself, do one of the following for the app you use.
Replace <folder> below with the full path of the folder this README is in
(Shift + right-click the folder -> "Copy as path").

[DeepSeek Harness]
  1. Quit DeepSeek Harness (also from the system tray).
  2. Double-click install.cmd in this folder.
  3. When it says it has finished, start DeepSeek Harness and choose the
     "VRChat Avatar" preset in a new session.
  Note: install.cmd downloads the published version from the internet
  (npm), so you may get a newer version than this ZIP.

[Claude Code]
  Run these two commands in PowerShell, then start a new session.

    claude plugin marketplace add "<folder>"
    claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter

[Codex]
  Run this in PowerShell, reopen the Codex app, and install
  "VRChat Avatar (Unity)" from Plugins.

    codex plugin marketplace add "<folder>"

  Note: the Codex version has not been tested in the author's
  environment yet.

To get new versions automatically, use
  mistraparutenaste/dsh-vrc-unity-supporter
instead of <folder> to install from GitHub.


# Updating to a new version
--------------------------------------------------------------------

  1. Extract the new ZIP and replace your old folder with the
     dsh-vrc-unity-supporter folder inside it (keep the same location).
  2. Run the following in PowerShell for the app you use.

  [Claude Code]
    claude plugin marketplace update dsh-vrc-unity-supporter
    claude plugin update dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
  [Codex]
    codex plugin marketplace upgrade dsh-vrc-unity-supporter
  [DeepSeek Harness]
    Update dsh-vrc-unity-supporter in Plugins.

  3. Start a new session (a new thread in Codex).


# First steps
--------------------------------------------------------------------

  1. Open the folder of the Unity project you want to modify (the folder
     that has Assets and ProjectSettings) as the app's working folder.
  2. Send "Look into the avatars in this project" in the chat.
     At this stage it only reads the project's files.
  3. Before you ask for changes, save the scene in Unity and close Unity.

  Detailed usage is in README.md (Japanese). An English overview is in
  docs/DETAIL.md. You can also ask the agent what it can do.


# Tested so far (as of version {{VERSION}})
--------------------------------------------------------------------

Tested in the author's environment (Windows 11, Unity 2022.3.22f1,
VRCFury 1.1475.0, Modular Avatar 1.18.7, Avatar Optimizer 1.9.23):

  - Diagnosing a project (a project with several avatars)
  - Toggles for outfits placed in the scene, and removing the toggles
  - Attaching accessories and hair to bones, and removing them
  - Fitting an outfit made for another avatar in Blender and dressing
    the avatar in it (shoulders, sleeves and shoes)
  - Color variants from an outfit's PSD, listing and deleting them
  - Before/after captures of copies with changed lilToon values
    (color correction, rim light, outline)
    (lilToon 2.4.1; applying them to the menu is not tested)
  - Adjusting body shape, removing the body hidden under clothes,
    and undoing both
  - Estimating the performance rank
  All of these were checked up to applying them in Unity and the SDK
  build preprocessing.

Not tested yet:

  - How it looks and moves inside VRChat (you check this by uploading)
  - Exclusive toggles (turning one on turns the other off) in
    Gesture Manager and inside VRChat
  - Color variants of skin, hair and eyes from a PSD
  - Adding Blendshape Sync to an outfit made for another avatar and
    removing the body underneath
  - Anything in the Codex version
  - Applying lilToon adjustments to the menu, and how they look in VRChat

Only a few avatars were tested. Other avatars and outfits may not work.


# Help and contact
--------------------------------------------------------------------

  See 「困ったとき」 (troubleshooting) in README.md (Japanese), or ask
  the agent to look into the problem.
  Report problems through one of these:
    - GitHub Issues
      https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/issues
    - BOOTH messages
  Replies and fixes are not guaranteed.


# License and disclaimer
--------------------------------------------------------------------

  - MIT License (LICENSE). You may modify and redistribute it.
  - No warranty. The author is not responsible for any damage caused by
    using it.
  - This plugin is not affiliated with VRChat Inc., Unity Technologies, or
    the authors of any package. VRChat and Unity are trademarks of their
    respective companies.
  - It contains no avatars, outfits, hair or other assets. Follow the
    terms of use of each asset's author. Do not distribute anything made
    from those assets, such as textures made from a bundled PSD.
  - This plugin was developed with help from AI.
