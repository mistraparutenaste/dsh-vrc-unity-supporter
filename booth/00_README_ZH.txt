VRChat Avatar (Unity) - dsh-vrc-unity-supporter  版本 {{VERSION}}
====================================================================

这是一个让 AI 代理（DeepSeek Harness / Claude Code / Codex）帮助你改造
VRChat 模型的插件。它不打开 Unity 就能读取项目，用 Unity 的 Editor 脚本
应用修改，并检查结果。它不会上传。

AI 代理默认用日语回答。用中文提问，它就会用中文回答。


■ 请先阅读
--------------------------------------------------------------------

・本插件免费，但使用时还需要 AI 代理应用，并另外支付其费用
  （付费订阅或 API 费用）。

・支持的 Unity 版本是 2022.3.22f1（VRChat SDK 面向创作者支持的版本）。
  不支持 Unity 6 项目。

・修改之前，请先备份项目。
  插件在应用修改前会用 Git 创建还原点，并展示内容征求你的同意，
  但无法防止所有失败。


■ 所需环境（Windows 10 / 11）
--------------------------------------------------------------------

  ・AI 代理应用（任选其一）
      DeepSeek Harness Desktop / Claude Code / Codex
  ・Git for Windows
  ・Python 3.10 或更高版本
  ・Unity Hub 和 Unity 2022.3.22f1（已激活许可证）
  ・用 VCC 或 ALCOM 管理、已安装 VRChat SDK - Avatars 的项目

  部分功能还需要 VRCFury、Modular Avatar、Avatar Optimizer、
  PhotoCraft 或 Blender。


■ 解压之前
--------------------------------------------------------------------

  右键点击下载的 ZIP → 属性 → 勾选下方的「解除锁定」→ 确定，
  然后再解压。
  请把解压后的文件夹放在不会删除的位置（例如「文档」中）。
  Claude Code 和 Codex 会从这个文件夹读取插件。


■ 安装方法
--------------------------------------------------------------------

最简单的方法是交给 AI 代理。以这个文件夹为工作文件夹打开 AI 代理应用，
然后发送下面这段话：

  请阅读这个文件夹中的 00_README_ZH.txt，按照其中的安装步骤，
  帮我为我正在使用的应用安装插件。每次运行命令前请先问我，
  需要我自己操作时请等待。

如果要自己安装，请根据你使用的应用执行下面的其中一项。
请把下面的 <文件夹> 替换为本 README 所在文件夹的完整路径
（按住 Shift 右键点击文件夹 →「复制文件地址」即可获得）。

[DeepSeek Harness]
  1. 退出 DeepSeek Harness（包括任务栏通知区域中的图标）。
  2. 双击这个文件夹中的 install.cmd。
  3. 显示完成后启动 DeepSeek Harness，在新会话中选择
     预设「VRChat Avatar」。
  ※ install.cmd 会从网络（npm）下载已发布的版本，
    因此可能会装上比这个 ZIP 更新的版本。

[Claude Code]
  在 PowerShell 中依次运行下面两条命令，然后开始新的会话。

    claude plugin marketplace add "<文件夹>"
    claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter

[Codex]
  在 PowerShell 中运行下面的命令，重新打开 Codex 应用，
  然后在 Plugins 中安装「VRChat Avatar (Unity)」。

    codex plugin marketplace add "<文件夹>"

  ※ Codex 版尚未在作者的环境中测试。

如果想自动获取新版本，可以用
  mistraparutenaste/dsh-vrc-unity-supporter
代替 <文件夹>，从 GitHub 安装。


■ 更新到新版本
--------------------------------------------------------------------

  1. 解压新的 ZIP，用其中的 dsh-vrc-unity-supporter 文件夹整个替换
     之前放置的文件夹（不要改变位置）。
  2. 根据你使用的应用，在 PowerShell 中运行下面的命令。

  [Claude Code]
    claude plugin marketplace update dsh-vrc-unity-supporter
    claude plugin update dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
  [Codex]
    codex plugin marketplace upgrade dsh-vrc-unity-supporter
  [DeepSeek Harness]
    在 Plugins 中更新 dsh-vrc-unity-supporter。

  3. 开始新的会话（Codex 中为新的线程）。


■ 先试试这些
--------------------------------------------------------------------

  1. 把要改造的 Unity 项目文件夹（包含 Assets 和 ProjectSettings 的
     文件夹）作为应用的工作文件夹打开。
  2. 在聊天中发送「调查一下这个项目里的模型结构」。
     这一步只会读取项目的文件。
  3. 请求修改之前，请在 Unity 中保存场景并关闭 Unity。

  详细用法请看 README.md（日语）。英文简介在 docs/DETAIL.md。
  也可以直接问 AI 代理能做什么。


■ 测试情况（截至版本 {{VERSION}}）
--------------------------------------------------------------------

在作者的环境（Windows 11、Unity 2022.3.22f1、VRCFury 1.1475.0、
Modular Avatar 1.18.7、Avatar Optimizer 1.9.23）中测试过的内容：

  ・诊断项目（包含多个模型的项目）
  ・为已放置的服装添加开关，以及移除开关
  ・把饰品、头发挂到骨骼上，以及取下
  ・在 Blender 中调整为其他模型制作的服装并穿上（肩、袖、鞋的位置）
  ・用服装附带的 PSD 制作换色版本，列出和删除
  ・修改了 lilToon 数值（色调校正、边缘光、描边）的副本的前后截图对比
    （lilToon 2.4.1。应用到菜单尚未测试）
  ・调整体型、删除被衣服遮住的身体，以及撤销这些修改
  ・估算性能等级
  以上都测试到了在 Unity 中应用以及 SDK 的预处理（构建）。

尚未测试的内容：

  ・在 VRChat 中的外观和动作（需要由用户上传后确认）
  ・互斥开关（打开一个时另一个关闭）在 Gesture Manager 和
    VRChat 中的表现
  ・用 PSD 制作皮肤、头发、眼睛的换色版本
  ・为其他模型的服装添加 Blendshape Sync 并删除衣服下身体的步骤
  ・Codex 版的所有功能
  ・把 lilToon 调整应用到菜单，以及在 VRChat 中的外观

测试过的模型有限。其他模型或服装可能无法正常使用。


■ 遇到问题与联系方式
--------------------------------------------------------------------

  请查看 README.md（日语）中的「困ったとき」（疑难解答），
  或者让 AI 代理帮你调查问题。
  问题反馈请通过以下任一方式：
    ・GitHub Issues
      https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/issues
    ・BOOTH 消息
  不保证回复或修复的时间。


■ 许可证与免责声明
--------------------------------------------------------------------

  ・采用 MIT 许可证（LICENSE）。可以修改和再分发。
  ・不提供任何担保。作者对使用本插件造成的任何损失不承担责任。
  ・本插件与 VRChat Inc.、Unity Technologies 以及各个包的作者无关。
    VRChat 和 Unity 是各自公司的商标。
  ・不包含模型、服装、头发等任何素材。请遵守各素材作者的使用条款。
    请勿分发用素材制作的东西，例如用附带 PSD 制作的贴图。
  ・本插件在开发中借助了 AI。
