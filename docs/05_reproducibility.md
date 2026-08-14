# 可复现性（Reproducibility）模板

## 摘要
简要说明本文件覆盖的复现范围（硬件、固件、实验/数据处理）。

## 必需材料与版本
- 引用 BOM：`bom/BOM.csv`（确保包含 `part_number`、供应商与版本）
- PCB 版本：
- 固件版本/commit：
- 工具链/OS 版本：

## 构建与镜像
- 本地构建命令（示例）：
```
# 在 firmware/ 目录下
make all
```
- 若使用容器：`docker/Dockerfile` 与镜像 tag

## 软件/固件依赖
- 列出依赖与精确版本（`requirements.txt`、`platformio.ini` 等）

## 硬件制作与校准
- Gerber 与制造商设置：`hardware/gerber/` 包含的文件与 SHA256
- 组装顺序：
- 校准步骤：步骤、所需标准样本与参考数据

## 实验/采样协议
- 标准化采样步骤（样本体积、时间、环境条件）以便产生可比数据

## 测试数据与脚本
- 原始数据位置：`data/raw/`
- 处理脚本与参数：`scripts/process.py` 或 `tests/run_repro.sh`
- 校验和文件：`data/checksums.txt`

## 最小复现示例
1. checkout 指定 tag/commit
2. 校验 `bom/BOM.csv` 与 `hardware/gerber/*.zip` 的 SHA256
3. 构建固件并校验二进制 hash
4. 按校准步骤运行一次测量，保存原始数据
5. 运行处理脚本并比对 `tests/results/` 中的期望输出

## 故障排查与常见问题

## 归档与引用
- 在 release 中包含 `data/checksums.txt`、固件二进制与 Gerber 包，建议归档到 Zenodo 并获取 DOI。
