export const REASONS = {
    cloud_off: "Cloud AI je vypnutá.",
    auto_disabled: "Auto režim není zapnutý.",
    missing_api_key: "Chybí OPENAI_API_KEY v .env.",
    missing_openai_package: "Chybí balíček openai (pip install -e .).",
    busy: "Ještě přemýšlím nad předchozím snímkem…",
    daily_limit: "Denní strop volání je vyčerpaný.",
    no_frame: "Kamera ještě neposlala snímek.",
};

export async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    return { ok: response.ok, data };
}

export function postJson(url, body) {
    return fetchJson(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? {}),
    });
}

export function drawOverlay(canvas, detections, options = {}) {
    const ctx = canvas.getContext("2d");
    canvas.width = detections.frame_width;
    canvas.height = detections.frame_height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (options.line) drawCountLine(ctx, canvas, options.line);
    if (options.pendingPoint) drawPoint(ctx, canvas, options.pendingPoint);

    const scale = canvas.width / 1280;
    ctx.lineWidth = 3 * scale;
    ctx.font = `bold ${Math.round(22 * scale)}px sans-serif`;
    for (const box of detections.boxes) {
        const [x1, y1, x2, y2] = box.xyxy;
        ctx.strokeStyle = "#2ea043";
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        if (options.showIds !== false) {
            ctx.fillStyle = "#2ea043";
            ctx.fillText(`#${box.track_id}`, x1 + 6 * scale, y1 + 24 * scale);
        }
    }
}

function drawPoint(ctx, canvas, [x, y]) {
    ctx.fillStyle = "#d29922";
    ctx.beginPath();
    ctx.arc(x * canvas.width, y * canvas.height, 10, 0, Math.PI * 2);
    ctx.fill();
}

function drawCountLine(ctx, canvas, line) {
    const [x1, y1, x2, y2] = line.map((v, i) => v * (i % 2 === 0 ? canvas.width : canvas.height));
    ctx.save();
    ctx.strokeStyle = "#d29922";
    ctx.lineWidth = 4;
    ctx.setLineDash([16, 10]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.setLineDash([]);
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const length = Math.hypot(x2 - x1, y2 - y1);
    const nx = (y2 - y1) / length;
    const ny = -(x2 - x1) / length;
    ctx.fillStyle = "#d29922";
    ctx.font = "bold 26px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("A", mx - nx * 40, my - ny * 40);
    ctx.fillText("B", mx + nx * 40, my + ny * 40);
    ctx.restore();
}
