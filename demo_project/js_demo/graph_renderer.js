/**
 * Graph Renderer - 图谱渲染器
 * 基于Canvas的知识图谱可视化组件
 */

class GraphRenderer {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.context = canvasElement.getContext("2d");
        this.nodes = [];
        this.edges = [];
        this.selectedNode = null;
        this.hoveredNode = null;
        this.transform = { x: 0, y: 0, scale: 1 };

        this._bindEvents();
        this._startRenderLoop();
    }

    loadData(graphData) {
        this.nodes = graphData.nodes.map((node, index) => ({
            ...node,
            x: this.canvas.width / 2 + (Math.random() - 0.5) * 400,
            y: this.canvas.height / 2 + (Math.random() - 0.5) * 400,
            velocityX: 0,
            velocityY: 0
        }));
        this.edges = graphData.edges;
    }

    _bindEvents() {
        this.canvas.addEventListener("mousemove", (event) => this._handleMouseMove(event));
        this.canvas.addEventListener("click", (event) => this._handleClick(event));
        this.canvas.addEventListener("wheel", (event) => this._handleWheel(event));
    }

    _handleMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const mouseY = event.clientY - rect.top;

        this.hoveredNode = this.nodes.find(node => {
            const dx = node.x - mouseX;
            const dy = node.y - mouseY;
            return Math.sqrt(dx * dx + dy * dy) < 20;
        });

        this.canvas.style.cursor = this.hoveredNode ? "pointer" : "default";
    }

    _handleClick(event) {
        if (this.hoveredNode) {
            this.selectedNode = this.hoveredNode;
            this.emit("nodeSelected", this.selectedNode);
        }
    }

    _handleWheel(event) {
        event.preventDefault();
        const zoomFactor = event.deltaY > 0 ? 0.9 : 1.1;
        this.transform.scale = Math.max(0.1, Math.min(5, this.transform.scale * zoomFactor));
    }

    _startRenderLoop() {
        const render = () => {
            this._applyPhysics();
            this._draw();
            requestAnimationFrame(render);
        };
        render();
    }

    _applyPhysics() {
        const repulsionForce = 500;
        const attractionForce = 0.003;
        const dampingFactor = 0.85;

        for (let i = 0; i < this.nodes.length; i++) {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const nodeA = this.nodes[i];
                const nodeB = this.nodes[j];
                const deltaX = nodeB.x - nodeA.x;
                const deltaY = nodeB.y - nodeA.y;
                const distance = Math.max(Math.sqrt(deltaX * deltaX + deltaY * deltaY), 1);
                const force = repulsionForce / (distance * distance);
                const forceX = (deltaX / distance) * force;
                const forceY = (deltaY / distance) * force;

                nodeA.velocityX -= forceX;
                nodeA.velocityY -= forceY;
                nodeB.velocityX += forceX;
                nodeB.velocityY += forceY;
            }
        }

        this.edges.forEach(edge => {
            const sourceNode = this.nodes.find(n => n.id === edge.source);
            const targetNode = this.nodes.find(n => n.id === edge.target);
            if (sourceNode && targetNode) {
                const deltaX = targetNode.x - sourceNode.x;
                const deltaY = targetNode.y - sourceNode.y;
                const distance = Math.max(Math.sqrt(deltaX * deltaX + deltaY * deltaY), 1);
                const force = (distance - 100) * attractionForce;
                sourceNode.velocityX += (deltaX / distance) * force;
                sourceNode.velocityY += (deltaY / distance) * force;
                targetNode.velocityX -= (deltaX / distance) * force;
                targetNode.velocityY -= (deltaY / distance) * force;
            }
        });

        this.nodes.forEach(node => {
            node.velocityX *= dampingFactor;
            node.velocityY *= dampingFactor;
            node.x += node.velocityX;
            node.y += node.velocityY;
        });
    }

    _draw() {
        const context = this.context;
        context.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.edges.forEach(edge => {
            const sourceNode = this.nodes.find(n => n.id === edge.source);
            const targetNode = this.nodes.find(n => n.id === edge.target);
            if (sourceNode && targetNode) {
                context.beginPath();
                context.moveTo(sourceNode.x, sourceNode.y);
                context.lineTo(targetNode.x, targetNode.y);
                context.strokeStyle = "rgba(59, 130, 246, 0.3)";
                context.lineWidth = 1;
                context.stroke();
            }
        });

        this.nodes.forEach(node => {
            const isHovered = node === this.hoveredNode;
            const isSelected = node === this.selectedNode;
            const radius = isHovered || isSelected ? 18 : 14;

            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = isSelected ? "#f59e0b" : "#3b82f6";
            context.fill();
            context.strokeStyle = "#60a5fa";
            context.lineWidth = 2;
            context.stroke();

            context.fillStyle = "#f1f5f9";
            context.font = "11px sans-serif";
            context.textAlign = "center";
            context.fillText(node.label, node.x, node.y + radius + 14);
        });
    }

    emit(eventName, data) {
        if (this._eventCallback) {
            this._eventCallback(eventName, data);
        }
    }

    onEvent(callback) {
        this._eventCallback = callback;
    }
}

export default GraphRenderer;
