# Android Phone Use skill

[English](README.md) | [简体中文](README.zh-CN.md)

这是一个通过 USB 或无线 ADB 操作 Android 手机的 Codex skill。它读取界面中可访问的文字和位置，通过 uiautomator2 操作手机，并将滚动列表采集为结构化记录，保留 PNG 截图供检查。安装后使用 `$android-phone-use` 调用。

## 基本功能

- 采集当前页面的 UI 树和无损截图。
- 根据实际观察到的控件或坐标，通过 uiautomator2 操作手机。
- 在一次有明确上限的本地操作中采集多页列表。
- 等待选定记录的文字和位置稳定，检查相邻页面的记录重叠。
- 保存结构化记录和每页原始证据，方便检查与比较。

本项目固定了已经接受的 v2 采集版本，使用成熟的 [uiautomator2](https://github.com/openatx/uiautomator2) 和 [adbutils](https://github.com/openatx/adbutils)。分享的价值在于把采集流程、稳定等待、连续性检查和验证方法封装成可复用的 skill。工具本身不调用语言模型。

安装后，可以向 Codex 提出这样的任务：

> 使用 $android-phone-use 检查已连接的 Android 手机，保存当前页面，然后采集当前列表的前 30 条记录并保留截图。

## 适用的手机范围

本项目面向 **Android 手机**。电脑的操作系统和手机的操作系统是两个不同的兼容范围。

| 手机系统 | 本版本的适用范围 |
|---|---|
| Android，以及基于 Android 的厂商系统 | 目标平台。手机必须授权 ADB，并允许 Android UiAutomator 服务运行；每台设备和具体应用仍需验证。 |
| 保留 Android 兼容能力的华为系统 | 有条件尝试，未验证。必须确认该系统上的 ADB 和 Android UiAutomator 实际可用，仅能安装 APK 不足以判断兼容。 |
| HarmonyOS NEXT / 原生鸿蒙 | 不支持。本项目没有鸿蒙 HDC 或原生 UI 自动化后端。 |
| iPhone / iOS | 不支持。本项目没有 iOS 自动化后端。 |

此前的真机采集验证仅使用了 **OnePlus 8T、Android 13、无线 ADB**，测试对象是系统设置中的应用列表。这不能代表所有 Android 版本、手机品牌或应用都已验证。本版本没有宣称经过测试的最低 Android 版本。

手机需要开启调试、授权所选主机，并在 `adb devices` 中显示为 `device`。连接方法见 [Android 官方 ADB 文档](https://developer.android.com/tools/adb)。界面采集依赖 Android UiAutomator 能访问的内容，自绘控件或纯图片内容可能需要检查截图。鸿蒙有独立的工具链，见 [华为 HDC 文档](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/hdc)；本版本没有实现该后端。

## 运行环境

| 主机 | 执行方式 | 验证情况 |
|---|---|---|
| Windows Codex | Windows Python 3.13 和 Windows ADB | 此前真机采集验证，以及当前运行检查 |
| WSL Codex CLI，默认路线 | 明确转调 Windows Python 与 Windows ADB，并转换输出路径 | 运行检查通过，包括从 WSL 文件系统执行 |
| WSL Codex CLI，`--runtime native` | Linux Python 3.10 及以上、Linux 依赖和 Linux ADB | 在 WSL 中通过运行检查，未做 Linux 真机流程验证 |
| 独立 Linux 系统 | 使用 Linux 原生路线，不需要 Windows | 原生路线在 WSL 中检查过，独立 Linux 真机流程未验证 |

每条路线使用独立的依赖目录。指定路线失败时，工具会报错，不会自动换用另一台主机的运行环境。原生 Linux 不需要 Windows，可通过 `--runtime native` 明确选择。

此前的真机采集测试在 Windows 上完成。Linux 原生入口已在 WSL 的 Linux 运行时通过检查，尚未验证 Linux 真机完整流程与性能。

**WSL 和 Linux 都有可用入口，本项目并非只能在 Windows 上运行。** WSL 默认复用 Windows 执行路线；明确选择原生模式后，使用 Linux 工具。原生模式要求 Linux ADB 能通过 USB 或已授权的无线连接访问手机。在 WSL 中走 USB 原生路线时，还需要让 USB 设备可由 WSL 访问。没有连接手机时，`doctor` 成功只表示运行环境可用。

## 全局安装

克隆仓库并安装：

```bash
git clone https://github.com/sesonli/android-phone-use-skill.git
cd android-phone-use-skill
python3 install.py
```

也可以下载源码，解压后在源码目录运行 `install.py`。

默认安装到当前用户的 `.agents/skills/android-phone-use`，这是 [Codex 文档列出的全局 skill 目录](https://learn.chatgpt.com/docs/build-skills)。Windows 使用 `py -3.13 install.py`。如果主机有自己的 skill 目录，可用 `--destination` 指定目标目录。安装器会保留已有的同名 skill，并停止覆盖操作。

进入已安装的 skill 目录，准备依赖并检查运行环境：

```bash
python3 scripts/run.py setup
python3 scripts/run.py doctor
```

Windows 将 `python3` 换成 `py -3.13`。WSL 默认转调 Windows；如果找不到 Windows Python，可设置 `PHONEUSE_WINDOWS_PYTHON`。纯 Linux 默认使用原生路线，也可以明确指定：

```bash
python3 scripts/run.py --runtime native setup
python3 scripts/run.py --runtime native doctor
```

依赖安装需要所选运行环境提供 pip 或 uv，工具会报告实际使用的安装器。Python 依赖安装在 skill 内部，不修改全局 Python 包。如果 ADB 不可用，请安装 Android platform-tools，或用 `ANDROID_ADB_EXE` 指定对应主机的 ADB。

也可通过 Codex 的 skill 安装器安装仓库中的 `skills/android-phone-use` 目录。安装后如果列表中没有出现该 skill，可以重新打开选择器或启动新对话。

## 页面采集

在已安装的 skill 目录运行：

```bash
python3 scripts/run.py devices
python3 scripts/run.py toolkit --serial DEVICE_SERIAL snapshot --output evidence/current.json --screenshot
```

将 `DEVICE_SERIAL` 替换为当前已连接且授权的手机序列号。无线调试的地址和端口会变化，应使用本次连接的信息。

列表采集需要先观察当前应用，确定记录的资源 ID、内容区域和滚动方式。详细命令、稳定模式示例和上游操作入口见 [使用说明](skills/android-phone-use/references/usage.md)。

## 固定版本与验证

版本 2.0.0 保留了 v2 的采集函数。默认使用 `conservative` 模式；对于已经确认有顺序且记录可区分的列表，可以使用 `stable` 模式。执行入口会检查冻结文件的哈希，依赖使用精确版本；如果已有依赖缓存与固定版本不同，安装会停止。

[来源与测试记录](skills/android-phone-use/references/provenance.md) 说明了此前 Android 设置列表的同记录对比，以及测试范围。这些结果不能直接代表其他应用的覆盖率和速度。

共享源码不包含私人界面采集、设备标识、配对码或主机凭据。依赖在使用时安装，源码包不包含各平台的运行缓存。

## 许可

本项目的代码与说明采用 [MIT 许可](LICENSE)。uiautomator2、adbutils 等依赖保留各自的上游许可。工具不会下载或调用语言模型。

## 发布检查

在仓库目录运行：

```bash
python3 -m unittest discover -s tests -v
python3 skills/android-phone-use/scripts/run.py verify
```

这些检查覆盖冻结文件被修改、保留已有安装、Windows 路线失败后禁止换用原生路线，以及原生路线拒绝 Windows ADB 的情况。检查不需要连接手机；具体应用的完整流程仍需要单独验证。
