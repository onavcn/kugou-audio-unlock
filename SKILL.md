---
name: kugou-audio-unlock
description: >-
  将酷狗音乐加密音频（.kgm / .kgma / .vpr，以及需要密钥库的 .kgg）解密并转换为标准
  MP3（或保留 FLAC/WAV）。当用户想把酷狗下载的歌曲转成通用格式、或提到“酷狗加密文件无法播放/
  转换/解锁/转 MP3”时使用。本技能完全自包含：KGM/KGMA/VPR 用纯 Python 标准库解密（零外部依赖），
  转码用独立获取的 ffmpeg，不引用、不调用任何桌面端应用程序的内部模块、HTTP 接口或数据文件。
---

# KuGou 加密音频解锁（独立技能）

## 一、功能定位

把酷狗音乐客户端下载的**加密音频文件**还原成任意播放器都能播放的**标准音频**（默认 MP3，
无损场景可保留 FLAC/WAV）。核心解密逻辑内嵌在本技能的 `decrypt_kgm.py` 中，是**纯 Python 标准库
实现，不依赖任何外部文件或闭源程序**。

适用格式：

| 格式 | 处理方式 | 是否需要额外密钥 |
|------|----------|------------------|
| `.kgm` / `.kgma` | 内嵌纯 Python XOR 解密 | 否（算法自包含） |
| `.vpr` | 内嵌纯 Python XOR 解密 | 否（算法自包含） |
| `.kgg` | 读本机酷狗 `KGMusicV3.db`（SQLCipher）后解密 | 是（需密钥库 + `pysqlcipher3`） |
| `.flac` / `.wav` / `.ogg` / `.m4a` | ffmpeg 转码为 MP3 | 否 |
| `.mp3` | 直接复制 | 否 |

## 二、触发条件

在以下场景启用本技能（不要依赖任何桌面端 app）：

- 用户说“把酷狗下载的歌转成 MP3 / 解锁 / 转换 / 解密”。
- 用户给出 `.kgm` / `.kgma` / `.vpr` / `.kgg` 文件或所在文件夹。
- 用户反馈“酷狗的文件在别的播放器放不了”。
- 批量处理一个文件夹里的酷狗加密歌曲。

注意：`.ncm` 是网易云格式，不在本技能范围；遇到时说明并建议用网易云专用工具。

## 三、与桌面端程序的独立性（重要）

本技能**不引用、不导入、不调用**任何外部桌面应用程序。具体而言：

- ❌ 不使用 `kugo-converter.exe` 或其 HTTP 接口（`/api/convert-stream` 等）。
- ❌ 不读取桌面程序目录里的 `kugo-converter.exe` / `ffmpeg.exe` / `启动.bat`。
- ❌ 不依赖桌面程序的数据结构或配置。
- ✅ 解密算法直接在本技能的 `decrypt_kgm.py` 内实现（标准库）。
- ✅ ffmpeg 由本技能**独立获取**（见下文“转码”一节），不借用桌面程序的副本。

## 四、执行逻辑

1. **收集输入**：文件、文件夹或 `.zip`（若是 zip 先解压到临时目录）。
2. **分类**：
   - 加密类：`kgm` / `kgma` / `vpr` / `kgg` → 走解密。
   - 普通类：`flac` / `wav` / `ogg` / `m4a` → 走 ffmpeg 转码。
   - `mp3` → 直接复制。
3. **解密**：对每个加密文件，用技能目录下的 `decrypt_kgm.py` 解出原始音频
   （FLAC / MP3 / WAV / OGG，由魔数自动判定）。
4. **转码**：若解密结果不是 MP3，用独立获取的 ffmpeg 转成 MP3（VBR 最高质量 `-q:a 0`；
   若用户要固定码率则用 `-b:a 320k`）。
5. **校验**：每个产物都检查文件头魔数（ID3 / `fLaC` / `RIFF` / `OggS` / MPEG 帧同步），
   非法的直接丢弃并报告，绝不产出损坏文件。
6. **清单**：输出目录生成 `转换清单.md`，列出每个文件、大小、来源格式、结果。

## 五、解密器用法（核心，自包含）

解密器位于本技能目录：`decrypt_kgm.py`（纯标准库，KGM/KGMA/VPR 零依赖）。

```bash
# KGM / KGMA / VPR（最常见，无需密钥）
python decrypt_kgm.py "歌名.kgma" "歌名.dec"

# KGG（需要本机酷狗密钥库；失败会被防护，不会损坏原文件）
python decrypt_kgm.py "歌名.kgg" "歌名.dec" \
    --kgg-db "<本机酷狗 KGMusicV3.db 的绝对路径>" \
    --kgg-key <KGMusicV3.db 的主密钥 hex>
```

`decrypt_kgm.py` 运行后打印 `OK format=<flac|mp3|wav|ogg> -> <输出路径>`；
KGM/KGMA/VPR 一定可用；KGG 在缺少 `pysqlcipher3` 或密钥时会明确报错并跳过该文件。

> 技能目录路径：加载本技能后，用技能所在目录拼接 `decrypt_kgm.py`（例如
> `~/.workbuddy/skills/kugou-audio-unlock/decrypt_kgm.py`）。运行前先 `Read` 该文件确认内容，
> 再写入临时脚本或直接调用。

## 六、转码（ffmpeg 独立获取）

本技能**自行获取** ffmpeg，不碰桌面程序：

1. 先在 PATH 里找系统 `ffmpeg`；找到就用。
2. 找不到则在受管隔离 venv 里用 `imageio_ffmpeg.get_ffmpeg_exe()` 拿到便携 ffmpeg
   （仅本机缓存，不污染用户环境）。
   - 在 WorkBuddy 受管环境下 `imageio-ffmpeg` 已预装，ffmpeg 立即可用，无需联网下载，
     其位于受管 Python venv 的
     `.../site-packages/imageio_ffmpeg/binaries/ffmpeg-<平台>.exe`
     （Windows 为 `ffmpeg-win-x86_64-v*.exe`，macOS / Linux 类似）。
   - 若换到全新环境，在任意 Python venv 里 `pip install imageio-ffmpeg` 即可。
3. 转码命令（FLAC/WAV/OGG → MP3）：
   ```bash
   ffmpeg -y -i "输入.dec" -q:a 0 "输出.mp3"
   ```

## 七、KGG 说明（诚实边界）

`.kgg` 的密钥存放在用户本机酷狗客户端的 `KGMusicV3.db`（一个 SQLCipher 加密库）。要离线解密 KGG：

- 需要 `pysqlcipher3`（通用 pip 包，不是桌面程序）以及该库的主密钥
  （unlock-music / Kugo-Music-Converter 内嵌的已知常量，可通过环境变量 `KGG_DB_MASTER_KEY`
  或 `--kgg-key` 提供）。
- `decrypt_kgm.py` 已内置该路径，且**强制校验输出魔数**：解密结果若不合法会直接删除并报告，
  绝不会生成看似成功实则损坏的文件。
- 若当前环境无法提供密钥库/密钥，KGG 文件会被跳过并明确告知用户，可改用酷狗客户端或
  unlock-music 网页工具处理——这属于格式固有限制，非本技能的耦合问题。

## 八、输出命名与冲突

- 默认输出文件名 = 原歌曲名（去掉加密后缀）+ `.mp3`。
- 若源目录里同一首歌同时存在 `.kgma` 和 `.mp3`，会产生两份 MP3（一份带 `_1` 后缀），属正常现象。

## 九、注意事项 / 合规

- 仅处理用户本人拥有合法使用权限的本地文件。
- 解密是无损去壳，不重新编码（除非用户主动要求转 MP3 码率）。
- 不联网、不上传任何文件，全程本地处理。

## 十、最小可运行示例（单文件）

```python
# 由 agent 在运行时构造（引用技能目录下的 decrypt_kgm.py）
import subprocess, os, shutil, glob

SKILL_DIR = "<技能目录>"          # 例如 ~/.workbuddy/skills/kugou-audio-unlock
DEC = os.path.join(SKILL_DIR, "decrypt_kgm.py")
PY  = "<你的 Python 解释器路径，或直接使用 'python'>"   # 例如 Windows 受管环境
OUT = "输出目录"

os.makedirs(OUT, exist_ok=True)
for src in glob.glob("输入目录/*"):
    ext = os.path.splitext(src)[1].lower()
    base = os.path.splitext(os.path.basename(src))[0]
    dec = os.path.join(OUT, base + ".dec")
    if ext in (".kgm", ".kgma", ".vpr"):
        r = subprocess.run([PY, DEC, src, dec], capture_output=True, text=True)
        # 根据 r.stdout 里的 format= 决定下一步转码或直接用
    elif ext == ".mp3":
        shutil.copy2(src, os.path.join(OUT, base + ".mp3"))
    elif ext in (".flac", ".wav", ".ogg", ".m4a"):
        subprocess.run([FFMPEG, "-y", "-i", src, "-q:a", "0",
                        os.path.join(OUT, base + ".mp3")], check=True)
```
