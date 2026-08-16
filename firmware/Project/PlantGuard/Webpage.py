WEBPAGESTRING = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PlantGuard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            background: linear-gradient(135deg, #edf7ef, #dfeee4);
            color: #17351e;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .card {
            width: min(92vw, 420px);
            background: rgba(255,255,255,0.95);
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(17, 49, 26, 0.12);
            padding: 28px 24px;
            text-align: center;
        }
        h1 {
            color: #1d7a4d;
            margin-bottom: 12px;
        }
        .status {
            font-size: 16px;
            margin: 12px 0;
        }
        .reading {
            margin-top: 18px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .box {
            background: #f4faf5;
            border: 1px solid #d3ead9;
            border-radius: 12px;
            padding: 18px 10px;
        }
        .value {
            font-size: 2rem;
            font-weight: bold;
            color: #145a35;
        }
        .label {
            font-size: 0.9rem;
            color: #4c6654;
        }
        .time {
            margin-top: 16px;
            color: #5f7667;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>PlantGuard</h1>
        <div class="status">局域网监控页</div>
        <div class="reading">
            <div class="box">
                <div class="label">温度</div>
                <div class="value" id="temperature">--</div>
                <div class="label">°C</div>
            </div>
            <div class="box">
                <div class="label">湿度</div>
                <div class="value" id="humidity">--</div>
                <div class="label">%</div>
            </div>
        </div>
        <div class="time" id="timestamp">等待数据...</div>
    </div>

    <script>
        const refreshMs = 5000;

        async function loadData() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                document.getElementById('temperature').textContent = data.temperature.toFixed(1);
                document.getElementById('humidity').textContent = data.humidity.toFixed(1);
                document.getElementById('timestamp').textContent = '已刷新: ' + data.elapsed + 's前';
            } catch (e) {
                document.getElementById('timestamp').textContent = '读取中...';
            }
        }

        loadData();
        setInterval(loadData, refreshMs);
    </script>
</body>
</html>
"""