# dsh-vrc-unity-supporter

[日本語](README.md) | [English](README.en.md) | 简体中文 | [한국어](README.ko.md)

这是一个用 AI 代理来改造 VRChat 模型的插件。

AI 代理默认用日语回答。用中文提问，它就会用中文回答。

## 安装方法

### 交给 AI 代理（推荐）

把下面这段话原样粘贴到 DSH、Claude Code 或 Codex 的聊天中并发送。AI 代理会依次引导你完成：检查缺少的软件、安装插件、进行第一次检查。

```text
我想用一个叫「dsh-vrc-unity-supporter」的插件来改造 VRChat 模型。
请在我的 Windows 电脑上，按下面的顺序帮我完成从安装到第一次检查的过程。
请一步一步进行，需要我自己操作的地方请等待。

1. 用命令检查是否已安装以下软件：
   Git / Python 3.10 或更高版本 / Unity Hub 和 Unity 2022.3.22f1 / VCC 或 ALCOM
   缺少的软件请告诉我官方下载地址，并等待我安装。
   请不要自己安装任何东西。
2. 确认我正在使用的应用是 DeepSeek Harness、Claude Code 还是 Codex，然后安装插件。
   - 如果是 Claude Code（包括桌面应用）：
     在 PowerShell 中运行下面两条命令之前先问我，然后再运行。
       claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
       claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
     如果找不到 claude 命令，请告诉我 https://code.claude.com/docs/en/setup 中
     面向 Windows 的步骤，并等待我安装。
   - 如果是 Codex：
     在 PowerShell 中运行下面的命令之前先问我，然后再运行。
       codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
     之后，请引导我在 Codex 应用的 Plugins 中安装「VRChat Avatar (Unity)」。
     如果找不到 codex 命令，请告诉我 https://developers.openai.com/codex/ 中的步骤，
     并等待我安装。
   - 如果是 DeepSeek Harness：
     请引导我在 Plugins → Add plugin 中添加「dsh-vrc-unity-supporter」。
3. 问我要改造的 Unity 项目文件夹（包含 Assets 和 ProjectSettings 的文件夹）。
4. 最后，告诉我在那个文件夹中开始新的会话，并发送下面这句话：
   「调查一下这个项目里的模型结构」

在此之前，请不要修改 Unity 项目中的任何文件。

GitHub 仓库地址：https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/tree/master
```

插件安装后，在新开始的会话中才能使用。

### 在 DSH 中安装

1. 打开 DSH，选择 **Plugins** → **Add plugin**。
2. 在输入框中粘贴下面的包名并安装。

   ```text
   dsh-vrc-unity-supporter
   ```

3. 创建 **新会话**，确认预设列表中出现了 **VRChat Avatar**。

<details>
<summary>从 ZIP 安装</summary>

1. 在这个 GitHub 页面上选择 **Code** → **Download ZIP**。
2. 右键点击下载的 ZIP，选择 **全部解压缩**。
3. 退出 DSH，双击解压后文件夹中的 **`install.cmd`**。
4. 显示完成后，重新启动 DSH，在 **新会话** 中选择 **VRChat Avatar**。

`install.cmd` 使用 DSH 自带的命令，从 npm 下载已发布的版本并安装。安装时请保持网络连接。 [安装程序的详细说明和卸载方法（日语）](installer/README.md)

</details>

### 在 Claude Code 中安装

Claude Code 在 **Claude 桌面应用的 Code 标签页** 和终端版中都可以使用。

**使用桌面应用时**

1. 打开 PowerShell，依次运行下面两条命令。

   ```powershell
   claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   ```powershell
   claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
   ```

   如果显示找不到 `claude`，请按照 [Claude Code 安装说明](https://code.claude.com/docs/en/setup) 中面向 Windows 的步骤安装 `claude` 命令，然后再运行一次。
2. 在桌面应用的 **Code** 标签页中，选择 Unity 项目文件夹并开始新的会话。
3. 在输入框旁的 **+** → **Plugins** → **Manage plugins** 中，确认 `dsh-vrc-unity-supporter` 已显示并已启用。

**使用终端版时**

在 Unity 项目文件夹中打开 Claude Code，依次运行：

```text
/plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
/plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
```

安装后运行 `/reload-plugins`，或开始新的会话。

### 在 Codex 中安装

1. 打开 PowerShell，运行下面的命令添加插件市场。

   ```powershell
   codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   如果显示找不到 `codex`，请按照 [Codex 文档](https://developers.openai.com/codex/) 中的步骤安装 `codex` 命令，然后再运行一次。
2. 重新打开 Codex 应用，在 **Plugins** 中选择插件市场 `dsh-vrc-unity-supporter`，安装 **VRChat Avatar (Unity)**。
3. 在 Unity 项目文件夹中开始新的线程。

在 Codex 中，技能的命令在沙盒中运行。运行 Unity 或 Blender 时，Codex 可能会询问是否可以在沙盒外运行。请先确认要运行的内容，再批准。

### 所需环境

交给 AI 代理时，它会替你检查。如果要自己准备，请在 Windows 上准备好以下内容。

| 所需软件 | 准备事项 |
| --- | --- |
| **DeepSeek Harness Desktop、Claude Code 或 Codex** | DSH 请从官网的 **Download Desktop → Windows (64-bit)** 安装，并按照屏幕提示完成初始设置。Claude Code 使用桌面应用或终端版。Codex 使用应用和 `codex` 命令。[DSH 官网](https://www.deepseek.com/en/harness/) · [Claude Code 概览](https://code.claude.com/docs/en/overview) · [Codex 文档](https://developers.openai.com/codex/) |
| **Git for Windows** | 用来记录修改前的状态，以便之后还原。记录只保存在你的电脑上。[下载 Git](https://git-scm.com/install/win) |
| **Python 3.10 或更高版本** | 用来读取模型的结构。安装后，请重新打开你使用的应用（DSH、Claude Code、Codex）。[下载 Windows 版 Python](https://www.python.org/downloads/windows/) |
| **Unity Hub 和 Unity 2022.3.22f1** | 在 Unity Hub 中设置有效的许可证，并确认可以用这个版本打开项目。[VRChat 官方的 Unity 安装指南](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) |
| **VCC 或 ALCOM 以及模型项目** | 使用你平时用的管理工具即可。要处理的项目需要已安装 **VRChat SDK - Avatars**，并且能在 Unity 中打开。[VCC 设置](https://vcc.docs.vrchat.com/guides/getting-started/) · [下载 ALCOM](https://vrc-get.anatawa12.com/alcom/) |

部分功能还需要其他软件（VRCFury、Modular Avatar、Avatar Optimizer、Meshia、VRCQuestTools、PhotoCraft、Blender）。请查看[功能](#功能)中的表格。

## 试一试

1. 打开要改造的 Unity 项目文件夹，也就是包含 `Assets`、`Packages` 和 `ProjectSettings` 的文件夹。在 DSH 中作为工作区打开，在 Claude Code 和 Codex 中作为工作文件夹打开。
2. 在 DSH 中，把新会话的预设设为 **VRChat Avatar**，模型设为 **DeepSeek V4.1 Flash**，努力程度设为 **MAX**。在 Claude Code 中只需开始新的会话，在 Codex 中只需开始新的线程。
3. 在聊天中发送下面这句话。这一步只会读取项目的文件。

   ```text
   调查一下这个项目里的模型结构
   ```

4. 确认了模型和服装后，把服装名换成你项目中的名称再提出请求。应用之前，请保存场景并关闭 Unity。

   ```text
   让 Outfit_Hoodie 可以在「服装/连帽衫」中开关。初始状态为开
   ```

5. AI 代理会展示目标和计划的修改，确认后再请它应用。服装名不明确时，它会从已保存的场景中列出候选并询问你。
6. 应用后，会显示保存的结果，以及 SDK 预处理是否确认了菜单和动画。要在 VRChat 中试用，请在 Unity 中选择 **VRChat SDK → Show Control Panel → Builder → Offline Testing → Build & Test**。在 VRChat 的 **SDK Test Avatars** 中选择测试用模型，从菜单中开关服装。[VRChat 本地测试步骤](https://creators.vrchat.com/avatars/#local-avatar-testing)

## 功能

| 功能 | 请求示例 | 另外需要 |
| --- | --- | --- |
| 调查模型结构 | 「调查一下这个项目里的模型结构」 | 无 |
| 在菜单中切换服装 | 「让 Outfit_Hoodie 可以在『服装/连帽衫』中开关」 | VRCFury |
| 制作换色版本 | 「做一个把连帽衫改成藏青色的换色版本」 | PhotoCraft、模型附带的 PSD |
| 调整 lilToon 的颜色、阴影、描边 | 「把头发的阴影调淡，描边调细」 | VRCFury、lilToon 或 Poiyomi 材质 |
| 调整体型、修复穿模 | 「删除衣服下面的身体，把胸部稍微调大」 | Modular Avatar、Avatar Optimizer |
| 挂上饰品、头发、服装 | 「把这个狼尾发型挂上去」 | Modular Avatar |
| 用 Blender 制作、穿上非对应服装 | 「把这件为 Selestia 做的外套穿到 Salt 身上」 | Blender、Modular Avatar |
| 调整摆动部件 | 「让后面的头发摆得更轻柔，尾巴不能被抓住」 | 无 |
| 调整视点和局部大小 | 「视点太低了，帮我改一下。把头稍微调大一点」 | 只改手或胸时需要 Modular Avatar |
| 修改表情 | 「把右手握拳改成笑脸，并且可以在菜单里切换成半眯眼」 | Modular Avatar |
| 把修改带到更新后的模型 | 「Salt 更新到新版本了，帮我把修改带过去」 | 无（各修改本身需要的除外） |
| 整理菜单 | 「把 Color 里的 Hair Pink 移到 Hair，把 Facial Set 放到最前面」 | VRCFury |
| 减少多边形 | 「把三角形减到 7 万以下，脸部不要减」 | Meshia |
| 制作 Quest（Android）版本 | 「让它在 Quest 上也能用」 | VRCQuestTools、Unity 的 Android Build Support |
| 查看性能等级和参数容量 | 「查一下性能等级」「参数还剩多少 bit？」 | 无 |

VRCFury、Modular Avatar、Avatar Optimizer、Meshia 和 VRCQuestTools 请用 VCC 或 ALCOM 添加到目标项目中。[VRCFury 安装步骤](https://vrcfury.com/download/)

### 在菜单中切换服装

让放置在场景中的服装可以从 VRChat 菜单中开关。请先把模型和服装放在同一个场景中并保存。

```text
让 Outfit_Hoodie 可以在「服装/连帽衫」中开关。初始状态为开
```

- **只穿一件**：请求「让连帽衫和外套可以切换，一次只穿其中一件」，它们就会成为同一组的开关。打开一个时，另一个会关闭。
- **列出和移除**：用「列出服装开关」查看已创建的开关。请求「移除连帽衫的开关」只会移除那个开关（服装本身保留）。

### 制作换色版本

用模型或服装附带的分层 PSD 制作换色版本。可以改变服装、皮肤、头发、眼睛的颜色，也可以加入你自己准备的标志或图案。原来的 PSD、贴图和材质保持不变，换色版本作为单独的材质添加。可以从菜单中与原来的外观切换。

```text
做一个把连帽衫改成藏青色的换色版本。PSD 在 Downloads\Salt_v1.0.1 中
```

AI 代理会读取 PSD 的图层结构，先说明要修改哪些图层、如何修改，然后再导出。接着在 Unity 中给模型截图，用修改前后并排的图片进行确认。用「列出换色版本」查看已制作的换色版本，用「删除 Hoodie_Blue 换色版本」移除。

- 请安装免费的图像编辑软件 **PhotoCraft**。PSD 通过命令行编辑，不需要打开它的窗口。[下载 PhotoCraft](https://getartcraft.com/apps/photocraft) · [详细用法（日语）](docs/PHOTOCRAFT.md)
- 许多模型的使用条款禁止分发用附带 PSD 制作的贴图。请只在项目内使用。

### 调整 lilToon 的颜色、阴影、描边

即使是没有 PSD 的服装或头发，也可以通过 lilToon 材质的数值调整外观。Poiyomi Toon（9、10，未锁定的）材质也可以使用。可以修改：主色和色调校正（色相、饱和度、亮度）、阴影的颜色和强度、描边的颜色和粗细、自发光、边缘光、MatCap，以及亮度的上限和下限。原来的材质保持不变，会添加一个修改了数值的副本。可以从菜单中与原来的外观切换。

```text
把头发的阴影调淡，描边调细。我想一直保持这个样子
```

AI 代理会读取当前显示的头发或服装所用的材质及其当前数值，并展示要修改的数值（修改前 → 修改后）。接着用修改前后并排的图片确认，征得你的同意后再应用。如果你说「一直保持」，开关的初始状态会设为开（在菜单中关闭即可恢复原样）。移除方法与换色版本相同。

- 黑色、白色、灰色的头发或衣服本身没有颜色，所以改变色相或饱和度几乎没有变化。请改用亮度、边缘光或描边来调整，或者用 PSD 制作换色版本。
- 不会修改渲染模式、透明、模板等数值。暂不支持 lilToon 和 Poiyomi 以外的着色器（例如 UnityChan Toon Shader）。

### 调整体型、修复穿模

不修改 FBX，调整模型的形状。

- **体型和脸**：修改模型附带的形态键（胸部大小、腰围等）的数值。
- **服装跟随**：改变体型时，让服装对应的形态键跟着身体变化（Modular Avatar 的 Blendshape Sync）。
- **删除被遮住的部分**：在构建时删除被衣服遮住的身体网格（Avatar Optimizer 的 Remove Mesh By BlendShape）。不容易穿模，多边形数也会减少。

```text
穿着连帽衫时删除衣服下面的身体，把胸部稍微调大
```

AI 代理会读取形态键，展示要修改的数值和要删除的部位。然后展示用与 VRChat 相同方式构建的修改前后图片和三角形数，征得你的同意后再应用。用「撤销 Fit_Hoodie 的体型调整」可以恢复。撤销的只是本插件修改的数值和添加的设置，模型原本自带的联动会保留。

### 挂上饰品、头发、服装

把现有的帽子、头发、饰品、服装（prefab 或 FBX）挂到模型上。

- **挂到骨骼上**：把帽子、蝴蝶结或模型用的头发挂到头部等骨骼上（Modular Avatar 的 Bone Proxy）。
- **合并骨架**：像服装这样带有骨架的东西，会合并到模型的骨架中（Modular Avatar 的 Setup Outfit）。
- **在菜单中显示和隐藏**：挂上的饰品可以在菜单中开关，并且可以只在佩戴时隐藏原来的头发等。
- **拿在手上、放下**：让模型手里拿着剑、杯子等道具，并可以用菜单中的「放下」把它留在原地。也可以做固定在世界中的道具。

```text
把这个狼尾发型挂上去，原来的头发可以在菜单中切换
```

AI 代理会调查候选和骨骼并说明挂法，用与 VRChat 相同方式构建的修改前后图片确认位置，征得你的同意后再应用。也可以请求「列出挂上的饰品」「移除 WolfHair」。

### 用 Blender 制作、穿上非对应服装

安装 **Blender** 后，还可以做以下事情。Blender 在后台运行，不会打开窗口。

- **制作饰品**：除了球体、立方体等，还可以沿着点平滑地生成带子和绳子（蝴蝶结、角、发箍、颈圈），把截面旋转成圆形物体（纽扣、珠子、铃铛），以及挤出星形和心形板，再组合成饰品。可以左右对称；会整理 UV 和面的朝向，并检查多边形数等。提供模型的 FBX 后，会把部件贴合到头部或头发表面，避免悬空或陷入，并给蝴蝶结的末端等加入摆动用骨骼，佩戴时可用 PhysBone 摆动。
- **穿上非对应的服装**：把为其他模型制作的头发或服装按照这个模型的骨架变形，并把陷入身体的部分向外推出。如果有服装原本对应的模型的 FBX，还会把胸、腰、手臂粗细等体型差异也转移到服装上。它还会在服装上创建模型的体型形态键（例如 `Breasts_big`），因此改变体型时服装也会跟随。挂上之后，会继续删除被衣服遮住的身体，并拍摄构建后的修改前后图片。

```text
把这件为 Selestia 做的外套穿到 Salt 身上。原来的素体在 Assets/Booth/SELESTIA.fbx
```

可以自动调整的是：骨骼的位置、方向和长度，与原模型的体型差异，从身体向外推出，以及跟随体型形态键。长度或体型差异较大的部分，可能需要在 Blender 中手动处理。能否把服装用在其他模型上，请确认各自的使用条款。

Blender 可以从 [blender.org](https://www.blender.org/download/) 免费安装（也可以用 `winget install BlenderFoundation.Blender`）。

### 调整摆动部件

通过模型上 PhysBone 的数值，调整头发、裙子、尾巴等部件的摆动方式。不修改原始 prefab，修改保存在场景中。

- **摆动方式**：先从「轻柔」「偏硬」「沉重下垂」等预设开始，再细调拉力、重力等数值。
- **抓取和摆姿势**：可以让别人无法抓住或摆弄这些部件。
- **防止穿模**：在大腿或身体上添加碰撞体，防止裙子或带子穿过腿部。

```text
让后面的头发摆得更轻柔，尾巴不能被抓住
```

代理会列出摆动部件及其数值（包括每个部件带动的骨骼数），展示要修改的数值（修改前 → 修改后）后再应用。摆动效果无法从图片中确认，应用后请在 Gesture Manager 或 VRChat 中晃动确认。说「还原 SoftHair 的摆动调整」即可还原。

### 调整视点和局部大小

- **视点**：把第一人称视点重新放到两眼之间，或稍微上下移动。
- **局部大小**：以骨骼为单位调整大小，例如把头稍微调大、把手稍微调小。调大头部时，头发、耳朵和戴着的帽子也会一起变大。也可以只改变某个部位，例如只改手掌或胸部（Modular Avatar 的 Scale Adjuster）。

```text
视点太低了，帮我改一下。把头稍微调大一点
```

应用前会展示修改前后的对比图，并用红色标记视点位置。说「还原 BigHead」即可还原。

### 修改表情

可以替换手势对应的表情、从菜单中选择并固定表情，或者开关脸红、眼泪、汗等形态键。不修改模型原有的动画器，而是添加用于表情的图层（Modular Avatar）。

```text
把右手握拳改成笑脸，并且可以在菜单里切换成半眯眼
```

代理会先查看脸部的形态键，以及模型原有的手势表情（哪只手的哪个手势会让哪些形态键变化），然后展示配方，并用每个表情的脸部图片确认后再应用。原作者的表情会保留，只覆盖配方中写到的形态键。说「移除 Face 表情」即可移除。

### 把修改带到更新后的模型

原作者更新模型时，可以把用本插件做的修改（服装开关、换色版本、体型、饰品、摆动部件、视点和大小、表情）重新应用到新版本上。

```text
Salt 更新到新版本了，帮我把修改带过去。新版本放在 Assets/DSHTest/SaltV2.unity
```

代理会列出当前模型上的修改，以及手动修改的数值（例如在 Inspector 中修改的值）。接着读取新版本，逐项确认修改所用的网格、形态键和骨骼是否存在；名称有变化的会给出相近的候选。条件齐全的修改会在确认一次后一并重新应用。手动修改的数值不会自动复制，而是作为需要重做的项目列出。

### 整理菜单

列出 VRChat 中看到的菜单（包括 VRCFury 和 Modular Avatar 在构建时添加的项目，以及「Next」页），并对项目进行移动、改名、设置图标和调整顺序。不修改原作者的菜单文件，而是把 VRCFury 的菜单整理组件集中添加到一个对象上。

```text
让我看看菜单。把 Color 里的 Hair Pink 移到 Hair，把 Facial Set 放到最前面
```

代理会以树状显示构建后的菜单，提出整理方案，确认后再应用。应用后会在构建后的菜单中确认项目已经移动。说「移除 Tidy 菜单整理」即可恢复原来的菜单。

### 减少多边形

使用 [Meshia](https://github.com/RamType0/Meshia.MeshSimplification) 在上传构建时减少多边形（三角形）数量。不修改 FBX 和网格文件。可以指定整个模型的目标（例如 7 万），或者每个网格的比例。脸部（口型同步的网格）和小网格，除非特别指定，否则不会减少。

```text
把三角形减到 7 万以下，脸部不要减
```

代理会查看每个网格的三角形数和等级并展示配方，用构建前后的图片确认没有破损后再应用。如果等级是由蒙皮网格或材质数量决定的，会先建议改善那些项目。说「恢复 Light 的多边形减少」即可恢复。

### 制作 Quest（Android）版本

使用 [VRCQuestTools](https://github.com/kurotu/VRCQuestTools) 从同一个场景制作 Quest（Android）版本。不复制模型，只在为 Android 构建时把材质换成移动端着色器、缩小贴图，并移除你选择的摆动部件。PC 版本不会改变。

```text
让它在 Quest 上也能用。想保留刘海和尾巴的摆动
```

代理会把副本作为 Android 构建并测量 Mobile 等级，与你商量要移除的摆动部件和贴图大小，以 Medium 以内为目标。上传请在 Unity 中切换到 Android 后自行进行（请先在 Unity Hub 中安装 Android Build Support）。说「移除 Quest 设置」即可恢复。

### 查看性能等级

请求「查一下性能等级」，就会显示 PC 和 Mobile 的性能等级、决定等级的项目（例如蒙皮网格的数量），以及提升一个等级的参考。这是用构建前的原始 prefab 统计的参考值，最终等级请在 VRChat SDK 的构建界面中确认。

说「参数还剩多少 bit？」即可统计同步参数的用量（上限 256 bit），包括 VRCFury 和 Modular Avatar 在构建时添加的部分。测量之后，添加服装开关或饰品前会显示剩余量，超过上限的修改会在应用前停止。

## 安全机制和还原方法

- **先只读取**：调查结构时只读取项目的文件。启动 Unity 和用 Git 记录，都在应用修改时才进行。
- **应用前确认**：AI 代理会先展示目标、计划的修改和要创建的文件，再应用。确认后如果场景或配方发生变化，会再次征求确认。
- **Git 还原点**：对于第一次使用 Git 的项目，会引导你在电脑上创建还原点。已经用 Git 管理的项目如果有未记录的修改，会要求你先记录。
- **保持 Unity 关闭**：应用和截图时会另外启动 Unity。请保存场景，并关闭打开了该项目的 Unity。
- **先确认动作再请你查看**：表情、菜单和饰品的「放下」，会用与 VRChat 相同方式构建的模型，通过手势和菜单驱动来确认（代替 Gesture Manager）。摆动部件会在 Unity 的 Play 模式中让模型摇晃、行走、坐下，测量摆动情况和穿入腿部的深度。对于「摆得更轻柔」「不要穿进腿里」这类请求，会一点点调整数值和碰撞体直到达到目标，展示结果后再应用。摆动效果和第一人称视角等最终确认请由你完成。
- **失败时恢复原状**：如果在 Unity 中保存后的检查失败，会把场景恢复到运行前的状态。
- **可以继续修改**：本插件保存并检查过的场景，在你手动修改之前，可以不重新记录到 Git 而继续修改。

用本插件做的修改，可以像下面这样请求还原。移除之前，会确认要还原的内容。

| 要还原的内容 | 请求示例 |
| --- | --- |
| 服装开关 | 「移除连帽衫的开关」 |
| 换色版本、lilToon 调整 | 「删除 Hoodie_Blue 换色版本」 |
| 体型调整 | 「撤销 Fit_Hoodie 的体型调整」 |
| 饰品、头发 | 「移除 WolfHair」 |
| 摆动调整 | 「还原 SoftHair 的摆动调整」 |
| 视点、局部大小 | 「还原 BigHead」 |
| 表情 | 「移除 Face 表情」 |
| 菜单整理 | 「移除 Tidy 菜单整理」 |
| 多边形减少 | 「恢复 Light 的多边形减少」 |
| Quest 版本设置 | 「移除 Quest 设置」 |

其他修改请从 Git 还原点恢复场景。具体方法可以在聊天中询问。

## 测试环境

| 项目 | DSH | Claude Code |
| --- | --- | --- |
| 应用 | DeepSeek Harness Desktop（Windows） | Claude 桌面应用 |
| 模型 | DeepSeek V4.1 Flash（显示为 `DeepSeek-V41-Flash`） | Opus 5.5 |
| 努力程度（推理强度） | `MAX` | 中等或以上 |

其他组合尚未测试。Codex 版尚未测试。

## 遇到问题时

- **不显示 VRChat Avatar。** 在 Plugins 中确认插件已安装，然后在 DSH 中创建新会话。
- **Claude Code 不使用技能。** 确认 `dsh-vrc-unity-supporter` 已启用：桌面应用在 **+** → **Plugins** → **Manage plugins** 中，终端版用 `/plugin`。然后开始新的会话（终端版也可以用 `/reload-plugins`）。
- **显示找不到 `claude`。** 按照 [Claude Code 安装说明](https://code.claude.com/docs/en/setup) 中面向 Windows 的步骤安装 `claude` 命令，然后重新打开 PowerShell。
- **Codex 不使用技能。** 在 Codex 应用的 **Plugins** 中确认已安装 **VRChat Avatar (Unity)**，然后开始新的线程。要更新到最新版本，请运行 `codex plugin marketplace upgrade dsh-vrc-unity-supporter`。
- **在 Codex 中 Unity 的运行中途停止。** 第一次编译需要几分钟，Unity 可能仍在运行。请在聊天中请求「确认 Unity 是否还在运行」，然后再请求一次。
- **找不到项目。** 确认应用中打开的文件夹里有 `Assets` 和 `ProjectSettings`。
- **显示「Blender was not found」。** 安装 Blender，然后重新打开应用。如果安装在其他位置，请把环境变量 `DSH_BLENDER` 设为 `blender.exe` 的完整路径。
- **换色时显示「PhotoCraft CLI was not found」。** 安装 PhotoCraft，然后重新打开应用。如果安装在其他位置，请把环境变量 `PHOTOCRAFT_CLI` 设为 `photocraft-cli.exe` 的完整路径。
- **截图（修改前后的图片）失败。** 截图时会使用 GPU 启动 Unity。请关闭 Unity 后再次请求；如果仍然失败，请查看聊天中显示的日志位置。
- **无法撤销体型调整。** 0.10.0 之前应用的体型调整没有用于撤销的记录。请从 Git 还原点恢复场景。
- **要求输入 Git 的名字和邮箱。** 请在聊天中问「怎样为这个项目设置 Git 的名字和邮箱？」
- **安装程序中途停止。** 请也从任务栏通知区域退出 DSH，并查看屏幕上显示的错误。[安装程序的故障排除（日语）](installer/README.md#うまくいかないとき)
- **插件仍是 0.2.0。** 请更新到最新版本。0.2.0 需要手动放置 Editor 脚本。[0.2.0 的设置步骤（日语）](https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/blob/v0.2.0/README.md#プロジェクトへの初期配置)

<details>
<summary>面向维护者的测试和发布步骤</summary>

在 Windows 上运行 `python -B -m unittest discover -s tests -v`，可以运行读取、服装开关、换色、体型、饰品、Blender 各 CLI 的回归测试（使用假的 Unity、Blender 和 PhotoCraft，因此不需要安装它们）。在装有 Unity 2022.3.22f1 的电脑上，还会运行一个把 `templates/Editor/` 中的辅助脚本按 Unity 的 DLL 编译的测试（没有时跳过）。在 GitHub 上，每次 push 和 PR 时，`.github/workflows/ci.yml` 都会在 Windows 和 Python 3.10 / 3.13 上运行相同的测试和 `verify-package.ps1`。Claude Code 版的清单可以用 `claude plugin validate . --strict` 检查。升级版本时，请让 `package.json`、`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json` 保持一致（`verify-package.ps1` 会核对）。Codex 版的清单是 `.codex-plugin/plugin.json`，插件市场是 `.agents/plugins/marketplace.json`，入口技能是 `codex/skills/vrc-avatar/`。共享技能在 `skills/` 中，Claude Code 用的入口技能（`claude/skills/vrc-avatar/`）和 Codex 用的入口技能都会引导到所有技能。在 BOOTH 发布的 ZIP，请在提交后用 `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-booth.ps1` 生成到 `dist/booth/` 中（ZIP 中的说明是 `booth/00_README_JA.txt`，商品页草稿是 `booth/LISTING.md`）。使用自己的 Editor 脚本时，把 `templates/Editor/` 中的辅助脚本放到 `Assets/DSH/Editor/`。`templates/AGENTS.template.md` 是可选的项目备注。

```powershell
npm login
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1
```

`publish.ps1` 会依次执行以下步骤，缺少前提条件时会**在不破坏任何东西的情况下停止**。

1. `verify-package.ps1`（BOM / 技能名 / JSON / `dsh.bundle.patch` / 插件清单）
2. 用 `npm pack --dry-run` 检查包的内容
3. 检查 npm / gh 的认证（未登录时显示要运行的命令并退出）
4. `npm publish --access public`（如果已存在相同版本则跳过；不使用两步验证时，把 npm 令牌传给 `-Token`）
5. `gh repo create ... --push`、`git tag`、推送标签

加上 `-DryRun` 时不执行第 4 步及之后的步骤，只显示要做什么。

</details>

## 许可证

MIT。第三方组件的处理请参阅 [THIRD-PARTY.md](THIRD-PARTY.md)。
本软件包与 VRChat Inc.、Unity Technologies 以及各 VPM 包的作者无关。
