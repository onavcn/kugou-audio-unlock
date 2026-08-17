# kugou-audio-unlock · 音乐加密音频解密工具（WorkBuddy Skill）

> **关键词（便于搜索）**：酷狗音乐解密 · kgm 转 mp3 · 酷狗音乐解锁 · 酷狗加密音频 · KGM KGMA VPR KGG 解密 · 离线 本地 无损 音频转换 · 酷狗下载的歌 其他播放器放不了 · Python 开源工具 · Kugo-Music-Converter 同类方案 · WorkBuddy 技能
>
> **Keywords**: KuGou music decrypt · kgm to mp3 · kugou audio unlock · kgm kgma vpr kgg decrypt · offline audio converter · pure Python no dependencies · WorkBuddy skill

一个**纯 Python 标准库实现**的酷狗音乐加密音频解密器，把你从酷狗音乐客户端下载的加密音频
（`.kgm` / `.kgma` / `.vpr` / `.kgg`）还原为任意播放器都能播放的标准音频
（FLAC / MP3 / WAV / OGG / M4A）。**全程本地、不联网、不依赖任何闭源桌面程序**，
解密是**无损去壳**，不会重新编码（除非你主动要求转 MP3）。

它同时也是一个 **WorkBuddy 技能（Skill）**——最常见、最简单的用法不是敲命令，而是直接装进
WorkBuddy，然后像聊天一样让它帮你转歌（见下方「如何使用」）。

> 最常用的 `.kgm` / `.kgma` / `.vpr` **零外部依赖**，只用 Python 标准库即可解密；
> `.kgg` 需要你本机的酷狗密钥库（可选支持）。

---

## 目录

- [这是什么 / What is this](#这是什么--what-is-this)
- [核心特性](#核心特性)
- [支持的格式](#支持的格式)
- [如何使用（最简单：装进 WorkBuddy）](#如何使用最简单装进-workbuddy)
- [命令行 / 脚本用法（进阶，可选）](#命令行--脚本用法进阶可选)
- [KGG 说明（诚实边界）](#kgg-说明诚实边界)
- [工作原理（算法）](#工作原理算法)
- [常见问题 FAQ](#常见问题-faq)
- [合规与免责](#合规与免责)
- [灵感来源](#灵感来源)
- [目录结构](#目录结构)
- [License](#license)

---

## 这是什么 / What is this

你在酷狗音乐客户端下载的歌曲，很多是**加密封装**的（常见后缀 `.kgm` / `.kgma` / `.vpr`），
只能在酷狗自己的播放器里放，拷到别的设备或播放器就“放不了 / 提示格式不支持”。

本工具就是用来把这类**你本人拥有合法使用权**的文件，在本地解开封装备、还原成通用音频，
方便你导入手机、车机、无损播放器或剪辑软件。**所有处理都在你自己的电脑上完成，不上传、不联网。**

相比需要安装整套桌面软件的方案，本工具最大的特点是：
- 解密核心只有**一个 Python 文件**，拷走就能用；
- KGM / KGMA / VPR **不需要安装任何第三方库**；
- 不调用、不引用任何桌面端应用程序的内部模块或数据文件；
- 作为 **WorkBuddy 技能**时，你甚至**不用敲任何命令**，跟 AI 说一句就行。

---

## 核心特性

- **零依赖解密**：KGM / KGMA / VPR 使用纯 Python 标准库实现的 XOR 掩码算法，不下载、不引用任何外部文件或闭源程序。
- **可选转码**：解密得到原始音频后，可用独立获取的 `ffmpeg` 转成 MP3（或其它格式）。
- **安全校验**：每个输出都会校验文件头魔数（ID3 / `fLaC` / `RIFF` / `OggS` / MPEG 帧），不合法的结果会被丢弃，**绝不产出损坏文件**。
- **本地优先**：不联网、不上传任何文件，所有处理都在你自己的机器上完成。

---

## 支持的格式

| 格式 | 处理方式 | 是否需要额外密钥 |
|------|----------|------------------|
| `.kgm` / `.kgma` | 内嵌纯 Python XOR 解密 | 否（算法自包含） |
| `.vpr`           | 内嵌纯 Python XOR 解密 | 否（算法自包含） |
| `.kgg`           | 读本机酷狗 `KGMusicV3.db`（SQLCipher）后解密 | 是（需密钥库 + `pysqlcipher3`） |
| `.flac` / `.wav` / `.ogg` / `.m4a` | `ffmpeg` 转码为 MP3 | 否 |
| `.mp3`           | 直接复制 | 否 |

---

## 如何使用（最简单：装进 WorkBuddy）

本工具是一个 **WorkBuddy 技能（Skill）**，推荐这样用，全程不用敲命令：

1. **下载**：点本仓库右上角 `Code → Download ZIP`，或
   ```bash
   git clone https://github.com/onavcn/kugou-audio-unlock.git
   ```
2. **添加进 WorkBuddy**：打开 WorkBuddy 的「技能 / Skills」→「添加技能 / 导入」→ 选择刚才下载的
   **压缩包（.zip）** 或解压后的**文件夹**。
3. **直接用**：在对话框里说「帮我把 `歌名.kgma` 转成 mp3」，WorkBuddy 会自动调用本技能完成
   解密（必要时再转码），并把结果放到你指定的目录。

就这么简单——解密、校验、转码全部由 WorkBuddy 代你跑，你只管说要什么。

---

## 命令行 / 脚本用法（进阶，可选）

如果你更习惯自己跑命令，核心解密器是单个文件 `decrypt_kgm.py`，无需 `pip install` 任何东西
（KGM / KGMA / VPR 只用 Python 标准库，需 Python 3.6+）。

```bash
# 解密单个文件（最常见，无需密钥）
python decrypt_kgm.py "歌名.kgma" "歌名.dec"

# 解密后再用 ffmpeg 转成 MP3（若原文件不是 MP3）
ffmpeg -y -i "歌名.dec" -q:a 0 "歌名.mp3"
```

作为 Python 模块调用：

```python
from decrypt_kgm import decrypt_kgm
fmt = decrypt_kgm("song.kgma", "song.dec")   # -> "flac" / "mp3" / ...
```

> KGG 支持是可选的：需 `pip install pysqlcipher3` 及本机酷狗密钥库，详见下方「KGG 说明」。

---

## KGG 说明（诚实边界）

`.kgg` 的密钥存放在你本机酷狗客户端的 `KGMusicV3.db`（一个 SQLCipher 加密库）中。
要离线解密 KGG，需要：

1. `pysqlcipher3`（通用 pip 包，不是桌面程序）以及系统的 SQLCipher 运行库；
2. 该数据库的主密钥（unlock-music / Kugo-Music-Converter 社区已知的常量），
   通过环境变量 `KGG_DB_MASTER_KEY`（hex）或 `--kgg-key` 提供。

脚本已内置对该库的标准 SQLCipher 配置（page_size=1024、关闭 HMAC、PBKDF2-HMAC-SHA1 等），
并**强制校验输出魔数**：解密结果若不合法会直接删除并报告，绝不会生成看似成功实则损坏的文件。
若当前环境无法提供密钥库 / 密钥，KGG 文件会被跳过并明确告知，可改用酷狗客户端或 unlock-music 网页工具处理。

---

## 工作原理（算法）

KGM / KGMA / VPR 采用社区已知的 **KGM V2 XOR** 方案，核心步骤：

```
fileKey   = header[0x1c:0x2c] + 0x00            # 17 字节
headerLen = uint32 LE at header[0x10]
audio     = 文件中从 headerLen 开始的数据
out[i]    = T( maskV2(i) ^ audio[i] ^ fileKey[i % 17] )
T(x)      = x ^ ((x & 0x0f) << 4)
maskV2(i) = tableV2[i % 272] ^ maskV1(i >> 4)
maskV1(o): while o >= 0x11:  v ^= table1[o % 272]; o >>= 4; v ^= table2[o % 272]; o >>= 4
# VPR 额外：out[i] ^= vprKey[i % 17]
```

算法常量（`table1` / `table2` / `tableV2` / `vprKey`）来自社区公开实现（如 unlock-music），
已在本仓库 `decrypt_kgm.py` 中内嵌并验证。

---

## 常见问题 FAQ

**Q：最简单怎么用？**
A：把本仓库下载成 ZIP，在 WorkBuddy 里「添加技能」导入，然后直接跟 WorkBuddy 说“把 xxx.kgma 转成 mp3”即可，无需敲命令。

**Q：解密出来的文件是什么格式？**
A：由原始音频的文件头自动判定，通常是 FLAC 或 MP3，也可能是 WAV / OGG / M4A。脚本运行后会打印 `format=xxx`。

**Q：KGM / KGMA / VPR 需要联网或安装什么吗？**
A：不需要。只用 Python 标准库，无需 `pip install` 任何包，不联网。

**Q：能不能直接得到 MP3？**
A：如果原文件本身就是 MP3，解密后就是 MP3；如果不是，解密后是一个通用音频，你可以用 `ffmpeg` 再转成 MP3。

**Q：为什么 `.kgg` 解不出来？**
A：`.kgg` 依赖你本机的酷狗密钥库，需要 `pysqlcipher3` 和主密钥。缺少任一条件，脚本会跳过并提示，不会损坏原文件。

**Q：这个工具会把我的文件上传吗？**
A：不会。所有处理都在本地完成，不联网、不上传。

---

## 合规与免责

- 本工具**仅供处理你本人拥有合法使用权的本地文件**。
- 解密是**无损去壳**，不会重新编码（除非你主动要求转 MP3 码率）。
- 本工具不内置任何绕过付费 / 破解版权保护的逻辑；`.kgg` 必须依赖你本机已有的密钥库。
- 使用时请遵守你所在国家或地区的法律法规与平台服务条款。

---

## 灵感来源

本项目的解密思路与实现，是在参考并结合社区开源项目
[**Kugo-Music-Converter**](https://github.com/skxxxkx666/Kugo-Music-Converter)
的思路基础上，以**纯 Python 标准库、单文件、零外部依赖**的方式重新实现与精简而来，
旨在提供一个更轻量、可审计、可移植的本地离线解密方案（同时也是一个即装即用的 WorkBuddy 技能）。

感谢原项目的启发。本项目与其相互独立，算法常量来自社区公开实现（如 unlock-music），

---

## 目录结构

```
kugou-audio-unlock/
├── decrypt_kgm.py   # 核心解密器（纯标准库，零依赖）
├── SKILL.md          # 原始 WorkBuddy 技能定义（含完整执行流程与 ffmpeg 获取说明）
├── README.md         # 本文件
├── LICENSE           # MIT
└── .gitignore
```

---

## License

[MIT](./LICENSE) © 2026 onavcn
