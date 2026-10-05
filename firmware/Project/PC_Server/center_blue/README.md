# 中心蓝色区域分析与 C3 回传

独立实现，不依赖上级目录的 `server.py` 或 `blue_analysis.py`。
沿用现有 ESP-CAM → PC → C3 链路，无需修改板端协议和 C3 网页。

## 启动

在 PC_Server 目录运行：

```powershell
py -m pip install -r center_blue/requirements.txt
py center_blue/server.py --show
```

电脑连接 C3 的 PlantGuard 热点，将 ESP-CAM 的 `PC_HOST` 设为电脑
在该热点内的 IPv4 地址，允许 TCP 8765 入站。旧接收程序需要先停止，
避免占用相同端口。默认回传地址：
`http://192.168.4.1/api/v1/camera/readings`。
打开 `http://192.168.4.1/`，网页“蓝色指标”显示本次 `blue_value`。
不带 `--show` 时无需图形桌面；预览中黄色框为中心搜索范围，绿色框为
所选区域的包围框，右侧仅显示提取出的蓝色像素。

```powershell
py center_blue/server.py --c3-url http://192.168.4.1/api/v1/camera/readings --roi-ratio 0.6 --min-pixels 9
py center_blue/server.py --image sample.jpg --preview preview.png
py center_blue/server.py --image sample.jpg --post
py -m unittest discover -s center_blue -p "test_*.py" -v
```

每帧完成分析并提交 C3 后，程序会 GET 同一 C3 主机的
`/api/v1/state`，将 `sensor`（温度、空气湿度、照度及光谱等原始字段）、
`sensor_age_ms`、相机分析结果和本机 UTC `recorded_at` 作为一条 JSON 写入
`center_blue/measurements.jsonl`。文件为 UTF-8 JSON Lines，逐行追加，
可用 `--records-file 路径` 指定已有文件或其他文件名（父目录须存在）。
采样是 C3 定期进行的，`sensor_age_ms` 表示读取时最近一次采样已有多旧，
并不代表拍照瞬间重新采样。C3 尚未采样时 `sensor` 为 `null`；读取失败时
也会保留该相机记录，并在 `sensor_error` 留下原因。文件写入失败时本次
返回失败确认。离线 `--image` 默认只输出 JSON；搭配 `--post` 才会向 C3
提交并写入本地合并记录。

本地图像模式默认只输出 JSON，不发送到 C3；`--post` 会以 `pc-local`
设备身份回传该结果。实际相机模式保留设备、序号、触发来源和拍摄时钟。

## 提取与数值定义

1. 在图像中央截取宽、高各占原图 60% 的矩形；可用 `--roi-ratio` 调整。
2. HSV 筛选蓝色：色相 190–260 度，饱和度至少 0.25，亮度至少 0.15，
   并要求 B 大于 R 和 G。白色、灰色、红色和过暗像素不属于候选区域。
   可用 `--hue-min`、`--hue-max`、`--saturation-min`、`--brightness-min` 调整。
3. 对候选像素计算四邻接连通区域，排除少于 `--min-pixels` 个像素的区域。
   选择到画面中心最近的区域（以最近像素距离衡量）；距离相同时选更大的区域。
   只统计搜索框内的像素，因此跨越边界的区域会被裁切。
4. `blue_value = 100 × mean((B - max(R, G)) / B)`，只在所选蓝色区域内计算。
   值域为 0–100，纯蓝为 100；白、灰不会因为 B 高而被误判为蓝色。
   同时回传所选像素数、ROI、区域包围框、方法名和处理耗时。

这是蓝色相对红绿的颜色优势指标，不是已标定的物质浓度，也不是单纯 B
亮度。相机白平衡、曝光、光源和 JPEG 压缩会影响结果；做定量实验时应
固定拍摄条件，并用标准样品建立浓度映射。默认阈值需结合实际样品调整。

没有符合条件的区域时回传 `selected_pixels=0`、`blue_value=null`、
`analysis_status="no_blue_region"`、`error="no_blue_region"`，网页显示 `--`，
避免把未识别误当作有效的零测量。

## 通信与失败行为

输入为 `PGJ1 + uint32_be(JSON长度) + uint32_be(JPEG长度) + JSON + JPEG`。
每个连接一帧，JSON 上限 4096 字节，图像文件上限 1 MiB，解码后上限
400 万像素。元数据必须包含 `device_id`、`sequence`、`capture_uptime_ms`、
`trigger`（timer/gpio），兼容现有 C3 字段校验。

只有 C3 接受 POST（HTTP 200/201）且本地记录已写入后才给 CAM 返回 `01`；无蓝色结果也会
正常上传并确认。图像损坏、协议错误、C3 拒绝或网络故障返回 `00`，继续
接收下一帧。预览或传感器读取失败不会使已成功上传的帧被重传。HTTP 超时 5 秒，TCP
单次接收超时 10 秒；不自动重复 POST，避免额外写入 C3 历史。当前 C3
接口不按序号去重，若上传成功但文件写入失败或 ACK 丢失，板端重传仍可能
形成重复记录；本地文件同样不按序号去重。
