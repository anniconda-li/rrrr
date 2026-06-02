# WKT1 AI Guide Backend

ESP32S3 AI 对讲导游设备的本地后端测试项目。

设备侧负责录音、拍照、上传 WAV/JPG、拉取回复 WAV 并播放；后端负责 ASR、Dify Workflow 调用、TTS 和 WAV 格式转换。Dify 只负责 RAG + LLM 文本回答，不处理音频和设备协议。

## 当前主测试

完整本地 AI 音频闭环：

```text
问题文本 -> TTS -> ASR -> Dify Workflow -> TTS -> reply.wav
```

运行：

```powershell
python tools\audio\test_ai_audio_loop.py --text "大雁塔有什么故事？"
```

不接真实 Dify，使用 mock 回答：

```powershell
python tools\audio\test_ai_audio_loop.py --text "大雁塔有什么故事？" --mock-dify
```

生成结果在：

```text
tmp/latest/reply.wav
```

## 环境配置

复制 `.env.example` 为 `.env`，并填入真实 Key：

```powershell
copy .env.example .env
```

主要配置：

```text
DASHSCOPE_API_KEY=your_dashscope_api_key
TTS_PROVIDER=dashscope
TTS_MODEL=qwen3-tts-flash
TTS_VOICE=Cherry

ASR_PROVIDER=dashscope
ASR_MODEL=paraformer-realtime-v2

DIFY_API_KEY=your_dify_api_key
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_USER=esp32s3-local-test
DIFY_INPUT_FIELD=question
```

项目入口会通过 `core/config.py` 自动加载根目录 `.env`。

## 依赖

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

还需要本机可运行 `ffmpeg`，用于把 TTS 音频转换为 ESP32S3 可播放格式：

```text
16000Hz / 16-bit / mono / PCM / WAV
```

## 目录结构

- `services/`：正式服务能力，包括 ASR、TTS、Dify、Vision 占位。
- `tools/`：当前常用本地测试和维护脚本。
- `samples/received_wav/`：真实客户端上传 WAV 样本。
- `samples/received_jpg/`：真实客户端上传 JPG 样本。
- `tmp/`：运行时临时产物，可随时清理。
- `docs/`：项目阶段记录。
- `archive/`：已归档的历史测试脚本和旧工具。

## 常用命令

清理临时产物：

```powershell
python tools\maintenance\clean_tmp.py
```

单独测试 Dify：

```powershell
python tools\dify\test_dify_service.py
```

查看当前阶段记录：

```text
docs/current_status.md
```

## 注意

- 不要提交 `.env` 或真实 API Key。
- `tmp/` 只存放运行时产物。
- 需要长期保留的音频/图片样本放到 `samples/`。
