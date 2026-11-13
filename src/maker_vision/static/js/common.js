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

const SKELETON = [
    [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12],
    [11, 13], [13, 15], [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4], [3, 5], [4, 6],
];
const KEYPOINT_MIN_CONFIDENCE = 0.5;
const COLORS = {
    box: "#4f8cff",
    skeleton: "rgba(255, 255, 255, 0.85)",
    joint: "#4f8cff",
    line: "#f2b347",
};

export class HeatmapLayer {
    constructor() {
        this.image = null;
        this.loading = false;
    }

    refresh() {
        if (this.loading) return;
        this.loading = true;
        const image = new Image();
        image.onload = () => {
            this.image = image;
            this.loading = false;
        };
        image.onerror = () => {
            this.loading = false;
        };
        image.src = `/api/heatmap.png?t=${Date.now()}`;
    }

    clear() {
        this.image = null;
    }
}

export function drawOverlay(canvas, detections, options = {}) {
    const ctx = canvas.getContext("2d");
    canvas.width = detections.frame_width;
    canvas.height = detections.frame_height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (options.heatmap) {
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(options.heatmap, 0, 0, canvas.width, canvas.height);
        ctx.restore();
    }

    if (options.line) drawCountLine(ctx, canvas, options.line);
    if (options.pendingPoint) drawPoint(ctx, canvas, options.pendingPoint);

    const scale = canvas.width / 1280;
    for (const box of detections.boxes) {
        if (box.keypoints) drawSkeleton(ctx, box.keypoints, scale);
        drawBox(ctx, box, scale, options.showIds !== false);
    }
}

function drawBox(ctx, box, scale, showId) {
    const [x1, y1, x2, y2] = box.xyxy;
    ctx.save();
    ctx.lineWidth = 2.5 * scale;
    ctx.strokeStyle = COLORS.box;
    roundRect(ctx, x1, y1, x2 - x1, y2 - y1, 6 * scale);
    ctx.stroke();
    if (showId) {
        const text = `#${box.track_id}`;
        ctx.font = `600 ${Math.round(17 * scale)}px -apple-system, "Segoe UI", Roboto, sans-serif`;
        const padding = 6 * scale;
        const width = ctx.measureText(text).width + padding * 2;
        const height = 24 * scale;
        const top = Math.max(y1 - height - 4 * scale, 0);
        ctx.fillStyle = COLORS.box;
        roundRect(ctx, x1, top, width, height, 4 * scale);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.textBaseline = "middle";
        ctx.fillText(text, x1 + padding, top + height / 2 + 1);
    }
    ctx.restore();
}

function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
}

function drawSkeleton(ctx, keypoints, scale) {
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineWidth = 3.5 * scale;
    ctx.strokeStyle = COLORS.skeleton;
    for (const [a, b] of SKELETON) {
        const [ax, ay, ac] = keypoints[a];
        const [bx, by, bc] = keypoints[b];
        if (ac < KEYPOINT_MIN_CONFIDENCE || bc < KEYPOINT_MIN_CONFIDENCE) continue;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
    }
    ctx.fillStyle = COLORS.joint;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5 * scale;
    for (const [x, y, c] of keypoints) {
        if (c < KEYPOINT_MIN_CONFIDENCE) continue;
        ctx.beginPath();
        ctx.arc(x, y, 4.5 * scale, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }
    ctx.restore();
}

function drawPoint(ctx, canvas, [x, y]) {
    ctx.fillStyle = COLORS.line;
    ctx.beginPath();
    ctx.arc(x * canvas.width, y * canvas.height, 10, 0, Math.PI * 2);
    ctx.fill();
}

function drawCountLine(ctx, canvas, line) {
    const [x1, y1, x2, y2] = line.map((v, i) => v * (i % 2 === 0 ? canvas.width : canvas.height));
    ctx.save();
    ctx.strokeStyle = COLORS.line;
    ctx.lineWidth = 3;
    ctx.setLineDash([14, 10]);
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
    ctx.fillStyle = COLORS.line;
    ctx.font = "600 24px -apple-system, \"Segoe UI\", Roboto, sans-serif";
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    ctx.fillText("A", mx - nx * 40, my - ny * 40);
    ctx.fillText("B", mx + nx * 40, my + ny * 40);
    ctx.restore();
}
