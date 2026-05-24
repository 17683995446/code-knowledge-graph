/**
 * Code Knowledge Graph - 前端可视化引擎
 * 基于Canvas的知识图谱渲染 + 系统架构图 + 流程图 + 时序图
 */

// ==================== 全局状态 ====================
const AppState = {
    currentPage: 'dashboard',
    websocket: null,
    isConnected: false,
    statistics: null,
    graphData: null,
    dependencyData: null,
    eventLog: [],
    selectedFile: null
};

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initWebSocket();
    loadAllData();
    initGraphCanvas();
});

// ==================== 导航 ====================
function initNavigation() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const page = tab.dataset.page;
            switchPage(page);
        });
    });
}

function switchPage(pageName) {
    AppState.currentPage = pageName;
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.page === pageName);
    });
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.toggle('active', section.id === `page-${pageName}`);
    });
    if (pageName === 'graph') {
        // BUG-FE-12修复：切换页面时停止旧动画循环
        stopAnimationLoop();
        graphNodes = [];
        graphEdges = [];
        setTimeout(() => {
            resizeCanvas();
            renderKnowledgeGraph();
        }, 200);
    }
    if (pageName === 'dependency' && AppState.dependencyData) {
        setTimeout(() => renderDependencyGraph(), 200);
    }
}

// ==================== WebSocket ====================
let wsHeartbeatTimer = null;
let wsReconnectTimer = null;

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    AppState.websocket = new WebSocket(wsUrl);

    AppState.websocket.onopen = () => {
        AppState.isConnected = true;
        updateConnectionStatus(true);
        addEventLog('sync', '已连接到知识图谱服务');
        // BUG-FE-HEARTBEAT-01修复：启动前端心跳ping，每30秒发送一次
        if (wsHeartbeatTimer) clearInterval(wsHeartbeatTimer);
        wsHeartbeatTimer = setInterval(() => {
            if (AppState.websocket && AppState.websocket.readyState === WebSocket.OPEN) {
                AppState.websocket.send('ping');
            }
        }, 30000);
    };

    AppState.websocket.onclose = () => {
        AppState.isConnected = false;
        updateConnectionStatus(false);
        addEventLog('error', '连接已断开，5秒后重连...');
        // BUG-FE-HEARTBEAT-01修复：断开时清理心跳定时器
        if (wsHeartbeatTimer) {
            clearInterval(wsHeartbeatTimer);
            wsHeartbeatTimer = null;
        }
        // BUG-FE-01 修复：防止重连时创建多个连接
        if (AppState.websocket) {
            AppState.websocket = null;
        }
        // BUG-FE-RECONNECT-01修复：重连时清理旧定时器
        if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
        wsReconnectTimer = setTimeout(() => {
            if (!AppState.websocket) initWebSocket();
        }, 5000);
    };

    AppState.websocket.onmessage = (event) => {
        // BUG-FE-02 修复：JSON.parse添加try-catch保护
        try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        } catch (e) {
            console.warn('WebSocket消息解析失败:', event.data);
        }
    };

    AppState.websocket.onerror = () => {
        AppState.isConnected = false;
        updateConnectionStatus(false);
    };
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('connection-dot');
    const text = document.getElementById('connection-text');
    if (dot) dot.classList.toggle('disconnected', !connected);
    if (text) text.textContent = connected ? '已连接' : '未连接';
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'file_update':
            handleFileUpdate(message.data);
            break;
        case 'stats_update':
            AppState.statistics = message.data;
            updateDashboardStats(message.data);
            break;
        case 'full_sync':
            addEventLog('sync', `全量同步完成: ${message.data.updated}个文件`);
            loadAllData();
            break;
    }
}

function handleFileUpdate(data) {
    // BUG-NULL-DEFENSE-01修复：添加空值防御，防止data为null或字段缺失时崩溃
    if (!data) return;
    (data.updated_files || []).forEach(file => {
        addEventLog('update', `文件已更新: ${getShortPath(file)}`);
    });
    (data.errors || []).forEach(err => {
        addEventLog('error', `更新失败: ${err}`);
    });
    loadAllData();
}

// ==================== 数据加载 ====================
async function loadAllData() {
    try {
        // BUG-FE-API-STATUS-01修复：所有API调用添加HTTP状态检查
        const [statsRes, graphRes, depRes, filesRes] = await Promise.allSettled([
            fetch('/api/statistics').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
            fetch('/api/graph').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
            fetch('/api/dependency-graph').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))),
            fetch('/api/files').then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
        ]);

        if (statsRes.status === 'fulfilled') AppState.statistics = statsRes.value;
        if (graphRes.status === 'fulfilled') AppState.graphData = graphRes.value;
        if (depRes.status === 'fulfilled') AppState.dependencyData = depRes.value;

        if (AppState.statistics) updateDashboardStats(AppState.statistics);
        if (AppState.statistics) renderLanguageChart(AppState.statistics.languages || {});
        if (AppState.statistics) renderTypeChart(AppState.statistics.type_kinds || {});
        if (AppState.statistics) renderReferenceChart(AppState.statistics.reference_kinds || {});
        if (filesRes.status === 'fulfilled') renderFileList(filesRes.value);

        if (AppState.currentPage === 'graph') {
            renderKnowledgeGraph();
        }
        if (AppState.currentPage === 'dependency') {
            renderDependencyGraph();
        }
    } catch (error) {
        console.error('数据加载失败:', error);
    }
}

// ==================== 仪表盘统计 ====================
function updateDashboardStats(stats) {
    updateStatCard('stat-files', stats.total_files || 0);
    updateStatCard('stat-types', stats.total_types || 0);
    updateStatCard('stat-functions', stats.total_functions || 0);
    updateStatCard('stat-calls', stats.total_calls || 0);
    updateStatCard('stat-references', stats.total_references || 0);
    updateStatCard('stat-updates', stats.engine_stats?.total_updates || 0);
}

function updateStatCard(elementId, value) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = value.toLocaleString();
}

// ==================== 语言分布图 ====================
function renderLanguageChart(languages) {
    const container = document.getElementById('language-chart');
    if (!container) return;

    const colors = {
        'python': '#3572A5', 'javascript': '#f1e05a', 'typescript': '#3178c6',
        'java': '#b07219', 'go': '#00ADD8', 'c': '#555555', 'cpp': '#f34b7d',
        'rust': '#dea584', 'kotlin': '#A97BFF', 'swift': '#F05138'
    };

    const total = Object.values(languages).reduce((a, b) => a + b, 0);
    if (total === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">暂无数据</div>';
        return;
    }

    let html = '<div style="display:flex;flex-direction:column;gap:12px;">';
    const sorted = Object.entries(languages).sort((a, b) => b[1] - a[1]);

    sorted.forEach(([lang, count]) => {
        const percent = ((count / total) * 100).toFixed(1);
        const color = colors[lang] || '#6b7280';
        html += `
            <div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="font-size:13px;font-weight:500;">${lang}</span>
                    <span style="font-size:13px;color:var(--text-muted);">${count} 文件 (${percent}%)</span>
                </div>
                <div style="height:6px;background:var(--bg-primary);border-radius:3px;overflow:hidden;">
                    <div style="height:100%;width:${percent}%;background:${color};border-radius:3px;transition:width 0.5s;"></div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// ==================== 类型分布图 ====================
function renderTypeChart(typeKinds) {
    const container = document.getElementById('type-chart');
    if (!container) return;

    const colors = {
        'class': '#3b82f6', 'interface': '#8b5cf6', 'struct': '#10b981',
        'enum': '#f59e0b', 'function': '#06b6d4', 'module': '#6b7280',
        'protocol': '#ec4899'
    };

    const total = Object.values(typeKinds).reduce((a, b) => a + b, 0);
    if (total === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">暂无数据</div>';
        return;
    }

    let html = '<div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;">';
    Object.entries(typeKinds).sort((a, b) => b[1] - a[1]).forEach(([kind, count]) => {
        const color = colors[kind] || '#6b7280';
        const percent = ((count / total) * 100).toFixed(1);
        html += `
            <div style="text-align:center;min-width:80px;">
                <div style="width:48px;height:48px;border-radius:12px;background:${color}20;display:flex;align-items:center;justify-content:center;margin:0 auto 8px;">
                    <span style="font-size:20px;font-weight:700;color:${color};">${count}</span>
                </div>
                <div style="font-size:12px;color:var(--text-secondary);">${kind}</div>
                <div style="font-size:11px;color:var(--text-muted);">${percent}%</div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// ==================== 引用关系图 ====================
function renderReferenceChart(refKinds) {
    const container = document.getElementById('reference-chart');
    if (!container) return;

    const colors = {
        'inherit': '#8b5cf6', 'implement': '#ec4899', 'import': '#06b6d4', 'use': '#f59e0b'
    };
    const labels = {
        'inherit': '继承', 'implement': '实现', 'import': '导入', 'use': '使用'
    };

    const total = Object.values(refKinds).reduce((a, b) => a + b, 0);
    if (total === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">暂无数据</div>';
        return;
    }

    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    Object.entries(refKinds).sort((a, b) => b[1] - a[1]).forEach(([kind, count]) => {
        const color = colors[kind] || '#6b7280';
        const label = labels[kind] || kind;
        const percent = ((count / total) * 100).toFixed(1);
        html += `
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0;"></div>
                <span style="font-size:13px;min-width:60px;">${label}</span>
                <div style="flex:1;height:6px;background:var(--bg-primary);border-radius:3px;overflow:hidden;">
                    <div style="height:100%;width:${percent}%;background:${color};border-radius:3px;"></div>
                </div>
                <span style="font-size:13px;color:var(--text-muted);min-width:40px;text-align:right;">${count}</span>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// ==================== 文件列表 ====================
function renderFileList(files) {
    const container = document.getElementById('file-list');
    if (!container) return;

    if (files.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">暂无文件</div>';
        return;
    }

    let html = '';
    files.forEach(file => {
        // BUG-FE-XSS-01修复：使用data属性传递路径，避免onclick中直接拼接导致XSS
        const safePath = escapeHtml(file.path);
        html += `
            <div class="file-item" data-file-path="${safePath}" onclick="showFileDetail(this.dataset.filePath)">
                <span class="file-language-badge ${file.language}">${file.language}</span>
                <span class="file-path">${getShortPath(file.path)}</span>
                <span class="file-modified">${formatTime(file.modified)}</span>
            </div>
        `;
    });
    container.innerHTML = html;
}

// ==================== 知识图谱渲染 ====================
let graphCanvas, graphCtx, graphNodes = [], graphEdges = [];
let isDragging = false, dragNode = null, offsetX = 0, offsetY = 0;
let graphOffsetX = 0, graphOffsetY = 0, graphScale = 1;
let isPanning = false, panStartX = 0, panStartY = 0;

function initGraphCanvas() {
    graphCanvas = document.getElementById('knowledge-graph-canvas');
    if (!graphCanvas) return;
    graphCtx = graphCanvas.getContext('2d');

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    graphCanvas.addEventListener('mousedown', onMouseDown);
    graphCanvas.addEventListener('mousemove', onMouseMove);
    graphCanvas.addEventListener('mouseup', onMouseUp);
    graphCanvas.addEventListener('wheel', onWheel, {passive: false});
    graphCanvas.addEventListener('dblclick', onDoubleClick);
}

function resizeCanvas() {
    if (!graphCanvas) return;
    const rect = graphCanvas.parentElement.getBoundingClientRect();
    // BUG-FE-HIDPI-01修复：处理高DPI屏幕，避免Canvas模糊
    const dpr = window.devicePixelRatio || 1;
    graphCanvas.width = rect.width * dpr;
    graphCanvas.height = rect.height * dpr;
    graphCanvas.style.width = rect.width + 'px';
    graphCanvas.style.height = rect.height + 'px';
    if (graphCtx) graphCtx.scale(dpr, dpr);
    if (AppState.currentPage === 'graph') renderKnowledgeGraph();
}

function renderKnowledgeGraph() {
    if (!graphCtx || !AppState.graphData) return;

    const data = AppState.graphData;
    if (data.nodes.length === 0) {
        graphCtx.clearRect(0, 0, graphCanvas.width, graphCanvas.height);
        graphCtx.fillStyle = '#64748b';
        graphCtx.font = '16px sans-serif';
        graphCtx.textAlign = 'center';
        graphCtx.fillText('暂无图谱数据，请等待文件解析完成...', graphCanvas.width / 2, graphCanvas.height / 2);
        return;
    }

    if (graphNodes.length === 0) {
        initializeGraphNodes(data);
        // BUG-FE-07 修复：启动力导向动画循环
        startAnimationLoop();
    } else {
        drawGraph();
    }
}

// BUG-FE-07 修复：力导向动画循环
let animationFrameId = null;
let animationIterations = 0;
const MAX_ANIMATION_ITERATIONS = 300;

function startAnimationLoop() {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    animationIterations = 0;

    function animate() {
        if (animationIterations < MAX_ANIMATION_ITERATIONS) {
            applyForces();
            animationIterations++;
            drawGraph();
            animationFrameId = requestAnimationFrame(animate);
        }
        // BUG-FE-11修复：达到最大迭代次数后停止动画循环
    }
    animate();
}

function stopAnimationLoop() {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
}

function initializeGraphNodes(data) {
    const width = graphCanvas.clientWidth || graphCanvas.width;
    const height = graphCanvas.clientHeight || graphCanvas.height;
    graphNodes = data.nodes.map((node, i) => ({
        ...node,
        x: width / 2 + (Math.random() - 0.5) * width * 0.6,
        y: height / 2 + (Math.random() - 0.5) * height * 0.6,
        vx: 0, vy: 0,
        radius: node.group === 'type' ? 20 : 14
    }));

    graphEdges = data.edges.map(edge => ({
        ...edge,
        sourceNode: null,
        targetNode: null
    }));

    graphEdges.forEach(edge => {
        edge.sourceNode = graphNodes.find(n => n.id === edge.source);
        edge.targetNode = graphNodes.find(n => n.id === edge.target);
    });
}

function applyForces() {
    const iterations = 3;
    for (let iter = 0; iter < iterations; iter++) {
        // 斥力
        for (let i = 0; i < graphNodes.length; i++) {
            for (let j = i + 1; j < graphNodes.length; j++) {
                const dx = graphNodes[j].x - graphNodes[i].x;
                const dy = graphNodes[j].y - graphNodes[i].y;
                const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
                const force = 800 / (dist * dist);
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                graphNodes[i].vx -= fx;
                graphNodes[i].vy -= fy;
                graphNodes[j].vx += fx;
                graphNodes[j].vy += fy;
            }
        }

        // 引力（边）
        graphEdges.forEach(edge => {
            if (!edge.sourceNode || !edge.targetNode) return;
            const dx = edge.targetNode.x - edge.sourceNode.x;
            const dy = edge.targetNode.y - edge.sourceNode.y;
            const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
            const force = (dist - 120) * 0.005;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            edge.sourceNode.vx += fx;
            edge.sourceNode.vy += fy;
            edge.targetNode.vx -= fx;
            edge.targetNode.vy -= fy;
        });

        // 中心引力
        const centerX = (graphCanvas.clientWidth || graphCanvas.width) / 2;
        const centerY = (graphCanvas.clientHeight || graphCanvas.height) / 2;
        graphNodes.forEach(node => {
            node.vx += (centerX - node.x) * 0.001;
            node.vy += (centerY - node.y) * 0.001;
            node.vx *= 0.9;
            node.vy *= 0.9;
            node.x += node.vx;
            node.y += node.vy;
        });
    }
}

function drawGraph() {
    if (!graphCtx) return;
    const ctx = graphCtx;
    // BUG-FE-HIDPI-01修复：使用CSS尺寸而非canvas像素尺寸（高DPI下后者已被放大）
    const width = graphCanvas.clientWidth || graphCanvas.width;
    const height = graphCanvas.clientHeight || graphCanvas.height;

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.translate(graphOffsetX, graphOffsetY);
    ctx.scale(graphScale, graphScale);

    // 绘制边
    const edgeColors = {
        'call': '#f59e0b',
        'inherit': '#8b5cf6',
        'implement': '#ec4899',
        'import': '#06b6d4',
        'use': '#6b7280'
    };

    graphEdges.forEach(edge => {
        if (!edge.sourceNode || !edge.targetNode) return;
        ctx.beginPath();
        ctx.moveTo(edge.sourceNode.x, edge.sourceNode.y);
        ctx.lineTo(edge.targetNode.x, edge.targetNode.y);
        ctx.strokeStyle = edgeColors[edge.kind] || '#334155';
        ctx.globalAlpha = 0.4;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.globalAlpha = 1;
    });

    // 绘制节点
    graphNodes.forEach(node => {
        const isType = node.group === 'type';
        const radius = node.radius;

        // 节点圆形
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = isType ? '#3b82f6' : '#10b981';
        ctx.fill();
        ctx.strokeStyle = isType ? '#60a5fa' : '#34d399';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 标签
        ctx.fillStyle = '#f1f5f9';
        ctx.font = `${isType ? '12' : '11'}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        const label = node.label.length > 12 ? node.label.substring(0, 12) + '...' : node.label;
        ctx.fillText(label, node.x, node.y + radius + 4);
    });

    ctx.restore();
}

// ==================== 图谱交互 ====================
function onMouseDown(e) {
    const rect = graphCanvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - graphOffsetX) / graphScale;
    const my = (e.clientY - rect.top - graphOffsetY) / graphScale;

    dragNode = graphNodes.find(n => {
        const dx = n.x - mx;
        const dy = n.y - my;
        return Math.sqrt(dx * dx + dy * dy) < n.radius;
    });

    if (dragNode) {
        isDragging = true;
        offsetX = mx - dragNode.x;
        offsetY = my - dragNode.y;
    } else {
        isPanning = true;
        panStartX = e.clientX - graphOffsetX;
        panStartY = e.clientY - graphOffsetY;
    }
}

function onMouseMove(e) {
    if (isDragging && dragNode) {
        const rect = graphCanvas.getBoundingClientRect();
        dragNode.x = (e.clientX - rect.left - graphOffsetX) / graphScale - offsetX;
        dragNode.y = (e.clientY - rect.top - graphOffsetY) / graphScale - offsetY;
        dragNode.vx = 0;
        dragNode.vy = 0;
        drawGraph();
    } else if (isPanning) {
        graphOffsetX = e.clientX - panStartX;
        graphOffsetY = e.clientY - panStartY;
        drawGraph();
    }
}

function onMouseUp() {
    isDragging = false;
    dragNode = null;
    isPanning = false;
}

function onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    graphScale = Math.max(0.1, Math.min(5, graphScale * delta));
    drawGraph();
}

function onDoubleClick(e) {
    const rect = graphCanvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - graphOffsetX) / graphScale;
    const my = (e.clientY - rect.top - graphOffsetY) / graphScale;

    const clickedNode = graphNodes.find(n => {
        const dx = n.x - mx;
        const dy = n.y - my;
        return Math.sqrt(dx * dx + dy * dy) < n.radius;
    });

    if (clickedNode && clickedNode.file_path) {
        showFileDetail(clickedNode.file_path);
    }
}

// ==================== 依赖图渲染 ====================
function renderDependencyGraph() {
    const container = document.getElementById('dependency-graph-canvas');
    if (!container || !AppState.dependencyData) return;

    const data = AppState.dependencyData;
    if (data.nodes.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px;">暂无依赖数据</div>';
        return;
    }

    const width = container.clientWidth;
    const height = 500;

    let svgContent = `<svg width="100%" height="${height}" xmlns="http://www.w3.org/2000/svg">`;
    svgContent += `<defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
        </marker>
        <marker id="arrowhead-inherit" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#8b5cf6" />
        </marker>
        <marker id="arrowhead-import" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#06b6d4" />
        </marker>
    </defs>`;

    const nodePositions = {};
    const cols = Math.ceil(Math.sqrt(data.nodes.length));
    const cellWidth = width / (cols + 1);
    const cellHeight = height / (Math.ceil(data.nodes.length / cols) + 1);

    data.nodes.forEach((node, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        nodePositions[node.id] = {
            x: (col + 1) * cellWidth,
            y: (row + 1) * cellHeight
        };
    });

    const edgeColors = { 'inherit': '#8b5cf6', 'implement': '#ec4899', 'import': '#06b6d4' };

    data.edges.forEach(edge => {
        const from = nodePositions[edge.source];
        const to = nodePositions[edge.target];
        if (from && to) {
            // BUG-R21-WEB-003修复：对来自后端的数据进行XML转义
            const safeKind = escapeXml(edge.kind || '');
            const color = edgeColors[safeKind] || '#3b82f6';
            const marker = safeKind === 'inherit' ? 'arrowhead-inherit' :
                          safeKind === 'import' ? 'arrowhead-import' : 'arrowhead';
            svgContent += `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}"
                stroke="${escapeXml(color)}" stroke-width="1.5" stroke-opacity="0.5" marker-end="url(#${escapeXml(marker)})" />`;
        }
    });

    data.nodes.forEach(node => {
        const pos = nodePositions[node.id];
        svgContent += `
            <rect x="${pos.x - 50}" y="${pos.y - 16}" width="100" height="32" rx="6"
                fill="#1e293b" stroke="#334155" stroke-width="1.5" />
            <text x="${pos.x}" y="${pos.y + 5}" text-anchor="middle" fill="#f1f5f9" font-size="11">
                ${escapeXml(node.label.length > 14 ? node.label.substring(0, 14) + '...' : node.label)}
            </text>
        `;
    });

    svgContent += '</svg>';
    container.innerHTML = svgContent;
}

// ==================== 文件详情 ====================
async function showFileDetail(filePath) {
    try {
        const response = await fetch(`/api/file/${encodeURIComponent(filePath)}`);
        if (!response.ok) {
            console.error(`获取文件详情失败: HTTP ${response.status}`);
            return;
        }
        const details = await response.json();
        if (!details || !details.file) return;

        const panel = document.getElementById('detail-panel');
        if (!panel) return;

        let html = `
            <button class="detail-panel-close" onclick="closeDetailPanel()">&times;</button>
            <h3 style="font-size:16px;margin-bottom:16px;">${getShortPath(filePath)}</h3>
            <div class="detail-section">
                <div class="detail-section-title">基本信息</div>
                <div class="detail-item"><span class="detail-item-label">语言</span><span class="detail-item-value">${details.file.language}</span></div>
                <div class="detail-item"><span class="detail-item-label">类型数</span><span class="detail-item-value">${details.types.length}</span></div>
                <div class="detail-item"><span class="detail-item-label">函数数</span><span class="detail-item-value">${details.functions.length}</span></div>
                <div class="detail-item"><span class="detail-item-label">调用关系</span><span class="detail-item-value">${details.calls.length}</span></div>
                <div class="detail-item"><span class="detail-item-label">引用关系</span><span class="detail-item-value">${details.references.length}</span></div>
            </div>
        `;

        if (details.types.length > 0) {
            html += '<div class="detail-section"><div class="detail-section-title">类型</div>';
            details.types.forEach(t => {
                html += `<div class="detail-item"><span class="detail-item-label">${t.kind}</span><span class="detail-item-value">${t.name}</span></div>`;
            });
            html += '</div>';
        }

        if (details.functions.length > 0) {
            html += '<div class="detail-section"><div class="detail-section-title">函数</div>';
            details.functions.forEach(f => {
                html += `<div class="detail-item"><span class="detail-item-label">${f.type_name}</span><span class="detail-item-value">${f.name}()</span></div>`;
            });
            html += '</div>';
        }

        panel.innerHTML = html;
        panel.classList.add('open');
    } catch (error) {
        console.error('获取文件详情失败:', error);
    }
}

function closeDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (panel) panel.classList.remove('open');
}

// ==================== AI分析 ====================
async function analyzeStructure() {
    const container = document.getElementById('analysis-result');
    if (!container) return;
    container.innerHTML = '<div class="analysis-loading"><div class="loading-spinner"></div><span>正在分析代码结构...</span></div>';

    try {
        const response = await fetch('/api/analysis/structure');
        if (!response.ok) {
            container.innerHTML = `<div class="analysis-content" style="color:var(--danger-color);">分析请求失败 (${response.status})</div>`;
            return;
        }
        const data = await response.json();
        if (data.analysis) {
            container.innerHTML = `<div class="analysis-content">${escapeHtml(data.analysis)}</div>`;
        } else if (data.error) {
            container.innerHTML = `<div class="analysis-content" style="color:var(--danger-color);">${escapeHtml(data.error)}</div>`;
        } else {
            container.innerHTML = '<div class="analysis-content" style="color:var(--text-muted);">分析服务暂不可用</div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="analysis-content" style="color:var(--danger-color);">分析请求失败</div>';
    }
}

async function analyzeDependencies() {
    // BUG-HTML-ID-01修复：AI分析页面使用独立的容器ID
    const container = document.getElementById('ai-dependency-analysis-result');
    if (!container) return;
    container.innerHTML = '<div class="analysis-loading"><div class="loading-spinner"></div><span>正在分析依赖关系...</span></div>';

    try {
        const response = await fetch('/api/analysis/dependencies');
        if (!response.ok) {
            container.innerHTML = `<div class="analysis-content" style="color:var(--danger-color);">分析请求失败 (${response.status})</div>`;
            return;
        }
        const data = await response.json();
        if (data.analysis) {
            container.innerHTML = `<div class="analysis-content">${escapeHtml(data.analysis)}</div>`;
        } else {
            container.innerHTML = '<div class="analysis-content" style="color:var(--text-muted);">分析服务暂不可用</div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="analysis-content" style="color:var(--danger-color);">分析请求失败</div>';
    }
}

async function triggerFullSync() {
    try {
        const response = await fetch('/api/sync', { method: 'POST' });
        if (!response.ok) {
            addEventLog('error', `全量同步触发失败 (${response.status})`);
            return;
        }
        const data = await response.json();
        if (data.error) {
            addEventLog('error', `全量同步失败: ${data.error}`);
        } else {
            addEventLog('sync', `手动触发全量同步: ${data.updated}个文件`);
        }
    } catch (error) {
        addEventLog('error', '全量同步触发失败');
    }
}

// ==================== 事件日志 ====================
function addEventLog(type, message) {
    const now = new Date();
    const time = now.toLocaleTimeString();
    AppState.eventLog.unshift({ type, message, time });
    if (AppState.eventLog.length > 100) AppState.eventLog.pop();

    // BUG-FE-09 修复：更新事件计数器
    const counter = document.getElementById('event-count');
    if (counter) {
        counter.textContent = `${AppState.eventLog.length} 条记录`;
    }

    const container = document.getElementById('event-log-list');
    if (container) {
        const item = document.createElement('div');
        item.className = 'event-log-item fade-in';
        item.innerHTML = `
            <span class="event-time">${time}</span>
            <span class="event-type ${type}">${type.toUpperCase()}</span>
            <span class="event-message">${escapeHtml(message)}</span>
        `;
        container.insertBefore(item, container.firstChild);
        while (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }
}

// BUG-FE-08 修复：添加文件搜索过滤函数
function filterFiles(keyword) {
    const container = document.getElementById('file-list');
    if (!container) return;
    const items = container.querySelectorAll('.file-item');
    const lowerKeyword = keyword.toLowerCase();
    items.forEach(item => {
        const pathEl = item.querySelector('.file-path');
        if (pathEl) {
            const text = pathEl.textContent.toLowerCase();
            item.style.display = text.includes(lowerKeyword) ? '' : 'none';
        }
    });
}

// ==================== 工具函数 ====================
function getShortPath(path) {
    return path.split('/').slice(-3).join('/');
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeXml(text) {
    // BUG-R21-WEB-003修复：添加单引号转义，确保XML属性安全
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}
