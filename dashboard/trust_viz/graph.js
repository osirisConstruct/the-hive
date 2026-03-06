// Trust Graph Visualization with D3.js
// Fetches data from /trust/graph and renders interactive force-directed graph

const CONFIG = {
    width: 1200,
    height: 800,
    nodeRadiusMin: 5,
    nodeRadiusMax: 20,
    edgeWidthMin: 1,
    edgeWidthMax: 5,
    colors: {
        lowTrust: "#ff4444",
        midTrust: "#ffaa00",
        highTrust: "#44ff44",
        noTrust: "#cccccc"
    }
};

let graphData = null;
let simulation = null;
let svg = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    setupControls();
    await fetchGraph();
    if (graphData) renderGraph();
});

async function fetchGraph() {
    try {
        const resp = await fetch('/trust/graph');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        graphData = await resp.json();
        updateStats();
    } catch (err) {
        console.error('Failed to fetch trust graph:', err);
        document.getElementById('graph').innerHTML = `<p style="color:red; text-align:center; padding:50px;">
            Error loading graph: ${err.message}<br>
            Make sure The Hive API is running and /trust/graph endpoint exists.
        </p>`;
    }
}

function updateStats() {
    if (!graphData) return;
    const stats = document.getElementById('stats');
    stats.innerHTML = `
        Agents: <strong>${graphData.metadata.total_agents}</strong> |
        Trust Edges: <strong>${graphData.metadata.total_vouches}</strong> |
        Generated: ${new Date(graphData.metadata.generated_at).toLocaleTimeString()}
    `;
}

function setupControls() {
    const minTrustSlider = document.getElementById('minTrust');
    const minTrustValue = document.getElementById('minTrustValue');
    const showEdgesCheckbox = document.getElementById('showEdges');
    const resetZoomBtn = document.getElementById('resetZoom');
    const exportPNGBtn = document.getElementById('exportPNG');

    minTrustSlider.addEventListener('input', (e) => {
        const val = e.target.value;
        minTrustValue.textContent = val + '%';
        if (simulation) simulation.alpha(0.3).restart();
    });

    showEdgesCheckbox.addEventListener('change', () => {
        if (simulation) updateEdgeVisibility();
    });

    resetZoomBtn.addEventListener('click', () => {
        if (svg) {
            svg.transition().duration(750).call(
                d3.zoom().transform,
                d3.zoomIdentity
            );
        }
    });

    exportPNGBtn.addEventListener('click', exportPNG);
}

function renderGraph() {
    const container = document.getElementById('graph');
    container.innerHTML = '';

    const width = CONFIG.width;
    const height = CONFIG.height;

    // Create SVG
    svg = d3.select('#graph')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', [0, 0, width, height]);

    // Add zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    svg.call(zoom);

    const g = svg.append('g');

    // Build node lookup
    const nodeMap = new Map();
    graphData.nodes.forEach(node => nodeMap.set(node.id, node));

    // Filter edges based on min trust threshold
    const minTrust = parseInt(document.getElementById('minTrust').value) / 100;
    let edges = graphData.edges.filter(e => e.weight >= minTrust);
    let nodes = graphData.nodes.filter(n => n.trust_score / 100 >= minTrust);

    // Edge line generator
    const edgeLine = d3.line()
        .x(d => d.x)
        .y(d => d.y)
        .curve(d3.curveBundle.beta(0.5));

    // Simulation
    simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(d => getNodeRadius(d) + 2).iterations(2));

    // Draw edges
    const edge = g.append('g')
        .attr('class', 'edges')
        .selectAll('line')
        .data(edges)
        .join('line')
        .attr('class', 'edge')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', d => Math.max(CONFIG.edgeWidthMin, d.weight * CONFIG.edgeWidthMax));

    // Draw nodes
    const node = g.append('g')
        .attr('class', 'nodes')
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => getNodeRadius(d))
        .attr('fill', d => getNodeColor(d))
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .call(drag(simulation))
        .on('click', (event, d) => showTooltip(event, d))
        .on('mouseover', function(event, d) {
            d3.select(this).attr('stroke', '#000').attr('stroke-width', 3);
        })
        .on('mouseout', function() {
            d3.select(this).attr('stroke', '#fff').attr('stroke-width', 2);
        });

    // Add labels (agent name, small)
    const label = g.append('g')
        .attr('class', 'labels')
        .selectAll('text')
        .data(nodes)
        .join('text')
        .text(d => d.name.length > 10 ? d.name.substring(0, 8) + '...' : d.name)
        .attr('font-size', 10)
        .attr('text-anchor', 'middle')
        .attr('fill', '#333')
        .attr('pointer-events', 'none');

    // Update positions on tick
    simulation.on('tick', () => {
        edge
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        label
            .attr('x', d => d.x)
            .attr('y', d => d.y + getNodeRadius(d) + 12);
    });

    // Store references for updates
    simulation.nodes(nodes);
    simulation.force('link').links(edges);
    simulation.alpha(1).restart();

    function updateEdgeVisibility() {
        const visible = document.getElementById('showEdges').checked;
        edge.style('display', visible ? 'block' : 'none');
    }
}

function getNodeRadius(node) {
    const score = node.trust_score / 100;
    const scale = d3.scaleSqrt()
        .domain([0, 1])
        .range([CONFIG.nodeRadiusMin, CONFIG.nodeRadiusMax]);
    return scale(score);
}

function getNodeColor(node) {
    const score = node.trust_score / 100;
    if (score >= 0.7) return CONFIG.colors.highTrust;
    if (score >= 0.4) return CONFIG.colors.midTrust;
    if (score > 0) return CONFIG.colors.lowTrust;
    return CONFIG.colors.noTrust;
}

function drag(simulation) {
    function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }

    function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
    }

    function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }

    return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended);
}

function showTooltip(event, node) {
    const tooltip = document.getElementById('tooltip');
    const details = `
        <strong>${node.name}</strong><br>
        DID: ${node.id}<br>
        Trust Score: ${(node.trust_score / 100).toFixed(2)}<br>
        Vouches Received: ${node.vouch_count}
    `.replace(/\n/g, '').replace(/\s{2,}/g, ' ');
    tooltip.innerHTML = details;
    tooltip.style.left = (event.pageX + 10) + 'px';
    tooltip.style.top = (event.pageY + 10) + 'px';
    tooltip.style.display = 'block';

    setTimeout(() => {
        tooltip.style.display = 'none';
    }, 3000);
}

function exportPNG() {
    if (!svg) return;
    const svgData = new XMLSerializer().serializeToString(svg.node());
    const canvas = document.createElement('canvas');
    canvas.width = CONFIG.width;
    canvas.height = CONFIG.height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const img = new Image();
    img.onload = () => {
        ctx.drawImage(img, 0, 0);
        const link = document.createElement('a');
        link.download = 'trust-graph.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    };
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
}
