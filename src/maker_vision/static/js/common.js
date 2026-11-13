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

const COLORS = { line: "#f2b347" };
const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

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

export function drawOverlay(canvas, options = {}) {
    const ctx = canvas.getContext("2d");
    if (canvas.width !== CANVAS_WIDTH) canvas.width = CANVAS_WIDTH;
    if (canvas.height !== CANVAS_HEIGHT) canvas.height = CANVAS_HEIGHT;
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
